"""
logging_config.py - Centralized logging configuration for VIPrestore
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from constants import APP_NAME

def configure_logging():
    """
    Configure application-wide logging with consistent levels and format.
    Creates logs in user's local appdata directory with rotation.
    
    Returns:
        str: Path to the log file
    """
    # Determine log directory
    log_dir = Path(os.getenv('LOCALAPPDATA', os.path.expanduser('~'))) / APP_NAME
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create log filename with app name
    log_filename = f"viprestore.log"
    log_path = str(log_dir / log_filename)
    
    # Create root logger
    root_logger = logging.getLogger('')
    root_logger.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create rotating file handler (10 files of 5MB each)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5*1024*1024,  # 5MB per file
        backupCount=10,         # Keep 10 files
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    
    # Add console handler for development environments
    if os.getenv('VIPRESTORE_DEV', '').lower() in ('1', 'true', 'yes'):
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        console.setFormatter(console_formatter)
        root_logger.addHandler(console)
    
    # Configure specific loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    # Create application logger and log startup
    logger = logging.getLogger(__name__)
    logger.info(f"Application started ({APP_NAME})")
    logger.info(f"Log file: {log_path}")
    
    return log_path