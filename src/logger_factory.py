import logging
import os

class CustomLogger:
    """Custom logger wrapper that supports per-call console output control."""
    
    def __init__(self, name: str, log_dir: str = "logs"):
        self.name = name
        self.log_dir = log_dir
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup the base file logger."""
        os.makedirs(self.log_dir, exist_ok=True)
        log_file = os.path.join(self.log_dir, f"{self.name.lower()}.log")
        
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)
        
        if not self.logger.handlers:
            # File handler
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.DEBUG)
            fmt = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                '%Y-%m-%d %H:%M:%S',
            )
            fh.setFormatter(fmt)
            self.logger.addHandler(fh)
    
    def _log_with_console_option(self, level, message, to_console=False):
        """Log message with optional console output."""
        # Always log to file
        getattr(self.logger, level)(message)
        
        # Optionally log to console
        if to_console:
            console_handler = None
            # Check if console handler already exists
            for handler in self.logger.handlers:
                if isinstance(handler, logging.StreamHandler) and handler.stream.name == '<stderr>':
                    console_handler = handler
                    break
            
            if not console_handler:
                # Create temporary console handler
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                fmt = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    '%Y-%m-%d %H:%M:%S',
                )
                console_handler.setFormatter(fmt)
                self.logger.addHandler(console_handler)
                
                # Log the message again to console
                getattr(self.logger, level)(message)
                
                # Remove the temporary console handler
                self.logger.removeHandler(console_handler)
            else:
                # Console handler exists, message already went to console
                pass
    
    def debug(self, message, to_console=False):
        self._log_with_console_option('debug', message, to_console)
    
    def info(self, message, to_console=False):
        self._log_with_console_option('info', message, to_console)
    
    def warning(self, message, to_console=False):
        self._log_with_console_option('warning', message, to_console)
    
    def error(self, message, to_console=False):
        self._log_with_console_option('error', message, to_console)
    
    def critical(self, message, to_console=False):
        self._log_with_console_option('critical', message, to_console)

def get_logger(name: str, log_dir: str = "logs") -> CustomLogger:
    """Return a custom logger that supports per-call console output control."""
    return CustomLogger(name, log_dir)
