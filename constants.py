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

# Auto-refresh configuration (in milliseconds)
# Polling intervals for subscription-based updates
POLL_INTERVAL_ACTIVE = 5000  # 5 seconds when window is active (faster for real-time feel)
POLL_INTERVAL_BACKGROUND = 30000  # 30 seconds when window is backgrounded
POLL_INTERVAL_BURST = 3000  # 3 seconds during burst mode (after user operations)
POLL_BURST_DURATION = 60000  # 1 minute of burst mode after user operations
POLL_IDLE_THRESHOLD = 20  # Number of unchanged polls before increasing interval
POLL_INTERVAL_IDLE = 15000  # 15 seconds when no changes detected (still responsive)