"""
strings.py - Centralized string resources for VIPrestore application.
"""

# General UI Strings
APP_TITLE = "VIPrestore"

# Dialog Titles
DIALOG_TITLE_LOGIN = "Login"
DIALOG_TITLE_ABOUT = "About"
DIALOG_TITLE_ERROR = "Error"
DIALOG_TITLE_WARNING = "Warning"
DIALOG_TITLE_INFO = "Information"
DIALOG_TITLE_CONFIRM = "Confirm"
DIALOG_TITLE_SYSTEMS_EDITOR = "Systems Editor"
DIALOG_TITLE_UPDATE = "Update Available"
DIALOG_TITLE_SERVICE_CREATION = "Confirm Service Creation"
DIALOG_TITLE_GROUP_SERVICE = "Group Service: {0}"  # {0} = group_id

# Error Messages
ERROR_LOGIN_FAILED = "Login Failed"
ERROR_LOGOUT_FAILED = "Logout Error"
ERROR_CONNECTION_FAILED = "Connection Failed"
ERROR_SESSION_EXPIRED = "Your session has expired. Please log in again."
ERROR_SERVICE_NOT_FOUND = "Service {0} not found"  # {0} = service_id
ERROR_SAVE_SYSTEMS = "Failed to save systems: {0}"  # {0} = error message
ERROR_CREATE_SERVICES = "Service Creation Error"
ERROR_CANCEL_SERVICES = "Cancel Error"
ERROR_FETCH_SERVICES = "Error Refreshing Services"
ERROR_DOWNLOAD = "Download failed: {0}"  # {0} = error message
ERROR_SSL_CERT = "SSL certificate verification failed for {0}."  # {0} = domain
ERROR_SSL_CERT_CONTINUE = """
SSL certificate verification failed for {0}.

Continuing without verification could expose sensitive information 
to attackers. Only proceed if you understand the risks.

Do you want to continue with an insecure connection?
"""

# Success Messages
SUCCESS_SERVICES_SAVED = "Saved {0} service(s) to {1}."  # {0} = count, {1} = path
SUCCESS_SERVICES_CREATED = "Successfully created {0} service(s)."  # {0} = count
SUCCESS_SERVICES_CANCELED = "Successfully cancelled {0} of {1} service(s)."  # {0} = success_count, {1} = total

# Confirmation Messages
CONFIRM_CANCEL_SERVICES = "Are you sure you want to cancel the selected service(s)?"
CONFIRM_REMOVE_SYSTEM = "Remove selected system?"

# Status Messages
STATUS_CONNECTED_HTTPS_VALID = "Connected (HTTPS, valid SSL)"
STATUS_CONNECTED_HTTPS_INVALID = "Connected (HTTPS, invalid SSL)"
STATUS_CONNECTED_HTTP = "Connected (HTTP, not secure)"
STATUS_CONNECTED_UNKNOWN = "Connected (Unknown Protocol)"
STATUS_CONNECTED_NO_URL = "Connected (Server URL not set)"
STATUS_DISCONNECTED = "No Connection"
STATUS_REFRESHING = "Refreshing services..."
STATUS_REFRESHED = "Services refreshed"
STATUS_ERROR_REFRESHING = "Error refreshing services"
STATUS_DOWNLOADING = "Downloading... {0} of {1}"  # {0} = downloaded size, {1} = total size
STATUS_DOWNLOAD_COMPLETE = "Download complete"
STATUS_DOWNLOAD_CANCELED = "Cancelling download..."
STATUS_TOTAL_SERVICES = "Total services: {0}"  # {0} = count

# Menu Strings
MENU_FILE = "File"
MENU_TOOLS = "Tools"
MENU_HELP = "Help"

# MenuItem Strings
MENU_ITEM_LOGIN = "Login"
MENU_ITEM_LOGOUT = "Logout"
MENU_ITEM_LOAD_SERVICES = "Load Services"
MENU_ITEM_SAVE_SELECTED = "Save Selected Services"
MENU_ITEM_EXIT = "Exit"
MENU_ITEM_REFRESH = "Refresh Services"
MENU_ITEM_EDIT_SYSTEMS = "Edit Systems"
MENU_ITEM_CANCEL_SERVICES = "Cancel Selected Services"
MENU_ITEM_ABOUT = "About"
MENU_ITEM_USER_MANUAL = "User Manual"

# Button Labels
BUTTON_LOGIN = "Login"
BUTTON_CANCEL = "Cancel"
BUTTON_DOWNLOAD = "Download & Install"
BUTTON_SAVE = "Save"
BUTTON_OK = "OK"
BUTTON_RESET_FILTERS = "Reset Filters"
BUTTON_ADD = "Add"
BUTTON_REMOVE = "Remove"
BUTTON_CLOSE = "Close"

# Selection Messages
MSG_NO_SELECTION = "Please select at least one service to save."
MSG_NO_SELECTION_CANCEL = "Please select at least one service to cancel."
MSG_NO_CONNECTION = "Not connected to a remote VideoIPath system."