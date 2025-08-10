import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

from src.logger_factory import get_logger


class SystemConfigManager:
    """Manages system-wide configuration (separate from trading config)."""
    
    def __init__(self, config_file: str = "system_config.json"):
        self.config_file = Path(config_file)
        self.logger = get_logger("SystemConfig")
        self._config = {}
        self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """Load system configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    self._config = json.load(f)
                self.logger.info(f"Loaded system config from {self.config_file}")
            else:
                self.logger.warning(f"System config file not found: {self.config_file}")
                self._config = self._get_default_config()
                self.save_config()
                
        except Exception as e:
            self.logger.error(f"Error loading system config: {e}")
            self._config = self._get_default_config()
            
        return self._config
        
    def save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self._config, f, indent=2)
            self.logger.info(f"Saved system config to {self.config_file}")
        except Exception as e:
            self.logger.error(f"Error saving system config: {e}")
            
    def get(self, key_path: str, default=None) -> Any:
        """Get configuration value using dot notation (e.g., 'streamer.type')."""
        keys = key_path.split('.')
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
            
    def set(self, key_path: str, value: Any):
        """Set configuration value using dot notation."""
        keys = key_path.split('.')
        config = self._config
        
        # Navigate to parent
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
            
        # Set final value
        config[keys[-1]] = value
        
    def get_streamer_config(self) -> Dict[str, Any]:
        """Get streamer configuration."""
        streamer_type = self.get('streamer.type', 'offline')
        return {
            'type': streamer_type,
            'config': self.get(f'streamer.config.{streamer_type}', {})
        }
        
    def get_executioner_config(self) -> Dict[str, Any]:
        """Get executioner configuration."""
        exec_type = self.get('executioner.type', 'mock')
        return {
            'type': exec_type,
            'config': self.get(f'executioner.config.{exec_type}', {})
        }
        
    def is_offline_mode(self) -> bool:
        """Check if system is in offline mode."""
        return self.get('system.mode', 'offline') == 'offline'
        
    def is_live_mode(self) -> bool:
        """Check if system is in live mode."""
        return self.get('system.mode', 'offline') == 'live'
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default system configuration."""
        return {
            "system": {
                "mode": "offline"
            },
            "streamer": {
                "type": "offline",
                "config": {
                    "offline": {
                        "data_dir": "data",
                        "playback_speed": 1.0
                    }
                }
            },
            "executioner": {
                "type": "mock",
                "config": {
                    "mock": {
                        "slippage_factor": 0.0001,
                        "execution_delay": 0.1,
                        "initial_cash": 100000.0
                    }
                }
            },
            "logging": {
                "level": "INFO",
                "console_output": True,
                "file_output": True
            }
        }
        
    def get_all_config(self) -> Dict[str, Any]:
        """Get complete configuration."""
        return self._config.copy()
