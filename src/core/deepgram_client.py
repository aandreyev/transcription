import os
import time
from typing import Dict, Any, Optional
from deepgram import DeepgramClient, DeepgramClientOptions, FileSource
from src.utils import ConfigManager, log_info, log_error, log_warning

class DeepgramTranscriber:
    def __init__(self):
        self.config = ConfigManager()
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        
        if not self.api_key or self.api_key == "your_deepgram_key_here":
            raise ValueError("Deepgram API key not configured. Please set DEEPGRAM_API_KEY in your .env file")
        
        # Configure Deepgram client
        config_options = DeepgramClientOptions(
            verbose=1 if self.config.get("app.debug", False) else 0
        )
        self.client = DeepgramClient(self.api_key, config_options)
    
    def transcribe_file(self, file_path: str, job_id: Optional[int] = None) -> str:
        """
        Transcribe audio file using Deepgram with speaker diarization
        
        Args:
            file_path: Path to the audio file
            job_id: Optional job ID for logging
            
        Returns:
            Formatted transcript with speaker labels
        """
        try:
            log_info(f"Starting Deepgram transcription for: {file_path}", job_id)
            
            # Read audio file
            with open(file_path, "rb") as audio_file:
                buffer_data = audio_file.read()
            
            payload: FileSource = {
                "buffer": buffer_data,
            }
            
            # Configure transcription options
            options = {
                "model": self.config.get("deepgram.model", "nova-2"),
                "punctuate": self.config.get("deepgram.features.punctuate", True),
                "paragraphs": self.config.get("deepgram.features.paragraphs", True),
                "diarize": self.config.get("deepgram.features.speaker_diarize", True),
                "smart_format": self.config.get("deepgram.features.smart_format", True),
                "utterances": self.config.get("deepgram.features.utt_split", True),
                "numerals": self.config.get("deepgram.features.numerals", True),
            }
            
            log_info(f"Sending file to Deepgram with options: {options}", job_id)
            
            # Make API call with retry logic
            response = self._transcribe_with_retry(payload, options, job_id)
            
            # Process response to get formatted transcript
            transcript = self._format_transcript(response, job_id)
            
            log_info(f"Deepgram transcription completed. Length: {len(transcript)} characters", job_id)
            return transcript
            
        except Exception as e:
            error_msg = f"Deepgram transcription failed: {str(e)}"
            log_error(error_msg, job_id)
            raise Exception(error_msg)
    
    def _transcribe_with_retry(self, payload: FileSource, options: Dict[str, Any], 
                              job_id: Optional[int] = None, max_retries: int = 3) -> Any:
        """Transcribe with retry logic"""
        for attempt in range(max_retries):
            try:
                response = self.client.listen.prerecorded.v("1").transcribe_file(payload, options)
                return response
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    log_warning(f"Deepgram API attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s", job_id)
                    time.sleep(wait_time)
                else:
                    raise e
    
    def _format_transcript(self, response: Any, job_id: Optional[int] = None) -> str:
        """Format Deepgram response into readable transcript with speaker labels"""
        try:
            full_transcript = []
            
            if not response.results or not response.results.channels:
                log_warning("No transcription results found in Deepgram response", job_id)
                return ""
            
            for channel in response.results.channels:
                for alternative in channel.alternatives:
                    if alternative.paragraphs and alternative.paragraphs.paragraphs:
                        # Use paragraph-based formatting (preferred for diarization)
                        for paragraph in alternative.paragraphs.paragraphs:
                            speaker = paragraph.speaker
                            # Extract text from words in the paragraph
                            if hasattr(paragraph, 'words') and paragraph.words:
                                transcript_text = " ".join([word.word for word in paragraph.words])
                            else:
                                # Fallback to sentences if words not available
                                transcript_text = " ".join([sentence.text for sentence in paragraph.sentences])
                            
                            if transcript_text.strip():
                                full_transcript.append(f"[Speaker {speaker}]: {transcript_text}")
                    
                    elif alternative.words:
                        # Fallback: Use word-level speaker information
                        current_speaker = -1
                        current_utterance = []
                        
                        for word_data in alternative.words:
                            if hasattr(word_data, 'speaker') and word_data.speaker != current_speaker:
                                # Speaker changed, save previous utterance
                                if current_utterance and current_speaker != -1:
                                    full_transcript.append(f"[Speaker {current_speaker}]: {' '.join(current_utterance)}")
                                
                                current_speaker = word_data.speaker
                                current_utterance = [word_data.word]
                            else:
                                current_utterance.append(word_data.word)
                        
                        # Add final utterance
                        if current_utterance and current_speaker != -1:
                            full_transcript.append(f"[Speaker {current_speaker}]: {' '.join(current_utterance)}")
                    
                    else:
                        # Last resort: Use transcript without speaker labels
                        log_warning("No speaker diarization data found, using basic transcript", job_id)
                        if hasattr(alternative, 'transcript'):
                            full_transcript.append(alternative.transcript)
            
            result = "\n\n".join(full_transcript)
            
            if not result.strip():
                log_warning("Empty transcript generated from Deepgram response", job_id)
                return "No speech detected in audio file."
            
            return result
            
        except Exception as e:
            log_error(f"Error formatting Deepgram transcript: {e}", job_id)
            # Return raw transcript as fallback
            try:
                if response.results and response.results.channels:
                    for channel in response.results.channels:
                        for alternative in channel.alternatives:
                            if hasattr(alternative, 'transcript'):
                                return alternative.transcript
                return "Error processing transcript"
            except:
                return "Error processing transcript"
    
    def test_connection(self) -> bool:
        """Test Deepgram API connection"""
        try:
            # Create a minimal test payload (empty buffer)
            payload: FileSource = {"buffer": b""}
            options = {"model": "nova-2"}
            
            # This will fail but should give us a proper API response indicating connection works
            try:
                self.client.listen.prerecorded.v("1").transcribe_file(payload, options)
            except Exception as e:
                # If we get a specific error about the audio format, the API is working
                if "audio" in str(e).lower() or "format" in str(e).lower():
                    return True
                raise e
            
            return True
            
        except Exception as e:
            log_error(f"Deepgram connection test failed: {e}")
            return False
