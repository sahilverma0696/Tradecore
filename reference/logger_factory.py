import logging
import os

def get_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """
    Create and return a logger that writes to logs/<name>.log.
    
    :param name: Identifier (usually the class or module name).
    :param log_dir: Directory where log files are stored.
    :return: Configured logger instance.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{name.lower()}.log")

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Set to DEBUG to allow all levels

    # Avoid duplicate handlers if logger is reused
    if not logger.handlers:
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)

        logger.addHandler(fh)

    return logger
