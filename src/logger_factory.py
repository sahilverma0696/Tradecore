import logging
import os

def get_logger(name: str, log_dir: str = "logs", console_output: bool = False) -> logging.Logger:
    """
    Return a logger writing DEBUG level logs to logs/<name>.log
    
    Args:
        name: Logger name
        log_dir: Directory for log files
        console_output: If True, also log to console/CLI
    
    Returns:
        Configured logger instance
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{name.lower()}.log")

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # File handler (always present)
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            '%Y-%m-%d %H:%M:%S',
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        
        # Console handler (optional)
        if console_output:
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)  # Console gets INFO level and above
            console_fmt = logging.Formatter(
                '%(name)s - %(levelname)s - %(message)s'
            )
            ch.setFormatter(console_fmt)
            logger.addHandler(ch)

    return logger
