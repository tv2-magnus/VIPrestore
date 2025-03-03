"""
logging_config.py - Centralized logging configuration for VIPrestore
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from constants import APP_NAME

def configure_logging():
    """
    Configure application-wide logging with consistent levels and format.
    Creates logs in user's local appdata directory.
    
    Returns:
        str: Path to the log file
    """
    # Determine log directory
    log_dir = Path(os.getenv('LOCALAPPDATA', os.path.expanduser('~'))) / APP_NAME
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"viprestore_{timestamp}.log"
    log_path = str(log_dir / log_filename)
    
    # Configure logging
    logging.basicConfig(
        filename=log_path,
        filemode='w',  # 'w' instead of 'a' since each file is new
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.INFO
    )
    
    # Add console handler for development environments
    if os.getenv('VIPRESTORE_DEV', '').lower() in ('1', 'true', 'yes'):
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
    
    # Configure specific loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    # Log application startup
    logger = logging.getLogger(__name__)
    logger.info("Application started")
    
    return log_path