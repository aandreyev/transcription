import os
import shutil
from datetime import datetime
from typing import Optional
from src.core import Database, DeepgramTranscriber, OpenAIProcessor, IntelligentFileNamer
from src.utils import (
    ConfigManager,
    log_info,
    log_error,
    log_warning,
    resolve_folder_prompt,
)

class AudioProcessor:
    def __init__(self):
        self.config = ConfigManager()
        self.db = Database()
        self.deepgram = DeepgramTranscriber()
        self.openai = OpenAIProcessor()
        self.file_namer = IntelligentFileNamer()
    
    def process_file(self, file_path: str) -> bool:
        """
        Process a single audio file through the complete pipeline
        
        Args:
            file_path: Path to the audio file to process
            
        Returns:
            True if processing succeeded, False otherwise
        """
        job_id = None
        try:
            filename = os.path.basename(file_path)
            log_info(f"Starting processing pipeline for: {filename}")
            
            # Create job record
            job_id = self.db.create_job(filename, file_path)
            self.db.update_job_status(job_id, 'processing')
            
            # Validate file
            if not self._validate_file(file_path, job_id):
                self.db.update_job_status(job_id, 'failed', 'File validation failed')
                return False
            
            # Resolve folder-specific prompts independently
            sum_overrides, sum_body, sum_path = resolve_folder_prompt(file_path, 'summary', self.config)
            name_overrides, name_body, name_path = resolve_folder_prompt(file_path, 'naming', self.config)
            val_overrides, val_body, val_path = resolve_folder_prompt(file_path, 'filename-validation', self.config)
            if sum_path:
                log_info(f"Using folder summary prompt: {sum_path} (len={len(sum_body)})", job_id)
            if name_path:
                log_info(f"Using folder naming prompt: {name_path} (len={len(name_body)})", job_id)
            if val_path:
                log_info(f"Using folder validation prompt: {val_path} (len={len(val_body)})", job_id)

            # Step 1: Transcribe with Deepgram
            log_info("Step 1: Transcribing audio with Deepgram", job_id)
            transcript = self.deepgram.transcribe_file(file_path, job_id)
            
            if not transcript or transcript.strip() == "":
                raise Exception("Empty transcript received from Deepgram")
            
            self.db.update_job_transcript(job_id, len(transcript))
            
            # Step 2: Extract duration first
            log_info("Step 2: Extracting duration", job_id)
            metadata_info = self.file_namer._extract_metadata(file_path, job_id)
            duration_minutes = None
            if metadata_info.get('duration'):
                duration_minutes = max(1, round(metadata_info['duration'] / 60))
                log_info(f"Extracted duration: {duration_minutes} minutes", job_id)
            
            # Step 3: Process with OpenAI (now with duration)
            log_info("Step 3: Processing transcript with OpenAI", job_id)
            processed_content = self.openai.process_transcript(
                transcript,
                filename,
                job_id,
                duration_minutes,
                prompt_overrides=sum_overrides,
                extra_instructions=sum_body
            )
            
            # Step 4: Extract naming information with duration
            log_info("Step 4: Extracting naming information", job_id)
            naming_info = self.openai.extract_naming_info(
                transcript,
                filename,
                job_id,
                duration_minutes,
                prompt_overrides=name_overrides,
                extra_instructions=name_body,
                validation_overrides=val_overrides,
                validation_extra=val_body,
            )
            
            # Step 5: Generate intelligent filename
            log_info("Step 5: Generating intelligent filename", job_id)
            
            suggested_filename, confidence = self.file_namer.generate_name(
                file_path, transcript, naming_info, job_id
            )
            
            # Step 5: Save output
            log_info("Step 5: Saving processed output", job_id)
            output_file = self._save_output(
                processed_content, transcript, suggested_filename, job_id
            )
            
            # Update job with naming and output information
            self.db.update_job_naming(job_id, suggested_filename, suggested_filename, confidence)
            self.db.update_job_output(job_id, output_file)
            
            # Step 6: Move processed file
            log_info("Step 6: Moving processed file", job_id)
            self._move_processed_file(file_path, job_id)
            
            # Mark job as completed
            self.db.update_job_status(job_id, 'completed')
            log_info(f"Successfully completed processing for: {filename}", job_id)
            
            return True
            
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            log_error(error_msg, job_id)
            
            if job_id:
                self.db.update_job_status(job_id, 'failed', error_msg)
            
            # Move file to error folder
            try:
                self._move_error_file(file_path, job_id)
            except Exception as move_error:
                log_error(f"Failed to move error file: {move_error}", job_id)
            
            return False
    
    def _validate_file(self, file_path: str, job_id: Optional[int] = None) -> bool:
        """Validate audio file before processing"""
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                log_error(f"File does not exist: {file_path}", job_id)
                return False
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                log_error(f"File is empty: {file_path}", job_id)
                return False
            
            # Check file extension
            supported_formats = self.config.get("processing.supported_formats", [])
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext not in supported_formats:
                log_error(f"Unsupported file format: {file_ext}", job_id)
                return False
            
            # Check if file is still being written (basic check)
            initial_size = file_size
            import time
            time.sleep(1)
            current_size = os.path.getsize(file_path)
            
            if current_size != initial_size:
                log_warning(f"File appears to be still being written: {file_path}", job_id)
                return False
            
            log_info(f"File validation passed: {file_path} ({file_size} bytes)", job_id)
            return True
            
        except Exception as e:
            log_error(f"File validation error: {e}", job_id)
            return False
    
    def _save_output(self, processed_content: str, transcript: str, 
                    suggested_filename: str, job_id: Optional[int] = None) -> str:
        """Save processed output to files"""
        try:
            output_folder = self.config.get("processing.output_folder")
            if not output_folder:
                raise Exception("Output folder not configured")
            
            os.makedirs(output_folder, exist_ok=True)
            
            # Generate timestamp for uniqueness
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save main processed content
            main_filename = f"{suggested_filename}.md"
            main_file_path = os.path.join(output_folder, main_filename)
            
            # Create comprehensive output
            full_content = self._create_full_output(processed_content, transcript, suggested_filename)
            
            with open(main_file_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            log_info(f"Saved processed output to: {main_file_path}", job_id)
            return main_file_path
            
        except Exception as e:
            log_error(f"Error saving output: {e}", job_id)
            raise
    
    def _create_full_output(self, processed_content: str, transcript: str, filename: str) -> str:
        """Create comprehensive output document"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # The processed_content already contains the full legal summary format
        # We just need to add the full transcript at the end
        content = f"""{processed_content}

---

## Full Transcript

{transcript}

---

*This document was automatically generated from audio transcription and AI analysis using Audio Processor v{self.config.get('app.version', '1.0.0')}*
"""
        return content
    
    def _move_processed_file(self, file_path: str, job_id: Optional[int] = None):
        """Move successfully processed file to processed folder"""
        try:
            processed_folder = self.config.get("processing.processed_folder")
            if not processed_folder:
                log_warning("Processed folder not configured, keeping file in place", job_id)
                return
            
            os.makedirs(processed_folder, exist_ok=True)
            
            filename = os.path.basename(file_path)
            destination = os.path.join(processed_folder, filename)
            
            # Handle duplicate filenames
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(destination):
                new_filename = f"{base_name}_{counter}{ext}"
                destination = os.path.join(processed_folder, new_filename)
                counter += 1
            
            shutil.move(file_path, destination)
            log_info(f"Moved processed file to: {destination}", job_id)
            
        except Exception as e:
            log_error(f"Error moving processed file: {e}", job_id)
            raise
    
    def _move_error_file(self, file_path: str, job_id: Optional[int] = None):
        """Move failed file to error folder"""
        try:
            if not os.path.exists(file_path):
                return  # File already moved or doesn't exist
            
            error_folder = self.config.get("processing.error_folder")
            if not error_folder:
                log_warning("Error folder not configured, keeping file in place", job_id)
                return
            
            os.makedirs(error_folder, exist_ok=True)
            
            filename = os.path.basename(file_path)
            destination = os.path.join(error_folder, filename)
            
            # Handle duplicate filenames
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(destination):
                new_filename = f"{base_name}_{counter}{ext}"
                destination = os.path.join(error_folder, new_filename)
                counter += 1
            
            shutil.move(file_path, destination)
            log_info(f"Moved error file to: {destination}", job_id)
            
        except Exception as e:
            log_error(f"Error moving error file: {e}", job_id)
    
    def test_connections(self) -> dict:
        """Test connections to external services"""
        results = {
            'deepgram': False,
            'openai': False,
            'database': False
        }
        
        try:
            # Test Deepgram
            results['deepgram'] = self.deepgram.test_connection()
        except Exception as e:
            log_error(f"Deepgram connection test failed: {e}")
        
        try:
            # Test OpenAI
            results['openai'] = self.openai.test_connection()
        except Exception as e:
            log_error(f"OpenAI connection test failed: {e}")
        
        try:
            # Test Database
            stats = self.db.get_job_stats()
            results['database'] = True
        except Exception as e:
            log_error(f"Database connection test failed: {e}")
        
        return results
    
    def get_health_status(self) -> dict:
        """Get overall system health status"""
        connections = self.test_connections()
        stats = self.db.get_job_stats()
        
        # Check folder accessibility
        folders = {
            'watch': self.config.get("processing.watch_folder"),
            'processed': self.config.get("processing.processed_folder"),
            'error': self.config.get("processing.error_folder"),
            'output': self.config.get("processing.output_folder")
        }
        
        folder_status = {}
        for name, path in folders.items():
            try:
                if path and os.path.exists(path) and os.access(path, os.W_OK):
                    folder_status[name] = True
                else:
                    folder_status[name] = False
            except:
                folder_status[name] = False
        
        return {
            'connections': connections,
            'folders': folder_status,
            'stats': stats,
            'healthy': all(connections.values()) and all(folder_status.values())
        }
