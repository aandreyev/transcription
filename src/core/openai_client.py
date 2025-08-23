import os
import re
import time
import json
from typing import Dict, Any, Optional, Tuple
from openai import OpenAI
from src.utils import ConfigManager, log_info, log_error, log_warning, read_prompt_file
from src.utils.prompt_manager import build_transcript_summary, combine_prompt, resolve_openai_params

class OpenAIProcessor:
    def __init__(self):
        self.config = ConfigManager()
        self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key or self.api_key == "your_openai_key_here":
            raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file")
        
        self.client = OpenAI(api_key=self.api_key)
    
    def process_transcript(self, transcript: str, original_filename: str = "", job_id: Optional[int] = None, duration_minutes: Optional[int] = None, *, prompt_overrides: Optional[Dict[str, Any]] = None, extra_instructions: str = "") -> str:
        """
        Process transcript using OpenAI to generate summary and extract information
        
        Args:
            transcript: The transcript text to process
            original_filename: Original filename for context
            job_id: Optional job ID for logging
            duration_minutes: Duration of the audio in minutes
            
        Returns:
            Processed content with summary, action items, and decisions
        """
        try:
            log_info(f"Starting OpenAI processing for transcript ({len(transcript)} chars)", job_id)
            
            duration_str = str(duration_minutes) if duration_minutes else 'Unknown'
            base_template = read_prompt_file('summary', self.config)
            placeholders = {
                'transcript': transcript,
                'original_filename': original_filename,
                'duration_minutes': duration_str,
            }
            smode = (prompt_overrides or {}).get('prompts', {}).get('summary_mode', 'replace')
            summary_prompt = combine_prompt(
                base_template=base_template,
                folder_body=extra_instructions or '',
                placeholders=placeholders,
                mode=smode,
                section_heading='Folder Instructions',
            )
            
            if not summary_prompt.strip():
                raise ValueError("Summary prompt not configured")
            
            # Process with retry logic
            model, temperature, max_tokens = resolve_openai_params(config=self.config, overrides=prompt_overrides)
            processed_content = self._process_with_retry(summary_prompt, job_id, model=model, temperature=temperature, max_tokens=max_tokens)
            
            log_info(f"OpenAI processing completed. Output length: {len(processed_content)} chars", job_id)
            return processed_content
            
        except Exception as e:
            error_msg = f"OpenAI processing failed: {str(e)}"
            log_error(error_msg, job_id)
            raise Exception(error_msg)
    
    def extract_naming_info(self, transcript: str, original_filename: str = "", job_id: Optional[int] = None, duration_minutes: Optional[int] = None, *, prompt_overrides: Optional[Dict[str, Any]] = None, extra_instructions: str = "", validation_overrides: Optional[Dict[str, Any]] = None, validation_extra: str = "") -> Dict[str, Any]:
        """
        Extract naming information from transcript for intelligent file naming using two-step validation
        
        Args:
            transcript: The transcript text to analyze
            original_filename: Original filename for context
            job_id: Optional job ID for logging
            
        Returns:
            Dictionary with participants, topic, and meeting_type
        """
        try:
            log_info("Step 1: Extracting naming information from transcript", job_id)
            
            # Step 1: Extract initial naming info
            naming_info = self._extract_initial_naming_info(
                transcript,
                original_filename,
                job_id,
                duration_minutes,
                prompt_overrides=prompt_overrides,
                extra_instructions=extra_instructions
            )
            
            # Step 2: Validate and correct the proposed filename
            validated_info = self._validate_filename(
                naming_info,
                transcript,
                original_filename,
                job_id,
                prompt_overrides=validation_overrides or prompt_overrides,
                extra_instructions=validation_extra
            )
            
            return validated_info
            
        except Exception as e:
            log_error(f"Naming extraction failed: {e}", job_id)
            return self._get_default_naming_info()
    
    def _extract_initial_naming_info(self, transcript: str, original_filename: str, job_id: Optional[int] = None, duration_minutes: Optional[int] = None, *, prompt_overrides: Optional[Dict[str, Any]] = None, extra_instructions: str = "") -> Dict[str, Any]:
        """Step 1: Extract complete filename from AI"""
        try:
            duration_str = str(duration_minutes) if duration_minutes else 'Unknown'
            base_template = read_prompt_file('naming', self.config)
            tsummary = build_transcript_summary(transcript)
            placeholders = {
                'transcript': transcript,
                'transcript_summary': tsummary,
                'original_filename': original_filename,
                'duration_minutes': duration_str,
            }
            nmode = (prompt_overrides or {}).get('prompts', {}).get('naming_mode', 'append')
            naming_prompt = combine_prompt(
                base_template=base_template,
                folder_body=extra_instructions or '',
                placeholders=placeholders,
                mode=nmode,
                section_heading='Folder Instructions',
            )
            
            if not naming_prompt.strip():
                log_warning("Naming extraction prompt not configured, using default", job_id)
                naming_prompt = self._get_default_naming_prompt().format(
                    transcript=transcript,
                    original_filename=original_filename
                )
            
            # Process with retry logic - no longer expecting JSON
            model, temperature, max_tokens = resolve_openai_params(config=self.config, overrides=prompt_overrides)
            response = self._process_with_retry(naming_prompt, job_id, expect_json=False, model=model, temperature=temperature, max_tokens=max_tokens)
            
            # Clean up the response (remove any extra whitespace/newlines)
            complete_filename = response.strip()
            
            if complete_filename:
                log_info(f"Step 1 - AI filename response: '{complete_filename}'", job_id)
                
                # Return the complete filename in a format the file namer expects
                return {
                    'complete_filename': complete_filename,
                    'participants': ['AI Generated'],  # Placeholder
                    'topic': 'AI Generated',  # Placeholder
                    'meeting_type': 'AI Generated'  # Placeholder
                }
            else:
                log_warning("AI returned empty filename, using fallback", job_id)
                return self._fallback_naming_extraction(transcript, job_id)
            
        except Exception as e:
            log_error(f"Initial naming extraction failed: {e}", job_id)
            return self._get_default_naming_info()
    
    def _validate_filename(self, naming_info: Dict[str, Any], transcript: str, original_filename: str, job_id: Optional[int] = None, *, prompt_overrides: Optional[Dict[str, Any]] = None, extra_instructions: str = "") -> Dict[str, Any]:
        """Step 2: Validate and correct the AI-generated complete filename"""
        try:
            log_info("Step 2: Validating AI-generated filename", job_id)
            
            # Get the complete filename from AI
            proposed_filename = naming_info.get('complete_filename', '')
            if not proposed_filename:
                log_warning("No complete filename to validate", job_id)
                return naming_info
            
            # Create a brief transcript summary for validation context
            transcript_summary = transcript[:500] + "..." if len(transcript) > 500 else transcript
            
            # Get validation prompt
            validation_template = read_prompt_file('filename-validation', self.config)
            placeholders = {
                'proposed_filename': proposed_filename,
                'original_filename': original_filename,
                'transcript_summary': transcript_summary
            }
            vmode = (prompt_overrides or {}).get('prompts', {}).get('validation_mode', 'replace')
            validation_prompt = combine_prompt(
                base_template=validation_template,
                folder_body=extra_instructions or '',
                placeholders=placeholders,
                mode=vmode,
                section_heading='Folder Validation Rules',
            )
            
            if not validation_prompt.strip():
                log_warning("Validation prompt not configured, skipping validation", job_id)
                return naming_info
            
            # Process validation - no longer expecting JSON
            model, temperature, max_tokens = resolve_openai_params(config=self.config, overrides=prompt_overrides)
            response = self._process_with_retry(validation_prompt, job_id, expect_json=False, model=model, temperature=temperature, max_tokens=max_tokens)
            
            # Clean up the response
            validation_response = response.strip()
            log_info(f"Step 2 - Validation response: '{validation_response}'", job_id)
            
            if validation_response == "VALID":
                log_info("Filename validation passed", job_id)
                return naming_info
            else:
                # The response should be the corrected filename
                log_info(f"Filename corrected to: '{validation_response}'", job_id)
                return {
                    'complete_filename': validation_response,
                    'participants': ['AI Generated'],  # Placeholder
                    'topic': 'AI Generated',  # Placeholder
                    'meeting_type': 'AI Generated'  # Placeholder
                }
            
        except Exception as e:
            log_warning(f"Filename validation failed: {e}. Using original naming info", job_id)
            return naming_info
    
    def _build_proposed_filename(self, naming_info: Dict[str, Any]) -> str:
        """Build a proposed filename from naming info for validation"""
        parts = []
        
        # Add date (placeholder)
        parts.append("20250720")
        
        # Add meeting type
        parts.append(naming_info.get('meeting_type', 'Meeting'))
        
        # Add participants
        participants = naming_info.get('participants', [])
        if participants and participants != ['Unknown']:
            participants_str = ' and '.join(participants[:2])
            parts.append(f"with {participants_str}")
        
        # Add topic
        topic = naming_info.get('topic', '')
        if topic and topic != 'Meeting':
            parts.append(f"re {topic}")
        
        # Add duration placeholder
        parts.append("- 18min")
        
        return ' '.join(parts)
    
    def _parse_corrected_filename(self, corrected_filename: str, original_info: Dict[str, Any]) -> Dict[str, Any]:
        """Parse corrected filename back to naming components"""
        try:
            # Simple parsing to extract corrected components
            corrected_info = original_info.copy()
            
            # Extract participants (between "with" and "re")
            with_match = re.search(r'with\s+([^-]+?)\s+re', corrected_filename)
            if with_match:
                participants_str = with_match.group(1).strip()
                participants = [p.strip() for p in participants_str.split(' and ')]
                corrected_info['participants'] = participants
            
            # Extract topic (between "re" and "-")
            re_match = re.search(r're\s+([^-]+?)\s*-', corrected_filename)
            if re_match:
                topic = re_match.group(1).strip()
                corrected_info['topic'] = topic
            
            # Extract meeting type (second word)
            words = corrected_filename.split()
            if len(words) > 1:
                corrected_info['meeting_type'] = words[1]
            
            log_info(f"Parsed corrected filename: {corrected_info}", None)
            return corrected_info
            
        except Exception as e:
            log_warning(f"Failed to parse corrected filename: {e}", None)
            return original_info
    
    def _process_with_retry(self, prompt: str, job_id: Optional[int] = None, 
                           expect_json: bool = False, max_retries: int = 3, *, model: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        """Process prompt with retry logic"""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=model or self.config.get("openai.model", "gpt-4o"),
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a helpful meeting assistant that analyzes transcripts and extracts key information."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=(temperature if temperature is not None else self.config.get("openai.temperature", 0.7)),
                    # Some newer models expect max_completion_tokens instead of max_tokens
                    max_completion_tokens=(max_tokens if max_tokens is not None else self.config.get("openai.max_tokens", 2000))
                )
                
                content = response.choices[0].message.content
                
                # Validate JSON if expected
                if expect_json:
                    try:
                        json.loads(content)
                    except json.JSONDecodeError:
                        if attempt < max_retries - 1:
                            log_warning(f"Invalid JSON response on attempt {attempt + 1}, retrying", job_id)
                            continue
                        else:
                            raise ValueError("Failed to get valid JSON response")
                
                return content
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    log_warning(f"OpenAI API attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s", job_id)
                    time.sleep(wait_time)
                else:
                    raise e
    
    def _fallback_naming_extraction(self, transcript: str, job_id: Optional[int] = None) -> Dict[str, Any]:
        """Fallback naming extraction using simple text analysis"""
        log_info("Using fallback naming extraction", job_id)
        
        # Simple extraction logic
        participants = []
        topic = "Meeting"
        meeting_type = "Meeting"
        
        # Look for speaker patterns
        lines = transcript.split('\n')
        for line in lines:
            if line.strip().startswith('[Speaker'):
                # Extract speaker info if available
                if ':' in line:
                    speaker_part = line.split(':')[0]
                    if 'Speaker' in speaker_part:
                        participants.append(f"Speaker {len(participants) + 1}")
        
        # Remove duplicates and limit
        participants = list(set(participants))[:3]
        
        # Look for common meeting keywords
        transcript_lower = transcript.lower()
        if 'call' in transcript_lower:
            meeting_type = "Call"
        elif 'interview' in transcript_lower:
            meeting_type = "Interview"
        elif 'presentation' in transcript_lower:
            meeting_type = "Presentation"
        
        # Try to extract topic from common phrases
        topic_keywords = ['regarding', 'about', 'discuss', 'meeting about', 'call about']
        for keyword in topic_keywords:
            if keyword in transcript_lower:
                # Simple topic extraction (this could be improved)
                topic = "Discussion"
                break
        
        return {
            'participants': participants if participants else ["Unknown"],
            'topic': topic,
            'meeting_type': meeting_type
        }
    
    def _get_default_naming_prompt(self) -> str:
        """Get default naming extraction prompt"""
        return """Analyze this meeting transcript and extract key information for file naming.

Extract:
1. All participant names (people speaking or mentioned as attendees)
2. Main meeting topic or purpose (be concise, 2-4 words)
3. Meeting type (Meeting/Call/Interview/Presentation/Discussion)

Rules:
- For participants: Use full names when available, otherwise first names
- For topic: Focus on the main subject (e.g., "Budget Review", "Contract Negotiation")
- Be concise but descriptive

Return as JSON only:
{{
  "participants": ["Name1", "Name2"],
  "topic": "Main Topic",
  "meeting_type": "Meeting"
}}

Transcript: {transcript}"""
    
    def _get_default_value(self, field: str) -> Any:
        """Get default value for missing fields"""
        defaults = {
            'participants': ["Unknown"],
            'topic': "Meeting",
            'meeting_type': "Meeting"
        }
        return defaults.get(field, "Unknown")
    
    def _post_process_naming_info(self, naming_info: Dict[str, Any], job_id: Optional[int] = None) -> Dict[str, Any]:
        """Post-process naming info to remove any remaining duplicates"""
        try:
            participants = naming_info.get('participants', [])
            if not participants:
                return naming_info
            
            # Remove duplicates using smart matching
            cleaned_participants = []
            
            for participant in participants:
                is_duplicate = False
                participant_words = set(participant.lower().split())
                
                for existing in cleaned_participants:
                    existing_words = set(existing.lower().split())
                    
                    # Check if one is a subset of the other (e.g., "Fox" is subset of "Michael Fox")
                    if participant_words.issubset(existing_words) or existing_words.issubset(participant_words):
                        # Keep the longer/more complete name
                        if len(participant) > len(existing):
                            # Replace existing with longer name
                            cleaned_participants[cleaned_participants.index(existing)] = participant
                        is_duplicate = True
                        log_info(f"Post-processing: Removed duplicate participant '{participant}' (matches '{existing}')", job_id)
                        break
                
                if not is_duplicate:
                    cleaned_participants.append(participant)
            
            # Update the naming info
            naming_info['participants'] = cleaned_participants
            
            if len(cleaned_participants) != len(participants):
                log_info(f"Post-processing: Cleaned participants from {participants} to {cleaned_participants}", job_id)
            
            return naming_info
            
        except Exception as e:
            log_warning(f"Error in post-processing naming info: {e}", job_id)
            return naming_info
    
    def _get_default_naming_info(self) -> Dict[str, Any]:
        """Get default naming info when extraction fails"""
        return {
            'participants': ["Unknown"],
            'topic': "Meeting",
            'meeting_type': "Meeting"
        }
    
    def test_connection(self) -> bool:
        """Test OpenAI API connection"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.get("openai.model", "gpt-4o"),
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return bool(response.choices[0].message.content)
        except Exception as e:
            log_error(f"OpenAI connection test failed: {e}")
            return False
