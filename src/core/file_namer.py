import os
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from mutagen import File as MutagenFile
from src.utils import ConfigManager, log_info, log_error, log_warning

class IntelligentFileNamer:
    def __init__(self):
        self.config = ConfigManager()
    
    def generate_name(self, original_file: str, transcript: str, 
                     ai_info: Dict[str, Any], job_id: Optional[int] = None) -> Tuple[str, float]:
        """
        Generate intelligent filename using AI-generated complete filename string
        
        Args:
            original_file: Path to original audio file
            transcript: Transcript content
            ai_info: AI-extracted information containing complete filename
            job_id: Optional job ID for logging
            
        Returns:
            Tuple of (suggested_filename, confidence_score)
        """
        try:
            log_info(f"Using AI-generated filename for: {original_file}", job_id)
            
            # Use AI-generated complete filename directly
            if ai_info.get('complete_filename'):
                filename = self._clean_filename(ai_info['complete_filename'])
                log_info(f"AI-generated filename: '{filename}'", job_id)
                return filename, 0.9
            
            # Fallback only if AI completely failed
            log_warning("AI did not provide complete filename, using fallback", job_id)
            fallback = self._generate_fallback_filename(original_file)
            return fallback, 0.1
            
        except Exception as e:
            log_error(f"Error using AI filename: {e}", job_id)
            fallback = self._generate_fallback_filename(original_file)
            return fallback, 0.1
    
    def _extract_date(self, file_path: str, job_id: Optional[int] = None) -> Dict[str, Any]:
        """Extract date from file metadata and filename"""
        date_info = {
            'date': None,
            'source': None,
            'confidence': 0.0
        }
        
        try:
            # Try to extract from filename first
            filename = os.path.basename(file_path)
            date_patterns = [
                r'(\d{4}[-_]\d{2}[-_]\d{2})',  # YYYY-MM-DD or YYYY_MM_DD
                r'(\d{2}[-_]\d{2}[-_]\d{4})',  # DD-MM-YYYY or DD_MM_YYYY
                r'(\d{8})',                     # YYYYMMDD
                r'(\d{2}\d{2}\d{4})',          # DDMMYYYY
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, filename)
                if match:
                    date_str = match.group(1)
                    parsed_date = self._parse_date_string(date_str)
                    if parsed_date:
                        date_info['date'] = parsed_date
                        date_info['source'] = 'filename'
                        date_info['confidence'] = 0.9
                        log_info(f"Extracted date from filename: {parsed_date}", job_id)
                        return date_info
            
            # Try file metadata
            stat = os.stat(file_path)
            creation_time = datetime.fromtimestamp(stat.st_ctime)
            modification_time = datetime.fromtimestamp(stat.st_mtime)
            
            # Use the earlier of creation or modification time
            file_date = min(creation_time, modification_time)
            date_info['date'] = file_date.strftime('%Y%m%d')
            date_info['source'] = 'file_metadata'
            date_info['confidence'] = 0.7
            
            log_info(f"Using file metadata date: {date_info['date']}", job_id)
            
        except Exception as e:
            log_warning(f"Error extracting date: {e}", job_id)
            # Fallback to current date
            date_info['date'] = datetime.now().strftime('%Y%m%d')
            date_info['source'] = 'current_date'
            date_info['confidence'] = 0.3
        
        return date_info
    
    def _parse_date_string(self, date_str: str) -> Optional[str]:
        """Parse various date string formats to YYYYMMDD"""
        try:
            # Remove separators
            clean_date = re.sub(r'[-_]', '', date_str)
            
            if len(clean_date) == 8:
                # YYYYMMDD
                if clean_date[:4].isdigit() and int(clean_date[:4]) > 1900:
                    return clean_date
                # DDMMYYYY
                elif clean_date[4:].isdigit() and int(clean_date[4:]) > 1900:
                    return clean_date[4:] + clean_date[2:4] + clean_date[:2]
            
            # Try parsing with separators
            for fmt in ['%Y-%m-%d', '%Y_%m_%d', '%d-%m-%Y', '%d_%m_%Y']:
                try:
                    parsed = datetime.strptime(date_str, fmt)
                    return parsed.strftime('%Y%m%d')
                except ValueError:
                    continue
                    
        except Exception:
            pass
        
        return None
    
    def _parse_filename(self, file_path: str, job_id: Optional[int] = None) -> Dict[str, Any]:
        """Parse existing filename for useful information"""
        filename_info = {
            'participants': [],
            'topic_keywords': [],
            'meeting_type': None,
            'matter_number': None,
            'confidence': 0.0
        }
        
        try:
            filename = os.path.splitext(os.path.basename(file_path))[0].lower()
            
            # Look for meeting type keywords and abbreviations
            meeting_types = {
                'Call': ['call', 'phone', 'zoom', 'teams', 'ta', 'telephone attendance'],
                'Meeting': ['meeting', 'meet', 'mtg', 'catch up', 'catchup'],
                'Interview': ['interview'],
                'Presentation': ['presentation', 'present', 'demo']
            }
            
            for meeting_type, keywords in meeting_types.items():
                if any(keyword in filename for keyword in keywords):
                    filename_info['meeting_type'] = meeting_type
                    filename_info['confidence'] += 0.2
                    log_info(f"Detected meeting type from filename: {meeting_type} (from keyword: {[k for k in keywords if k in filename]})", job_id)
                    break
            
            # Enhanced name extraction - prioritize full names and handle legal formats
            name_patterns = [
                # Pattern: "TA [Full Name]" (highest priority - legal format)
                r'(?:^|[_\s])(?:ta|telephone\s+attendance)[_\s]+([A-Z][a-z]+(?:[_\s]+[A-Z][a-z]+)+)',
                # Pattern: "MTG [Full Name]" 
                r'(?:^|[_\s])(?:mtg|meeting)[_\s]+([A-Z][a-z]+(?:[_\s]+[A-Z][a-z]+)+)',
                # Pattern: "with [Full Name]" or "w [Full Name]"
                r'(?:with|w)[_\s]+([A-Z][a-z]+(?:[_\s]+[A-Z][a-z]+)+)',
                # Pattern: Full names before "re" (e.g., "John Smith re contract")
                r'([A-Z][a-z]+[_\s]+[A-Z][a-z]+)(?:[_\s]+re[_\s])',
                # Pattern: Full names after date but before keywords
                r'(?:\d{8}|\d{4}[-_]\d{2}[-_]\d{2})[_\s]+(?:ta|mtg|meeting|call)?[_\s]*([A-Z][a-z]+[_\s]+[A-Z][a-z]+)',
                # Pattern: Standalone full names (First Last format)
                r'\b([A-Z][a-z]+[_\s]+[A-Z][a-z]+)\b(?![_\s]*(?:meeting|call|interview|discussion|about|re|regarding))',
                # Pattern: Single names after TA/MTG (fallback)
                r'(?:ta|mtg)[_\s]+([A-Z][a-z]{2,15})\b(?![_\s]*(?:meeting|call|interview|discussion|about|re|regarding))',
            ]
            
            # Common words to exclude from name detection
            exclude_words = {
                'meeting', 'call', 'interview', 'discussion', 'about', 'regarding', 
                'admin', 'estate', 'contract', 'review', 'notes', 'client', 'matter',
                'phone', 'zoom', 'teams', 'conference', 'legal', 'law', 'firm',
                'ta', 'mtg', 'telephone', 'attendance', 'question', 'issue', 'land',
                'gst', 'tax', 'advice', 'consultation', 'update', 'follow', 'up'
            }
            
            # Process patterns in order of priority
            for i, pattern in enumerate(name_patterns):
                matches = re.findall(pattern, filename, re.IGNORECASE)
                for match in matches:
                    name = re.sub(r'[_\s]+', ' ', match).strip().title()
                    
                    # Validate name
                    if self._is_valid_name(name, exclude_words):
                        # Check if this name is already represented (avoid duplicates like "Jim Hunwick" and "Hunwick")
                        is_duplicate = False
                        for existing_name in filename_info['participants']:
                            if self._are_same_person(existing_name, name):
                                is_duplicate = True
                                log_info(f"Skipping duplicate name from filename: '{name}' (matches existing '{existing_name}')", job_id)
                                break
                        
                        if not is_duplicate:
                            filename_info['participants'].append(name)
                            # Higher confidence for full names and legal format patterns
                            confidence_boost = 0.5 if i < 2 else 0.4 if ' ' in name else 0.3
                            filename_info['confidence'] += confidence_boost
                            log_info(f"Extracted name from filename (pattern {i+1}): {name}", job_id)
            
            # Extract topic keywords
            topic_indicators = ['re', 'about', 'regarding', 'discussion', 'review']
            for indicator in topic_indicators:
                pattern = f'{indicator}[_\\s]+([a-zA-Z]+(?:[_\\s]+[a-zA-Z]+)*)'
                matches = re.findall(pattern, filename)
                for match in matches:
                    topic = re.sub(r'[_\s]+', ' ', match).strip().title()
                    if len(topic) > 2:
                        filename_info['topic_keywords'].append(topic)
                        filename_info['confidence'] += 0.2
            
            # Extract matter number
            matter_number = self._extract_matter_number(os.path.basename(file_path), job_id)
            if matter_number:
                filename_info['matter_number'] = matter_number
                filename_info['confidence'] += 0.3
            
            log_info(f"Parsed filename info: {filename_info}", job_id)
            
        except Exception as e:
            log_warning(f"Error parsing filename: {e}", job_id)
        
        return filename_info
    
    def _extract_metadata(self, file_path: str, job_id: Optional[int] = None) -> Dict[str, Any]:
        """Extract metadata from audio file"""
        metadata_info = {
            'duration': None,
            'title': None,
            'artist': None,
            'confidence': 0.0
        }
        
        try:
            audio_file = MutagenFile(file_path)
            if audio_file is not None:
                # Get duration
                if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'length'):
                    duration_seconds = int(audio_file.info.length)
                    metadata_info['duration'] = duration_seconds
                    metadata_info['confidence'] += 0.1
                
                # Get title and artist if available
                if hasattr(audio_file, 'tags') and audio_file.tags:
                    title = audio_file.tags.get('TIT2') or audio_file.tags.get('TITLE')
                    if title:
                        metadata_info['title'] = str(title[0]) if isinstance(title, list) else str(title)
                        metadata_info['confidence'] += 0.2
                    
                    artist = audio_file.tags.get('TPE1') or audio_file.tags.get('ARTIST')
                    if artist:
                        metadata_info['artist'] = str(artist[0]) if isinstance(artist, list) else str(artist)
                        metadata_info['confidence'] += 0.2
                
                log_info(f"Extracted metadata: duration={metadata_info['duration']}s", job_id)
            
        except Exception as e:
            log_warning(f"Error extracting metadata: {e}", job_id)
        
        return metadata_info
    
    def _extract_matter_number(self, filename: str, job_id: Optional[int] = None) -> Optional[str]:
        """
        Extract 5-digit matter number from filename in various formats and return in uniform square bracket format:
        - [52366] (square brackets) -> [52366]
        - _52366_ (underscores on both sides) -> [52366]
        - _52366 (underscore on left side, typically at end of filename) -> [52366]
        """
        try:
            # Pattern for 5-digit numbers with square brackets: [12345]
            bracket_pattern = r'\[(\d{5})\]'
            match = re.search(bracket_pattern, filename)
            if match:
                matter_num = match.group(1)
                log_info(f"Found matter number in brackets: {matter_num}", job_id)
                return f"[{matter_num}]"
            
            # Pattern for 5-digit numbers with underscores on both sides: _12345_
            underscore_both_pattern = r'_(\d{5})_'
            match = re.search(underscore_both_pattern, filename)
            if match:
                matter_num = match.group(1)
                log_info(f"Found matter number with underscores: {matter_num} -> converting to [{matter_num}]", job_id)
                return f"[{matter_num}]"
            
            # Pattern for 5-digit numbers with underscore on left: _12345 (typically at end)
            underscore_left_pattern = r'_(\d{5})(?:\.|$)'
            match = re.search(underscore_left_pattern, filename)
            if match:
                matter_num = match.group(1)
                log_info(f"Found matter number with left underscore: {matter_num} -> converting to [{matter_num}]", job_id)
                return f"[{matter_num}]"
            
            # No matter number found
            return None
            
        except Exception as e:
            log_warning(f"Error extracting matter number: {e}", job_id)
            return None
    
    
    def _clean_filename(self, filename: str) -> str:
        """Clean filename to be filesystem-safe and remove duplications"""
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = re.sub(r'\s+', ' ', filename)  # Multiple spaces to single
        filename = filename.strip()
        
        # Fix common duplication patterns
        filename = self._fix_duplications(filename)
        
        # Limit length
        if len(filename) > 200:
            filename = filename[:200].rsplit(' ', 1)[0]  # Cut at word boundary
        
        return filename
    
    def _fix_duplications(self, filename: str) -> str:
        """Fix common duplication patterns in filename"""
        # Fix "Re re" patterns
        filename = re.sub(r'\bre\s+re\b', 're', filename, flags=re.IGNORECASE)
        
        # Fix "With with" patterns  
        filename = re.sub(r'\bwith\s+with\b', 'with', filename, flags=re.IGNORECASE)
        
        # Fix "And and" patterns
        filename = re.sub(r'\band\s+and\b', 'and', filename, flags=re.IGNORECASE)
        
        # Fix repeated words in general (but be careful with names)
        words = filename.split()
        cleaned_words = []
        
        for i, word in enumerate(words):
            # Don't deduplicate if it might be part of a name
            if i > 0 and word.lower() == words[i-1].lower():
                # Check if this might be a name duplication
                if (word.lower() not in ['re', 'with', 'and', 'the', 'a', 'an', 'of', 'in', 'on', 'at'] and
                    len(word) > 2 and word[0].isupper()):
                    # This looks like a name, skip the duplicate
                    continue
                elif word.lower() in ['re', 'with', 'and']:
                    # These are definitely duplicates to remove
                    continue
            
            cleaned_words.append(word)
        
        return ' '.join(cleaned_words)
    
    def _deduplicate_participants(self, filename_participants: list, ai_participants: list, job_id: Optional[int] = None) -> list:
        """Intelligently deduplicate participants from different sources"""
        result = []
        
        # Start with filename participants (highest priority)
        for participant in filename_participants:
            if participant not in result:
                result.append(participant)
        
        # Add AI participants, but check for duplicates intelligently
        for ai_participant in ai_participants:
            is_duplicate = False
            
            # Check if this AI participant is already represented
            for existing in result:
                if self._are_same_person(existing, ai_participant):
                    is_duplicate = True
                    log_info(f"Detected duplicate participant: '{ai_participant}' matches existing '{existing}'", job_id)
                    break
            
            # Add if not duplicate and we have space
            if not is_duplicate and len(result) < 3:
                result.append(ai_participant)
        
        log_info(f"Deduplicated participants: {result}", job_id)
        return result
    
    def _are_same_person(self, name1: str, name2: str) -> bool:
        """Check if two names refer to the same person"""
        # Normalize names for comparison
        norm1 = name1.lower().strip()
        norm2 = name2.lower().strip()
        
        # Exact match
        if norm1 == norm2:
            return True
        
        # Check if one name is contained in the other (e.g., "Rob" vs "Rob Veitch")
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        # If one set is a subset of the other, they're likely the same person
        if words1.issubset(words2) or words2.issubset(words1):
            return True
        
        # Check for common surname patterns (e.g., "Rob Veitch" and "Veitch")
        if len(words1) > 1 and len(words2) == 1:
            # Check if single name matches any word in full name
            if words2.pop() in words1:
                return True
        elif len(words2) > 1 and len(words1) == 1:
            # Check if single name matches any word in full name
            if words1.pop() in words2:
                return True
        
        return False
    
    def _is_topic_actually_name(self, topic: str, participants: list) -> bool:
        """Check if the AI topic is actually a person's name"""
        if not topic:
            return False
        
        # Check if topic matches any participant
        for participant in participants:
            if self._are_same_person(topic, participant):
                return True
        
        # Check if topic looks like a person's name (First Last pattern)
        words = topic.split()
        if len(words) == 2:
            # Two words, both capitalized, could be a name
            if all(word[0].isupper() and word[1:].islower() for word in words if word):
                # Additional check: common name patterns
                if not any(legal_word in topic.lower() for legal_word in [
                    'agreement', 'contract', 'estate', 'tax', 'legal', 'advice',
                    'planning', 'review', 'matter', 'issue', 'question', 'consultation'
                ]):
                    return True
        
        return False
    
    def _is_valid_name(self, name: str, exclude_words: set) -> bool:
        """Validate if extracted text is a valid name"""
        # Check basic criteria
        if len(name) < 2 or len(name) > 50:
            return False
        
        # Check if it's in exclude words
        if name.lower() in exclude_words:
            return False
        
        # Check if any word in the name is in exclude words
        name_words = name.lower().split()
        if any(word in exclude_words for word in name_words):
            return False
        
        # Must contain at least one letter
        if not re.search(r'[a-zA-Z]', name):
            return False
        
        # Should not be all numbers
        if name.replace(' ', '').isdigit():
            return False
        
        # Should not contain special characters (except spaces and hyphens)
        if re.search(r'[^a-zA-Z\s\-]', name):
            return False
        
        return True
    
    def _generate_fallback_filename(self, original_file: str) -> str:
        """Generate fallback filename when all else fails"""
        if original_file:
            # Just clean up the original filename, don't add dates or "Processed"
            base_name = os.path.splitext(os.path.basename(original_file))[0]
            return self._clean_filename(base_name)
        else:
            return "Audio Processing"
