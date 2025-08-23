import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional
from src.utils.config_manager import ConfigManager

class Logger:
    _instance = None
    _logger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._setup_logger()
        return cls._instance
    
    def _setup_logger(self):
        """Setup centralized logging configuration"""
        config = ConfigManager()
        
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Configure logger
        self._logger = logging.getLogger("audio_processor")
        self._logger.setLevel(getattr(logging, config.get("logging.level", "INFO")))
        
        # Clear existing handlers
        self._logger.handlers.clear()
        
        # File handler with rotation
        log_file = f"logs/audio_processor_{datetime.now().strftime('%Y%m%d')}.log"
        max_bytes = self._parse_size(config.get("logging.max_file_size", "10MB"))
        backup_count = config.get("logging.backup_count", 5)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '10MB' to bytes"""
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def get_logger(self):
        """Get the configured logger instance"""
        return self._logger
    
    def log_job_event(self, job_id: Optional[int], level: str, message: str):
        """Log an event with job correlation"""
        if job_id:
            message = f"[Job {job_id}] {message}"
        
        log_method = getattr(self._logger, level.lower(), self._logger.info)
        log_method(message)

# Convenience functions
def get_logger():
    """Get the singleton logger instance"""
    return Logger().get_logger()

def log_info(message: str, job_id: Optional[int] = None):
    """Log info message"""
    Logger().log_job_event(job_id, "info", message)

def log_error(message: str, job_id: Optional[int] = None):
    """Log error message"""
    Logger().log_job_event(job_id, "error", message)

def log_warning(message: str, job_id: Optional[int] = None):
    """Log warning message"""
    Logger().log_job_event(job_id, "warning", message)

def log_debug(message: str, job_id: Optional[int] = None):
    """Log debug message"""
    Logger().log_job_event(job_id, "debug", message)
