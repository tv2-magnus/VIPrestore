import logging
from utils import resource_path

logger = logging.getLogger(__name__)

# Application identifiers
APP_NAME = "VIPrestore"
APP_VERSION_FILE = "version.txt"

def get_version():
    """
    Get the application version from the version file.
    This is the centralized version reading function to be used throughout the application.
    
    Returns:
        str: Version string, or "0.0.0" if version file can't be read
    """
    try:
        with open(resource_path(APP_VERSION_FILE), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error reading version file: {e}")
        return "0.0.0"

# Application constants
APP_VERSION = get_version()
APP_ID = f"tv2.{APP_NAME.lower()}.client.{APP_VERSION}"