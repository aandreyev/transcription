#!/usr/bin/env python3
"""
Audio Processor - Main Application Entry Point

This application monitors a folder for audio files, transcribes them using Deepgram,
processes them with OpenAI, and generates intelligent summaries with smart file naming.
"""

import sys
import os
import signal
import threading
import socket
import argparse
from src.core import FileMonitor, AudioProcessor
from src.utils import ConfigManager, log_info, log_error
from src.web.app import create_app
import uvicorn

class AudioProcessorApp:
    def __init__(self, port_override=None):
        self.config = ConfigManager()
        self.file_monitor = None
        self.web_server = None
        self.running = False
        self.actual_port = None
        self.port_override = port_override
    
    def find_available_port(self, start_port, max_attempts=20):
        """Find an available port starting from start_port, avoiding problematic ports"""
        # Ports to avoid (system, well-known services, security issues)
        avoid_ports = {
            # System/privileged ports
            22,    # SSH
            23,    # Telnet
            25,    # SMTP
            53,    # DNS
            80,    # HTTP
            110,   # POP3
            143,   # IMAP
            443,   # HTTPS
            993,   # IMAPS
            995,   # POP3S
            
            # Database ports
            1433,  # SQL Server
            1521,  # Oracle
            3306,  # MySQL
            5432,  # PostgreSQL
            6379,  # Redis
            27017, # MongoDB
            
            # Development/common conflicts
            3000,  # React dev server
            4200,  # Angular dev server
            5000,  # Flask default
            5173,  # Vite dev server
            8080,  # Common alt HTTP
            8443,  # Common alt HTTPS
            9000,  # Common dev port
            
            # Security/malware associated
            1337,  # Often used by malware
            31337, # Elite/hacker port
            
            # System services
            135,   # Windows RPC
            139,   # NetBIOS
            445,   # SMB
            1900,  # UPnP
            5353,  # mDNS
        }
        
        for i in range(max_attempts):
            port = start_port + i
            
            # Skip ports we want to avoid
            if port in avoid_ports:
                continue
                
            # Skip privileged ports (< 1024) unless specifically requested
            if port < 1024 and start_port >= 1024:
                continue
                
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    return port
            except OSError:
                continue
                
        raise RuntimeError(f"Could not find available port after {max_attempts} attempts starting from {start_port}")
    
    def start(self):
        """Start the complete application"""
        try:
            log_info("Starting Audio Processor Application")
            log_info(f"Version: {self.config.get('app.version', '1.0.0')}")
            
            # Test system health before starting (tolerant of missing keys)
            health = None
            try:
                processor = AudioProcessor()
                health = processor.get_health_status()
            except Exception as e:
                log_error(f"Health check limited: {e}")
                # Build a minimal health snapshot without external services
                connections = {
                    'deepgram': False,
                    'openai': False,
                    'database': True,
                }
                folders = {
                    'watch': self.config.get("processing.watch_folder"),
                    'processed': self.config.get("processing.processed_folder"),
                    'error': self.config.get("processing.error_folder"),
                    'output': self.config.get("processing.output_folder"),
                }
                folders = {k: bool(v and os.path.exists(v) and os.access(v, os.W_OK)) for k, v in folders.items()}
                health = {
                    'connections': connections,
                    'folders': folders,
                    'stats': {'total': 0, 'status_counts': {}, 'today': 0, 'success_rate': 0},
                    'healthy': False,
                }
                log_error("Continuing startup without external services; configure on /admin")
            
            if not health['healthy']:
                log_error("System health check reported issues")
            
            # Start file monitor only if watch folder configured
            try:
                watch_folder = self.config.get('processing.watch_folder')
                if watch_folder and os.path.isdir(watch_folder):
                    log_info("Starting file monitor...")
                    self.file_monitor = FileMonitor()
                    self.file_monitor.start()
                else:
                    log_error("Watch folder not configured or missing; skipping monitor. Configure on /admin")
            except Exception as e:
                log_error(f"File monitor not started: {e}")
            
            # Start web server
            log_info("Starting web server...")
            self._start_web_server()
            
            self.running = True
            log_info("Audio Processor Application started successfully")
            log_info(f"Web interface available at: http://{self.config.get('web.host', '127.0.0.1')}:{self.actual_port}")
            log_info(f"Monitoring folder: {self.config.get('processing.watch_folder')}")
            
        except Exception as e:
            log_error(f"Failed to start application: {e}")
            self.stop()
            raise
    
    def _start_web_server(self):
        """Start the web server in a separate thread"""
        # Determine port to use
        desired_port = self.port_override or self.config.get('web.port', 8005)
        auto_port = self.config.get('web.auto_port', True)
        
        if auto_port:
            try:
                self.actual_port = self.find_available_port(desired_port)
                if self.actual_port != desired_port:
                    log_info(f"Port {desired_port} busy, using port {self.actual_port} instead")
            except RuntimeError as e:
                log_error(f"Port conflict resolution failed: {e}")
                self.actual_port = desired_port  # Fall back to original port
        else:
            self.actual_port = desired_port
        
        def run_server():
            try:
                app = create_app()
                uvicorn.run(
                    app,
                    host=self.config.get('web.host', '127.0.0.1'),
                    port=self.actual_port,
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
    parser = argparse.ArgumentParser(description='Audio Processor - Intelligent audio transcription and processing')
    parser.add_argument('--port', type=int, help='Web server port (overrides config file)')
    parser.add_argument('--host', type=str, help='Web server host (overrides config file)')
    parser.add_argument('--no-auto-port', action='store_true', help='Disable automatic port finding')
    
    args = parser.parse_args()
    
    try:
        app = AudioProcessorApp(port_override=args.port)
        
        # Override config with command line args
        if args.host:
            app.config.config['web']['host'] = args.host
        if args.no_auto_port:
            app.config.config['web']['auto_port'] = False
            
        app.run_forever()
    except KeyboardInterrupt:
        log_info("Application interrupted by user")
    except Exception as e:
        log_error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
