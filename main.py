#!/usr/bin/env python3
"""
Audio Processor - Main Application Entry Point

This application monitors a folder for audio files, transcribes them using Deepgram,
processes them with OpenAI, and generates intelligent summaries with smart file naming.
"""

import sys
import signal
import threading
from src.core import FileMonitor, AudioProcessor
from src.utils import ConfigManager, log_info, log_error
from src.web.app import create_app
import uvicorn

class AudioProcessorApp:
    def __init__(self):
        self.config = ConfigManager()
        self.file_monitor = None
        self.web_server = None
        self.running = False
    
    def start(self):
        """Start the complete application"""
        try:
            log_info("Starting Audio Processor Application")
            log_info(f"Version: {self.config.get('app.version', '1.0.0')}")
            
            # Test system health before starting
            processor = AudioProcessor()
            health = processor.get_health_status()
            
            if not health['healthy']:
                log_error("System health check failed:")
                log_error(f"Connections: {health['connections']}")
                log_error(f"Folders: {health['folders']}")
                
                # Continue anyway but warn user
                log_error("Continuing startup despite health issues...")
            
            # Start file monitor
            log_info("Starting file monitor...")
            self.file_monitor = FileMonitor()
            self.file_monitor.start()
            
            # Start web server
            log_info("Starting web server...")
            self._start_web_server()
            
            self.running = True
            log_info("Audio Processor Application started successfully")
            log_info(f"Web interface available at: http://{self.config.get('web.host', '127.0.0.1')}:{self.config.get('web.port', 8000)}")
            log_info(f"Monitoring folder: {self.config.get('processing.watch_folder')}")
            
        except Exception as e:
            log_error(f"Failed to start application: {e}")
            self.stop()
            raise
    
    def _start_web_server(self):
        """Start the web server in a separate thread"""
        def run_server():
            try:
                app = create_app()
                uvicorn.run(
                    app,
                    host=self.config.get('web.host', '127.0.0.1'),
                    port=self.config.get('web.port', 8000),
                    log_level="info" if self.config.get('app.debug', False) else "warning",
                    access_log=False
                )
            except Exception as e:
                log_error(f"Web server error: {e}")
        
        self.web_server = threading.Thread(target=run_server, daemon=True)
        self.web_server.start()
    
    def stop(self):
        """Stop the application gracefully"""
        if not self.running:
            return
        
        log_info("Stopping Audio Processor Application...")
        
        try:
            # Stop file monitor
            if self.file_monitor:
                log_info("Stopping file monitor...")
                self.file_monitor.stop()
            
            # Web server will stop automatically as it's a daemon thread
            
            self.running = False
            log_info("Audio Processor Application stopped")
            
        except Exception as e:
            log_error(f"Error during shutdown: {e}")
    
    def run_forever(self):
        """Run the application indefinitely"""
        self.start()
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            log_info(f"Received signal {signum}, shutting down...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Keep main thread alive
            while self.running:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            log_info("Received keyboard interrupt")
        finally:
            self.stop()

def main():
    """Main entry point"""
    try:
        app = AudioProcessorApp()
        app.run_forever()
    except KeyboardInterrupt:
        log_info("Application interrupted by user")
    except Exception as e:
        log_error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
