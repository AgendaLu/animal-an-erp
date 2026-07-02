"""
Logging utility for the ERP system
"""
import os
import logging
from datetime import datetime
from pathlib import Path

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with specific configuration
    
    Args:
        name: Logger name (usually __name__ from the calling module)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    
    # Only configure handlers if they haven't been added yet
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Create logs directory if it doesn't exist
        logs_dir = Path(__file__).parent.parent / 'logs'
        logs_dir.mkdir(exist_ok=True)
        
        # Create file handler
        log_file = logs_dir / f"{datetime.now().strftime('%Y%m')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Add formatter to handlers
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

# Create default logger
default_logger = get_logger('erp')

def log_error(message: str, error: Exception = None):
    """Log error message and exception details"""
    if error:
        default_logger.error(f"{message}: {str(error)}")
    else:
        default_logger.error(message)

def log_info(message: str):
    """Log info message"""
    default_logger.info(message)

def log_debug(message: str):
    """Log debug message"""
    default_logger.debug(message)

def log_warning(message: str):
    """Log warning message"""
    default_logger.warning(message)
