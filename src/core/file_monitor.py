import os
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.core.processor import AudioProcessor
from src.utils import ConfigManager, log_info, log_error, log_warning

class AudioFileHandler(FileSystemEventHandler):
    def __init__(self, processor: AudioProcessor):
        self.processor = processor
        self.config = ConfigManager()
        self.processing_files = set()  # Track files currently being processed
        self.lock = threading.Lock()
    
    def on_created(self, event):
        """Handle new file creation events"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        log_info(f"New file detected: {file_path}")
        
        # Schedule file for processing after stability check
        threading.Thread(
            target=self._process_file_safely,
            args=(file_path,),
            daemon=True
        ).start()
    
    def _process_file_safely(self, file_path: str):
        """Process file with safety checks and stability waiting"""
        try:
            # Check if already processing this file
            with self.lock:
                if file_path in self.processing_files:
                    log_warning(f"File already being processed: {file_path}")
                    return
                self.processing_files.add(file_path)
            
            try:
                # Wait for file stability
                if not self._wait_for_file_stability(file_path):
                    log_warning(f"File stability check failed: {file_path}")
                    return
                
                # Check file format
                if not self._is_supported_format(file_path):
                    log_info(f"Unsupported file format, skipping: {file_path}")
                    return
                
                # Process the file
                log_info(f"Starting processing for: {file_path}")
                success = self.processor.process_file(file_path)
                
                if success:
                    log_info(f"Successfully processed: {file_path}")
                else:
                    log_error(f"Processing failed for: {file_path}")
                    
            finally:
                # Remove from processing set
                with self.lock:
                    self.processing_files.discard(file_path)
                    
        except Exception as e:
            log_error(f"Error in file processing thread: {e}")
            with self.lock:
                self.processing_files.discard(file_path)
    
    def _wait_for_file_stability(self, file_path: str) -> bool:
        """Wait for file to be completely written"""
        try:
            stability_wait = self.config.get("processing.file_stability_wait", 10)
            max_checks = 10
            check_interval = max(1, stability_wait // max_checks)
            
            log_info(f"Waiting for file stability: {file_path}")
            
            previous_size = -1
            stable_count = 0
            required_stable_checks = 3
            
            for i in range(max_checks):
                if not os.path.exists(file_path):
                    log_warning(f"File disappeared during stability check: {file_path}")
                    return False
                
                try:
                    current_size = os.path.getsize(file_path)
                    
                    if current_size == previous_size and current_size > 0:
                        stable_count += 1
                        if stable_count >= required_stable_checks:
                            log_info(f"File stable after {i + 1} checks: {file_path}")
                            return True
                    else:
                        stable_count = 0
                    
                    previous_size = current_size
                    
                except OSError as e:
                    log_warning(f"Error checking file size: {e}")
                    stable_count = 0
                
                time.sleep(check_interval)
            
            # Final check - if file has size and hasn't changed recently, proceed
            if previous_size > 0:
                log_warning(f"File may still be unstable but proceeding: {file_path}")
                return True
            
            log_error(f"File stability check failed: {file_path}")
            return False
            
        except Exception as e:
            log_error(f"Error in file stability check: {e}")
            return False
    
    def _is_supported_format(self, file_path: str) -> bool:
        """Check if file format is supported"""
        try:
            supported_formats = self.config.get("processing.supported_formats", [])
            file_ext = os.path.splitext(file_path)[1].lower()
            return file_ext in supported_formats
        except Exception as e:
            log_error(f"Error checking file format: {e}")
            return False

class FileMonitor:
    def __init__(self):
        self.config = ConfigManager()
        self.processor = None
        self.observer = None
        self.running = False
        
        # Get watch folder from config
        self.watch_folder = self.config.get("processing.watch_folder")
        if not self.watch_folder:
            raise ValueError("Watch folder not configured. Please set WATCH_FOLDER in your .env file")
        
        # Ensure watch folder exists
        os.makedirs(self.watch_folder, exist_ok=True)
        
        log_info(f"File monitor initialized for: {self.watch_folder}")
    
    def start(self):
        """Start monitoring the watch folder"""
        if self.running:
            log_warning("File monitor is already running")
            return
        
        try:
            # Lazily create processor at start time
            self.processor = AudioProcessor()
            # Create event handler
            event_handler = AudioFileHandler(self.processor)
            
            # Create observer
            self.observer = Observer()
            recursive_flag = bool(self.config.get("processing.recursive_watch", True))
            self.observer.schedule(event_handler, self.watch_folder, recursive=recursive_flag)
            
            # Start monitoring
            self.observer.start()
            self.running = True
            
            log_info(f"File monitor started, watching: {self.watch_folder}")
            
            # Process any existing files in the folder
            self._process_existing_files(event_handler)
            
        except Exception as e:
            log_error(f"Failed to start file monitor: {e}")
            raise
    
    def stop(self):
        """Stop monitoring"""
        if not self.running:
            return
        
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5)
            
            self.running = False
            log_info("File monitor stopped")
            
        except Exception as e:
            log_error(f"Error stopping file monitor: {e}")
    
    def _process_existing_files(self, handler: AudioFileHandler):
        """Process any files that already exist in the watch folder"""
        try:
            if not os.path.exists(self.watch_folder):
                return
            
            existing_files = []
            recursive_flag = bool(self.config.get("processing.recursive_watch", True))
            if recursive_flag:
                for root, _, files in os.walk(self.watch_folder):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        existing_files.append(file_path)
            else:
                for filename in os.listdir(self.watch_folder):
                    file_path = os.path.join(self.watch_folder, filename)
                    if os.path.isfile(file_path):
                        existing_files.append(file_path)
            
            if existing_files:
                log_info(f"Found {len(existing_files)} existing files to process")
                
                for file_path in existing_files:
                    log_info(f"Processing existing file: {file_path}")
                    # Use the same handler logic
                    threading.Thread(
                        target=handler._process_file_safely,
                        args=(file_path,),
                        daemon=True
                    ).start()
                    
                    # Small delay between files to avoid overwhelming the system
                    time.sleep(1)
            
        except Exception as e:
            log_error(f"Error processing existing files: {e}")
    
    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self.running
    
    def get_status(self) -> dict:
        """Get monitor status"""
        return {
            'running': self.running,
            'watch_folder': self.watch_folder,
            'folder_exists': os.path.exists(self.watch_folder) if self.watch_folder else False,
            'folder_accessible': os.access(self.watch_folder, os.R_OK) if self.watch_folder and os.path.exists(self.watch_folder) else False
        }
    
    def run_forever(self):
        """Run the monitor indefinitely (blocking)"""
        self.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            log_info("Received interrupt signal, stopping file monitor")
        finally:
            self.stop()
