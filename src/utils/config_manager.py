import os
import yaml
from typing import Dict, Any
from dotenv import load_dotenv
import re

class ConfigManager:
    def __init__(self, config_path: str = "config/config.yaml", env_path: str = "config/.env"):
        self.config_path = config_path
        self.env_path = env_path
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML and environment variables"""
        # Load environment variables (override so admin changes take effect immediately)
        load_dotenv(self.env_path, override=True)
        
        # Load YAML config
        with open(self.config_path, 'r') as file:
            self._config = yaml.safe_load(file)
        
        # Replace placeholders with environment variables
        self._config = self._replace_env_vars(self._config)
    
    def _replace_env_vars(self, obj: Any) -> Any:
        """Recursively replace {{VAR}} placeholders with environment variables"""
        if isinstance(obj, dict):
            return {key: self._replace_env_vars(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            # Replace {{VAR}} with environment variable
            pattern = r'\{\{(\w+)\}\}'
            matches = re.findall(pattern, obj)
            for match in matches:
                env_value = os.getenv(match, f"{{{{${match}}}}}")  # Keep placeholder if env var not found
                obj = obj.replace(f"{{{{{match}}}}}", env_value)
            return obj
        else:
            return obj
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'app.name')"""
        keys = key_path.split('.')
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration"""
        return self._config.copy()
    
    def reload(self):
        """Reload configuration from files"""
        self._load_config()
