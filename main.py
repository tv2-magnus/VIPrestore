import sys
import os
import re
import json
import asyncio
from datetime import datetime
from qasync import QEventLoop
from PyQt6 import QtWidgets, uic, QtGui, QtCore
from vipclient import VideoIPathClient, VideoIPathClientError
from login_dialog import LoginDialog
from load_services_dialog import LoadServicesDialog
from group_detail_dialog import GroupDetailDialog
from concurrent.futures import ThreadPoolExecutor
from services_filter import ServicesFilterProxy
from utils import resource_path, schedule_ui_task
from service_manager import ServiceManager, ServiceManagerError
import logging
from pathlib import Path
from splash_manager import SplashManager
import styling
from application_updater import ApplicationUpdater
from constants import APP_NAME
import strings
from logging_config import configure_logging
from exceptions import exception_handler

# This is test cmment for testing purposes
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Cross-platform log directory determination
def get_app_log_dir() -> Path:
    """
    Returns a Path object for a user-writable application log directory.
    On Windows, uses LOCALAPPDATA; on macOS, uses Application Support; on Linux, uses XDG_CONFIG_HOME.
    The directory is created if it doesn't exist.
    """
    if sys.platform.startswith("win"):
        log_dir = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / APP_NAME
    elif sys.platform == "darwin":
        log_dir = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        log_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
    
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

# Use the cross-platform function for log directory
log_dir = get_app_log_dir()
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"viprestore_{timestamp}.log"

# Configure logging
logging.basicConfig(
    filename=str(log_dir / log_filename),
    filemode='w',  # 'w' instead of 'a' since each file is new
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.debug("Application started")

def get_user_config_dir() -> Path:
    """
    Returns a Path object for a user-writable configuration directory.
    On Windows, uses LOCALAPPDATA; on macOS, uses Application Support; on Linux, uses XDG_CONFIG_HOME (or ~/.config).
    The directory is created if it doesn't exist.
    """
    if sys.platform.startswith("win"):
        config_dir = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "VIPrestore"
    elif sys.platform == "darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "VIPrestore"
    else:
        config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "VIPrestore"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def get_remote_systems_config_file() -> Path:
    """
    Returns the full path to remotesystems.json in the user-writable config directory.
    """
    return get_user_config_dir() / "remotesystems.json"

def save_remote_systems_config(config_data: dict) -> None:
    """
    Saves the provided configuration data as JSON into remotesystems.json in a user-writable location.
    """
    config_file = get_remote_systems_config_file()
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        logging.debug(f"Remote systems configuration saved to {config_file}")
    except Exception as e:
        logging.error(f"Error saving remote systems configuration: {e}")
        raise

def load_remote_systems_config() -> dict | None:
    """
    Loads and returns the remote systems configuration from remotesystems.json.
    Returns None if the file does not exist or cannot be loaded.
    """
    config_file = get_remote_systems_config_file()
    if not config_file.exists():
        logging.debug(f"Remote systems configuration file does not exist at {config_file}")
        return None
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        logging.debug(f"Remote systems configuration loaded from {config_file}")
        return config_data
    except Exception as e:
        logging.error(f"Error loading remote systems configuration: {e}")
        return None

def ensure_remote_systems_config():
    """
    Checks if remotesystems.json exists in the user config directory.
    If not, copies the default bundled file (via resource_path) to that location.
    """
    config_file = get_remote_systems_config_file()
    if not config_file.exists():
        default_config_path = resource_path("remotesystems.json")
        if os.path.exists(default_config_path):
            try:
                with open(default_config_path, "r", encoding="utf-8") as src, \
                     open(config_file, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
                logging.debug(f"Copied default remotesystems.json to {config_file}")
            except Exception as e:
                logging.error(f"Failed to copy default remotesystems.json: {e}")
        else:
            logging.debug("Default remotesystems.json not found in resources.")

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(resource_path("main.ui"), self)

        # Add this right after super().__init__()
        self.bold_font_family = None  # Will be set from main()
        
        # Initialize current services storage
        self.currentServices = {}

        # Clean up menu bar: create a new organized menu bar for improved UX
        menubar = self.menuBar()
        menubar.clear()
        # Create menus
        self.menuFile = menubar.addMenu("File")
        self.menuTools = menubar.addMenu("Tools")
        self.menuHelp = menubar.addMenu("Help")

        # Create actions with keyboard shortcuts
        self.actionLogin = QtGui.QAction("Login", self)
        self.actionLogin.setShortcut("Ctrl+L")

        self.actionLogout = QtGui.QAction("Logout", self)
        self.actionLogout.setShortcut("Ctrl+Shift+L")

        self.actionLoadServices = QtGui.QAction("Load Services", self)
        self.actionLoadServices.setShortcut("Ctrl+O")

        self.actionSaveSelectedServices = QtGui.QAction("Save Selected Services", self)
        self.actionSaveSelectedServices.setShortcut("Ctrl+S")

        self.actionExit = QtGui.QAction("Exit", self)
        self.actionExit.setShortcut("Ctrl+Q")

        self.actionRefresh = QtGui.QAction("Refresh Services", self)
        self.actionRefresh.setShortcut("F5")

        self.actionEditSystems = QtGui.QAction("Edit Systems", self)
        self.actionEditSystems.setShortcut("Ctrl+E")

        self.actionAbout = QtGui.QAction("About", self)
        self.actionAbout.setShortcut("F1")

        # --- Cancel Services Action ---
        self.actionCancelSelectedServices = QtGui.QAction("Cancel Selected Services", self)
        self.actionCancelSelectedServices.setShortcut("Ctrl+D")
        self.actionCancelSelectedServices.setEnabled(False)
        self.menuTools.addAction(self.actionCancelSelectedServices)
        self.actionCancelSelectedServices.triggered.connect(lambda: asyncio.create_task(self.cancelSelectedServices()))
        # --- End Cancel Services Action ---

        # Add actions to File menu with grouping separators
        self.menuFile.addAction(self.actionLogin)
        self.menuFile.addAction(self.actionLogout)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionLoadServices)
        self.menuFile.addAction(self.actionSaveSelectedServices)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)

        # Add actions to Tools menu (with a separator between groups)
        self.menuTools.addAction(self.actionRefresh)
        self.menuTools.addSeparator()
        self.menuTools.addAction(self.actionEditSystems)

        # Add actions to Help menu with a separator
        self.menuHelp.addAction(self.actionAbout)
        self.menuHelp.addSeparator()

        self.actionHelp = QtGui.QAction("User Manual", self)
        self.actionHelp.setShortcut("Ctrl+H")
        self.menuHelp.addAction(self.actionHelp)
        self.actionHelp.triggered.connect(self.showHelpManual)

        # Connect Action Signals
        self.actionLogin.triggered.connect(lambda: asyncio.create_task(self.doLogin()))
        self.actionLogout.triggered.connect(self.doLogout)
        self.actionLoadServices.triggered.connect(lambda: asyncio.create_task(self.load_and_create_services()))
        self.actionSaveSelectedServices.triggered.connect(lambda: asyncio.create_task(self.saveSelectedServices()))
        self.actionExit.triggered.connect(self.close)
        self.actionRefresh.triggered.connect(lambda: asyncio.create_task(self.refreshServicesAsync()))
        self.actionEditSystems.triggered.connect(self.editSystems)
        self.actionAbout.triggered.connect(self.showAbout)

        self.setSplitterPlacement()

        # Instance Variables
        self.client = None
        self.service_manager = ServiceManager()
        self.profileCheckBoxes = []

        # Executor for blocking calls
        self.executor = ThreadPoolExecutor()

        # Basic table configuration - don't create models yet
        self.tableViewServices.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tableViewServices.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tableViewServices.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tableViewServices.setAlternatingRowColors(True)
        self.tableViewServices.setSortingEnabled(True)
        self.tableViewServices.clicked.connect(self.onServiceClicked)

        # Setup Model and Filter for Services
        self.serviceModel = QtGui.QStandardItemModel(self)
        self.filterProxy = ServicesFilterProxy(self)
        self.filterProxy.setSourceModel(self.serviceModel)
        self.tableViewServices.setModel(self.filterProxy)
        self.tableViewServices.selectionModel().selectionChanged.connect(self.onServiceSelectionChanged)

        # Setup Filter Widgets
        self.lineEditSourceFilter.textChanged.connect(self.onSourceFilterChanged)
        self.lineEditDestinationFilter.textChanged.connect(self.onDestinationFilterChanged)
        self.dateTimeEditStart.dateTimeChanged.connect(self.onTimeFilterChanged)
        self.dateTimeEditEnd.dateTimeChanged.connect(self.onTimeFilterChanged)
        self.checkBoxEnableTimeFilter.stateChanged.connect(self.onTimeFilterChanged)
        self.buttonResetFilters.clicked.connect(self.onResetFilters)

        # Configure Profile Filters Area
        self.scrollAreaProfilesFilters.setWidgetResizable(True)
        self.layoutProfiles = self.verticalLayoutProfilesList
        self.layoutProfiles.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Set Default Date/Time for Filters (today's 00:00 -> 23:59)
        today = QtCore.QDate.currentDate()
        start_dt = QtCore.QDateTime(today, QtCore.QTime(0, 0, 0))
        end_dt = QtCore.QDateTime(today, QtCore.QTime(23, 59, 59))
        self.dateTimeEditStart.setDateTime(start_dt)
        self.dateTimeEditEnd.setDateTime(end_dt)

        # Configure Service Details Table
        self.tableWidgetServiceDetails.setColumnCount(2)
        self.tableWidgetServiceDetails.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tableWidgetServiceDetails.horizontalHeader().setStretchLastSection(True)
        self.tableWidgetServiceDetails.horizontalHeader().setVisible(False)
        self.tableWidgetServiceDetails.verticalHeader().setVisible(False)
        self.tableWidgetServiceDetails.setWordWrap(True)
        self.tableWidgetServiceDetails.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.tableWidgetServiceDetails.verticalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.tableWidgetServiceDetails.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectItems)
        self.tableWidgetServiceDetails.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.tableWidgetServiceDetails.cellClicked.connect(self._onDetailsCellClicked)
        self.tableWidgetServiceDetails.setAlternatingRowColors(True)

        # Setup Session Timer
        self.sessionTimer = QtCore.QTimer(self)
        self.sessionTimer.setInterval(30000)
        self.sessionTimer.timeout.connect(self.checkSession)
        self.sessionTimer.start()

        # --- Context Menu Setup ---
        self.tableViewServices.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tableViewServices.customContextMenuRequested.connect(self.showContextMenu)
        # --- End Context Menu Setup ---

        # --- Status Bar Setup ---
        status_bar = QtWidgets.QStatusBar(self)
        self.setStatusBar(status_bar)

        # Connection state: indicator and text
        self.frameConnectionIndicator = QtWidgets.QFrame()
        self.frameConnectionIndicator.setMinimumSize(QtCore.QSize(20, 20))
        self.frameConnectionIndicator.setMaximumSize(QtCore.QSize(20, 20))
        self.frameConnectionIndicator.setFrameShape(QtWidgets.QFrame.Shape.Box)
        self.frameConnectionIndicator.setFrameShadow(QtWidgets.QFrame.Shadow.Raised)
        self.frameConnectionIndicator.setStyleSheet("background-color: grey;")
        status_bar.addWidget(self.frameConnectionIndicator)

        self.labelConnectionStatusText = QtWidgets.QLabel("No Connection")
        status_bar.addWidget(self.labelConnectionStatusText)

        # Service count
        self.labelServiceCount = QtWidgets.QLabel("Total services: 0")
        status_bar.addWidget(self.labelServiceCount)
        self.labelServiceCount.setVisible(False)

        # User info (name and role)
        self.labelUserInfo = QtWidgets.QLabel("User: N/A | Role: N/A")
        status_bar.addWidget(self.labelUserInfo)

        # Loading spinner (force a fixed size to prevent expansion)
        self.loadingLabel = QtWidgets.QLabel("")
        self.loadingMovie = QtGui.QMovie(resource_path(os.path.join("logos", "spinner.gif")))
        self.loadingLabel.setMovie(self.loadingMovie)
        self.loadingLabel.setFixedSize(20, 20)  # <-- Fixed size to constrain height
        status_bar.addWidget(self.loadingLabel)
        self.loadingLabel.setVisible(False)

        # Temporary status message on the far right
        self.statusMsgLabel = QtWidgets.QLabel("")

        # Ensure the status message label has a fixed vertical size
        self.statusMsgLabel.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed
        )
        status_bar.addPermanentWidget(self.statusMsgLabel)

        # Set Initial Connection Status
        self.updateConnectionStatus(False)

        # --- Context Menu for Details Table ---
        self.tableWidgetServiceDetails.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tableWidgetServiceDetails.customContextMenuRequested.connect(self.showDetailsContextMenu)
        # --- End Context Menu for Details Table ---

        schedule_ui_task(self.initialize_table_models, 100)

    def showHelpManual(self):
        help_dialog = QtWidgets.QDialog(self)
        help_dialog.setWindowTitle("VIPrestore - User Manual")
        help_dialog.resize(800, 600)
        
        layout = QtWidgets.QVBoxLayout(help_dialog)
        
        # Use QTextBrowser for rich text display with markdown support
        text_browser = QtWidgets.QTextBrowser(help_dialog)
        text_browser.setOpenExternalLinks(True)
        
        # Load the manual content
        manual_path = resource_path("manual.md")
        try:
            with open(manual_path, "r", encoding="utf-8") as f:
                manual_content = f.read()
            text_browser.setMarkdown(manual_content)
        except Exception as e:
            text_browser.setPlainText(f"Error loading manual: {str(e)}")
        
        layout.addWidget(text_browser)
        
        # Add a close button
        close_button = QtWidgets.QPushButton("Close", help_dialog)
        close_button.clicked.connect(help_dialog.close)
        layout.addWidget(close_button)
        
        help_dialog.exec()

    def showContextMenu(self, position):
        # Create a context menu
        context_menu = QtWidgets.QMenu(self)

        # Create a "Save Selected" action for the context menu
        save_action = QtGui.QAction("Save Selected Services", self)
        save_action.triggered.connect(lambda: asyncio.create_task(self.saveSelectedServices()))
        context_menu.addAction(save_action)

        # --- Copy Cell Action ---
        copy_action = QtGui.QAction("Copy Cell", self)
        copy_action.triggered.connect(lambda: self.copyCell(self.tableViewServices))
        context_menu.addAction(copy_action)
        # --- End Copy Cell Action ---

        # Check if there's a valid selection
        indexes = self.tableViewServices.selectionModel().selectedRows()
        if not indexes:
            save_action.setEnabled(False)

        # Show the context menu at the mouse position
        context_menu.exec(self.tableViewServices.viewport().mapToGlobal(position))

    def showDetailsContextMenu(self, position):
        """Shows the context menu for the service details table."""
        # Add logging for debugging
        logger.debug("showDetailsContextMenu() called")
        logger.debug(f"Context menu requested at position: {position}")

        context_menu = QtWidgets.QMenu(self)

        # --- Copy Cell Action ---
        copy_action = QtGui.QAction("Copy Cell", self)
        copy_action.triggered.connect(lambda: self.copyCell(self.tableWidgetServiceDetails))
        context_menu.addAction(copy_action)
        # --- End Copy Cell Action ---

        # Check which cell was clicked
        index = self.tableWidgetServiceDetails.indexAt(position)
        if index.isValid():
            item = self.tableWidgetServiceDetails.item(index.row(), 0)
            logger.debug(f"Clicked cell info: Row={index.row()}, Col={index.column()}, Text='{item.text() if item else 'None'}'")

        logger.debug("Displaying details context menu now.")
        context_menu.exec(self.tableWidgetServiceDetails.viewport().mapToGlobal(position))
        logger.debug("Context menu closed.")

    def ssl_exception_handler(self, message: str) -> bool:
        """Handle SSL certificate exceptions by prompting the user in a thread-safe way"""
        # We need to use Qt's event loop to call back to the main thread
        event_loop = QtCore.QEventLoop()
        result = [False]  # Use a list to store the result from the inner function
        
        # This will run on the main thread
        def show_dialog():
            reply = QtWidgets.QMessageBox.question(
                self,
                "SSL Certificate Warning",
                message,
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No  # Default is No (safer)
            )
            result[0] = reply == QtWidgets.QMessageBox.StandardButton.Yes
            event_loop.quit()
        
        # Schedule the dialog to be shown on the main thread
        QtCore.QMetaObject.invokeMethod(self, "showSslWarningDialog", 
                                    QtCore.Qt.ConnectionType.QueuedConnection,
                                    QtCore.Q_ARG(str, message),
                                    QtCore.Q_ARG(object, result),
                                    QtCore.Q_ARG(object, event_loop))
        
        # Wait for the dialog to be handled
        event_loop.exec()
        return result[0]

    # Add this slot method to MainWindow
    @QtCore.pyqtSlot(str, object, object)
    def showSslWarningDialog(self, message, result_list, event_loop):
        """Slot to show SSL warning dialog on the main thread"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "SSL Certificate Warning",
            message,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        result_list[0] = reply == QtWidgets.QMessageBox.StandardButton.Yes
        event_loop.quit()

    def _format_timestamp(self, timestamp):
        """Converts a timestamp into a readable date format."""
        if not timestamp:
            return "N/A"
        try:
            dt_val = datetime.fromtimestamp(int(timestamp) / 1000)
            return dt_val.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(timestamp)

    def copyCell(self, table_widget):
        """Copies the content of the currently selected cell to the clipboard."""
        if table_widget == self.tableViewServices:
            # Handle service table
            selected_indexes = table_widget.selectionModel().selectedIndexes()
            if selected_indexes:
                index = selected_indexes[0]
                # Use filterProxy for service table
                text = self.filterProxy.data(index, QtCore.Qt.ItemDataRole.DisplayRole)
                QtWidgets.QApplication.clipboard().setText(str(text))

        elif table_widget == self.tableWidgetServiceDetails:
             # Handle details table
            selected_indexes = table_widget.selectedIndexes()
            if selected_indexes:
                index = selected_indexes[0]
                text = table_widget.model().data(index, QtCore.Qt.ItemDataRole.DisplayRole)
                QtWidgets.QApplication.clipboard().setText(str(text))

    async def cancelSelectedServices(self):
        indexes = self.tableViewServices.selectionModel().selectedRows()
        if not indexes:
            QtWidgets.QMessageBox.information(
                self,
                "No Selection",
                "Please select at least one service to cancel."
            )
            return

        # Confirm with the user
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Cancellation",
            "Are you sure you want to cancel the selected service(s)?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No  # Default button
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        service_ids = []
        for index in indexes:
            service_id = self.filterProxy.index(index.row(), 0).data()
            service_ids.append(service_id)

        try:
            result = await self.service_manager.cancel_services(service_ids)
            
            success_count = result["success_count"]
            total = result["total"]
            failed_services = result["failed_services"]
            
            msg = f"Successfully cancelled {success_count} of {total} service(s).\n"
            if failed_services:
                msg += "Failed to cancel:\n"
                for service_id, error in failed_services:
                    msg += f"- {service_id}: {error}\n"
            
            QtWidgets.QMessageBox.information(self, "Cancellation Results", msg)
        except ServiceManagerError as e:
            QtWidgets.QMessageBox.critical(self, "Cancel Error", str(e))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Unexpected Error", f"An unexpected error occurred: {str(e)}")
        finally:
            # Always refresh, even if there's an error
            await self.refreshServicesAsync()

    def closeEvent(self, event: QtGui.QCloseEvent):
        """
        When the main window is about to close, stop the sessionTimer
        so it doesn't keep calling checkSession() on a destroyed window.
        """
        if self.sessionTimer.isActive():
            self.sessionTimer.stop()
        super().closeEvent(event)

    def update_table_fonts(self):
        """Update table fonts explicitly"""
        if self.bold_font_family:
            print(f"Updating table fonts to: {self.bold_font_family}")  # Debug print
            bold_font = QtGui.QFont(self.bold_font_family, 10, QtGui.QFont.Weight.Bold)
            self.tableViewServices.setFont(bold_font)
            self.tableWidgetServiceDetails.setFont(bold_font)

    def initialize_table_models(self):
        """Lazily initialize table models and related data structures.
        Called after the window is visible to improve startup time."""
        
        # Configure Service View Table - deferred initialization
        self.serviceModel = QtGui.QStandardItemModel(self)
        self.filterProxy = ServicesFilterProxy(self)
        self.filterProxy.setSourceModel(self.serviceModel)
        self.tableViewServices.setModel(self.filterProxy)
        self.tableViewServices.selectionModel().selectionChanged.connect(self.onServiceSelectionChanged)
        
        # Log completion
        logger.debug("Table models initialized")

    def set_bold_font_family(self, font_family):
        print(f"Setting bold font family to: {font_family}")
        self.bold_font_family = font_family
        if self.bold_font_family:
            table_style = f"""
                QTableView, QTableWidget {{
                    background-color: #eeeeee;
                    alternate-background-color: #dddddd;
                    color: black;
                    font-family: "{self.bold_font_family}";
                    font-weight: bold;
                }}
                QTableView::item:selected, QTableWidget::item:selected {{
                    background-color: #a1aaff;
                    color: black;
                }}
            """
            print("Applying table style with bold font")
            # Remove this line to avoid affecting the entire window:
            # self.setStyleSheet(table_style)
            self.tableWidgetServiceDetails.setStyleSheet(table_style)
            self.tableViewServices.setStyleSheet(table_style)
            
            # Force update of table fonts
            self.tableViewServices.setFont(QtGui.QFont(self.bold_font_family, 10, QtGui.QFont.Weight.Bold))
            self.tableWidgetServiceDetails.setFont(QtGui.QFont(self.bold_font_family, 10, QtGui.QFont.Weight.Bold))

    def setSplitterPlacement(self):
        splitter = self.findChild(QtWidgets.QSplitter, "splitterCentral")
        if splitter is None:
            print("Warning: QSplitter with objectName 'splitterCentral' not found. Please check your .ui file.")
            return
        splitter.setSizes([400, 340])

    async def doLogin(self):
        while True:
            dlg = LoginDialog()
            if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                break
            server_url, username, password = dlg.getCredentials()
            self.server_url = server_url  # Store for later reference
            self.client = VideoIPathClient(
                server_url,
                verify_ssl=True,
                ssl_exception_callback=self.ssl_exception_handler  # Add this parameter
            )
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(self.executor, self.client.login, username, password)
                self.service_manager.set_client(self.client)
                session_info = await loop.run_in_executor(self.executor, lambda: self.client.get("/api/_session"))
                user_data = session_info.get("userCtx", {})
                username_disp = user_data.get("name", "unknown")
                roles = user_data.get("roles", [])
                roles_str = ", ".join(roles) if roles else "No roles"
                user_status_text = f"User: {username_disp} | Role(s): {roles_str}"
                self.updateUserStatus(user_status_text)
                print(f"Logged-in User: {username_disp}")
                print(f"Roles: {roles_str}")
            except VideoIPathClientError as e:
                QtWidgets.QMessageBox.critical(self, "Login Failed", str(e))
                self.client = None
                self.updateConnectionStatus(False)
                continue
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Login Failed", str(e))
                self.client = None
                self.updateConnectionStatus(False)
                continue

            # Determine SSL verification status based on client settings.
            ssl_verified = self.client.session.verify if server_url.startswith("https://") else False
            self.updateConnectionStatus(True, ssl_verified)
            await self.refreshServicesAsync()
            break

    def updateUserStatus(self, text):
        self.labelUserInfo.setText(text)

    def doLogout(self):
        if self.client:
            try:
                self.client.logout()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Logout Error", str(e))
        self.client = None
        self.service_manager.set_client(None)
        self.updateConnectionStatus(False)
        self.clearAppState()

    def clearAppState(self):
        # Clear service table and details
        self.serviceModel.clear()
        self.tableWidgetServiceDetails.setRowCount(0)
        self.tableViewServices.clearSelection()
        self.currentServices.clear()

        # Reset filters
        self.lineEditSourceFilter.clear()
        self.lineEditDestinationFilter.clear()
        self.checkBoxEnableTimeFilter.setChecked(False)
        today = QtCore.QDate.currentDate()
        self.dateTimeEditStart.setDateTime(QtCore.QDateTime(today, QtCore.QTime(0, 0, 0)))
        self.dateTimeEditEnd.setDateTime(QtCore.QDateTime(today, QtCore.QTime(23, 59, 59)))

        # Clear profile checkboxes
        while self.layoutProfiles.count() > 0:
            item = self.layoutProfiles.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.profileCheckBoxes.clear()

    async def saveSelectedServices(self):
        indexes = self.tableViewServices.selectionModel().selectedRows()
        if not indexes:
            QtWidgets.QMessageBox.information(
                self,
                "No Selection",
                "Please select at least one service to save."
            )
            return

        service_ids = []
        for index in indexes:
            service_id = self.filterProxy.index(index.row(), 0).data()
            service_ids.append(service_id)

        try:
            modern_services_to_save = self.service_manager.prepare_services_for_export(service_ids)
            
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save Modern Services",
                "",
                "JSON Files (*.json)"
            )
            
            if not file_path:
                return

            await self.service_manager.save_services(modern_services_to_save, file_path)
            
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"Saved {len(modern_services_to_save)} service(s) to {file_path}."
            )
        except ServiceManagerError as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error Saving Services",
                str(e)
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred: {str(e)}"
            )

    async def load_services_from_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Services File",
            "",
            "JSON Files (*.json)"
        )

        if not file_path:
            return None

        try:
            return await self.service_manager.load_services(file_path)
        except ServiceManagerError as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error Loading File",
                str(e)
            )
            return None

    async def load_and_create_services(self):
        """
        Loads modern-format services from a file, presents them in a confirmation dialog,
        and then creates the selected services via the modern API.
        """
        services = await self.load_services_from_file()  # Add await here
        if not services:
            return

        dlg = LoadServicesDialog(services, self)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        selected_ids = dlg.selected_services
        if not selected_ids:
            QtWidgets.QMessageBox.information(
                self,
                "No Services Selected",
                "No services were selected for creation."
            )
            return

        await self.create_services_from_file(services, selected_ids)

    async def create_services_from_file(self, services, selected_ids):
        try:
            result = await self.service_manager.create_services(services, selected_ids)
            
            success_count = result["success_count"]
            total = result["total"]
            failed_services = result["failed_services"]
            
            msg = f"Successfully created {success_count} service(s).\n"
            if failed_services:
                failure_count = len(failed_services)
                msg += f"Failed to create {failure_count} service(s):\n"
                for service_id, error in failed_services:
                    msg += f"- {service_id}: {error}\n"
            else:
                msg += "All services were created successfully."
            
            QtWidgets.QMessageBox.information(
                self,
                "Service Creation Results",
                msg
            )
            
            # Automatically refresh the services list in the GUI
            await self.refreshServicesAsync()
        except ServiceManagerError as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Service Creation Error",
                str(e)
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred: {str(e)}"
            )

    def editSystems(self):
        from systems_editor_dialog import SystemsEditorDialog
        config_dir = get_user_config_dir()
        dlg = SystemsEditorDialog(self, config_dir=config_dir)
        dlg.exec()

    def updateConnectionStatus(self, connected: bool, ssl_verified: bool = True):
        if connected:
            if hasattr(self, 'server_url'):
                if self.server_url.startswith("https://"):
                    if ssl_verified:
                        self.frameConnectionIndicator.setStyleSheet("background-color: green;")
                        self.labelConnectionStatusText.setText("Connected (HTTPS, valid SSL)")
                    else:
                        self.frameConnectionIndicator.setStyleSheet("background-color: orange;")
                        self.labelConnectionStatusText.setText("Connected (HTTPS, invalid SSL)")
                elif self.server_url.startswith("http://"):
                    self.frameConnectionIndicator.setStyleSheet("background-color: red;")
                    self.labelConnectionStatusText.setText("Connected (HTTP, not secure)")
                else: # Added this for completeness
                    self.frameConnectionIndicator.setStyleSheet("background-color: green;")
                    self.labelConnectionStatusText.setText("Connected (Unknown Protocol)")
            else:  # Handle case where server_url is not set, but connected is True
                self.frameConnectionIndicator.setStyleSheet("background-color: yellow;")  # Distinct color
                self.labelConnectionStatusText.setText("Connected (Server URL not set)")
        else:
            self.frameConnectionIndicator.setStyleSheet("background-color: grey;")
            self.labelConnectionStatusText.setText("No Connection")
        
        self.actionLogout.setEnabled(connected)
        self.actionSaveSelectedServices.setEnabled(connected)
        self.actionCancelSelectedServices.setEnabled(connected) # Important: Enable/disable the new action
        
        # Show or hide user role and service count based on connection state.
        self.labelUserInfo.setVisible(connected)
        self.labelServiceCount.setVisible(connected)
        
        # Always hide spinner when not loading.
        self.loadingLabel.setVisible(False)


    def showAbout(self):
        """Shows the About dialog with application information."""
        version = get_version()

        dlg = QtWidgets.QDialog()
        uic.loadUi(resource_path("about_dialog.ui"), dlg)

        # Set window title & fixed size for a polished look
        dlg.setWindowTitle(strings.DIALOG_TITLE_ABOUT)
        dlg.setFixedSize(400, 300)  # Adjust to fit contents

        # Load the application icon
        icon_path = resource_path("logos/viprestore_icon.png")
        pixmap = QtGui.QPixmap(icon_path).scaled(100, 100, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)

        # Update QLabel for the logo
        logo_label = dlg.findChild(QtWidgets.QLabel, "labelLogo")
        if logo_label:
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Update version information
        version = get_version()
        label = dlg.findChild(QtWidgets.QLabel, "labelAbout")
        if label:
            about_text = f"""
            <h1 style="color:#0078D7; font-size: 22px; font-weight: bold; margin-bottom: 5px;">VIPrestore</h1>
            <p style="font-size: 14px; color: #555;">Version {version}</p>
            <p style="font-size: 12px; color: #777; margin-top: 5px;">Copyright © 2025</p>
            """
            label.setText(about_text)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        dlg.exec()


    async def _onDetailsCellClicked(self, row: int, col: int):
        if col != 1:
            return

        item = self.tableWidgetServiceDetails.item(row, col)
        if not item:
            return

        parent_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not parent_id:
            return

        try:
            group_svc = await self.service_manager.fetch_group_connection(parent_id)
            if not group_svc:
                QtWidgets.QMessageBox.information(
                    self,
                    "Group Parent",
                    f"Could not locate group parent '{parent_id}' in the remote system."
                )
                return
            
            dlg = GroupDetailDialog(parent_id, group_svc, parent=self)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to fetch group connection: {e}")

    async def refreshServicesAsync(self):
        if not self.client:
            QtWidgets.QMessageBox.information(
                self, "Not Connected", "Not connected to a remote VideoIPath system."
            )
            return
        self.startLoadingAnimation()
        self.statusMsgLabel.setText("Refreshing services...")
        try:
            result = await self.service_manager.fetch_services_data()
            self.onServicesRetrieved(result)
        except ServiceManagerError as e:
            self.onServicesError(str(e))
        except Exception as e:
            self.onServicesError(f"Unexpected error: {str(e)}")
        finally:
            self.stopLoadingAnimation()
            self.statusMsgLabel.setText("Services refreshed")
            await asyncio.sleep(3)
            self.statusMsgLabel.setText("")

    async def _fetchServicesData(self) -> dict:
        future_normal = self._run_api_call(self.client.retrieve_services)
        future_profiles = self._run_api_call(self.client.get_profiles)
        future_endpoint_map = self._run_api_call(self.client.get_endpoint_map)  # see next refactoring
        future_group = self._run_api_call(self.client.retrieve_group_connections)
        
        normal_services, profiles_resp, endpoint_map, group_res = await asyncio.gather(
            future_normal, future_profiles, future_endpoint_map, future_group
        )
        
        return {
            "normal_services": normal_services,
            "profiles_resp": profiles_resp,
            "endpoint_map": endpoint_map,
            "group_res": group_res,
        }

    def _processServicesData(self, responses: dict) -> dict:
        normal_services = responses["normal_services"]
        profiles_resp = responses["profiles_resp"]
        endpoint_map = responses["endpoint_map"]
        group_res = responses["group_res"]
        group_services, child_to_group = group_res

        merged = {}
        merged.update(normal_services)
        merged.update(group_services)
        for svc_id, svc_obj in normal_services.items():
            if svc_id in child_to_group:
                svc_obj["groupParent"] = child_to_group[svc_id]

        used_profile_ids = set()
        for svc_data in merged.values():
            booking = svc_data.get("booking", {})
            pid = booking.get("profile", "")
            if pid:
                used_profile_ids.add(pid)

        prof_data = profiles_resp.get("data", {}).get("config", {}).get("profiles", {})
        profile_mapping = {pid: info.get("name", pid) for pid, info in prof_data.items()}

        return {
            "merged": merged,
            "used_profile_ids": used_profile_ids,
            "profile_mapping": profile_mapping,
            "endpoint_map": endpoint_map,
            "child_to_group": child_to_group,
        }

    async def _run_api_call(self, func, *args, timeout=10, retries=2):
        loop = asyncio.get_running_loop()
        for attempt in range(retries):
            try:
                return await asyncio.wait_for(loop.run_in_executor(self.executor, func, *args), timeout)
            except Exception as e:
                if attempt == retries - 1:
                    raise e

    def startLoadingAnimation(self):
        if hasattr(self, "loadingMovie"):
            self.loadingLabel.setVisible(True)
            self.loadingMovie.start()

    def stopLoadingAnimation(self):
        if hasattr(self, "loadingMovie"):
            self.loadingMovie.stop()
            self.loadingLabel.setVisible(False)

    def onServicesRetrieved(self, result):
        merged = result["merged"]
        used_profile_ids = result["used_profile_ids"]
        
        # Create a model with six columns in the specified order
        new_model = QtGui.QStandardItemModel(self)
        new_model.setHorizontalHeaderLabels(["Service ID", "Source", "Destination", "Profile", "Created By", "Start"])
        
        # Only add non-group based services to the table
        for svc_id, svc_data in merged.items():
            if svc_data.get("type", "") == "group":
                continue  # Skip group-based connections
            booking = svc_data.get("booking", {})
            label = booking.get("descriptor", {}).get("label", "")
            match = re.match(r'(.+?)\s*->\s*(.+)', label)
            if match:
                src = match.group(1).strip()
                dst = match.group(2).strip()
            else:
                src = label
                dst = ""
            pid = booking.get("profile", "")
            prof_name = self.service_manager.profile_mapping.get(pid, pid)
            created_by = booking.get("createdBy", "")
            
            # Process start time: store display text and raw timestamp for sorting
            start_ts = booking.get("start")
            start_str = ""
            timestamp_value = None
            if start_ts:
                try:
                    dt_val = datetime.fromtimestamp(int(start_ts) / 1000)
                    start_str = dt_val.strftime("%d-%m-%Y - %H:%M:%S")
                    timestamp_value = int(start_ts)
                except Exception:
                    pass
            
            # Create QStandardItem for the Start column and store the raw timestamp in UserRole
            start_item = QtGui.QStandardItem(start_str)
            if timestamp_value is not None:
                start_item.setData(timestamp_value, QtCore.Qt.ItemDataRole.UserRole)
            
            row_items = [
                QtGui.QStandardItem(str(booking.get("serviceId", svc_id))),
                QtGui.QStandardItem(src),
                QtGui.QStandardItem(dst),
                QtGui.QStandardItem(str(prof_name)),
                QtGui.QStandardItem(created_by),
                start_item,
            ]
            new_model.appendRow(row_items)
        
        self.filterProxy.setSourceModel(new_model)
        self.serviceModel = new_model

        self._rebuildProfileCheckboxes(used_profile_ids)
        self._setTableViewColumnWidths()
        
        # Update the total services count
        total_services = len([svc for svc in merged.values() if svc.get("type", "") != "group"])
        self.labelServiceCount.setText(f"Total services: {total_services}")

        self.update_table_fonts()

    def onServicesError(self, error_msg):
        QtWidgets.QMessageBox.critical(self, "Error Refreshing Services", error_msg)
        self.statusMsgLabel.setText("Error refreshing services")
        schedule_ui_task(lambda: self.statusMsgLabel.setText(""), 3000)

    def displayServiceDetails(self, svc_id: str):
        self.tableWidgetServiceDetails.setRowCount(0)
        
        try:
            details = self.service_manager.get_service_details(svc_id)
            
            for field, val in details:
                r = self.tableWidgetServiceDetails.rowCount()
                self.tableWidgetServiceDetails.insertRow(r)
                
                item_field = QtWidgets.QTableWidgetItem(field)
                item_field.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
                self.tableWidgetServiceDetails.setItem(r, 0, item_field)
                
                item_val = QtWidgets.QTableWidgetItem(val)
                item_val.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
                
                # Handle group parent links
                is_link = False
                user_data = None
                if field == "Group Parent":
                    is_link = True
                    user_data = val
                
                if is_link:
                    brush = QtGui.QBrush(QtGui.QColor("blue"))
                    item_val.setForeground(brush)
                    font = item_val.font()
                    font.setUnderline(True)
                    item_val.setFont(font)
                    if user_data is not None:
                        item_val.setData(QtCore.Qt.ItemDataRole.UserRole, user_data)
                        
                self.tableWidgetServiceDetails.setItem(r, 1, item_val)
        except ServiceManagerError as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))

    def _setTableViewColumnWidths(self):
        header = self.tableViewServices.horizontalHeader()
        # Set all columns except the last one (Start) to Interactive.
        for col in range(self.serviceModel.columnCount() - 1):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Interactive)
        # Set the last column ("Start") to stretch.
        header.setSectionResizeMode(self.serviceModel.columnCount() - 1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tableViewServices.setColumnWidth(0, 90)   # Service ID
        self.tableViewServices.setColumnWidth(1, 240)   # Source
        self.tableViewServices.setColumnWidth(2, 240)   # Destination
        self.tableViewServices.setColumnWidth(3, 100)   # Profile
        self.tableViewServices.setColumnWidth(4, 120)   # Created By
        #self.tableViewServices.setColumnWidth(5, 150)   # Start

    def _addServiceToTable(self, svc_id: str, svc_data: dict):
        self.currentServices[svc_id] = svc_data

        booking = svc_data.get("booking", {})
        desc = booking.get("descriptor", {})
        label = desc.get("label","")

        match = re.match(r'(.+?)\s*->\s*(.+)', label)
        if match:
            src = match.group(1).strip()
            dst = match.group(2).strip()
        else:
            src = label
            dst = ""

        start_ts = booking.get("start")
        start_str = ""
        if start_ts:
            try:
                dt_val = datetime.fromtimestamp(int(start_ts)/1000)
                start_str = dt_val.strftime("%Y-%m-%d %H:%M:%S")  # updated format
            except Exception:
                pass

        pid = booking.get("profile","")
        prof_name = self._profile_mapping.get(pid, pid)

        row_items = [
            QtGui.QStandardItem(str(booking.get("serviceId", svc_id))),
            QtGui.QStandardItem(src),
            QtGui.QStandardItem(dst),
            QtGui.QStandardItem(start_str),
            QtGui.QStandardItem(str(prof_name)),
        ]
        self.serviceModel.appendRow(row_items)

    def checkSession(self):
        if not self.client:
            return
        try:
            if not self.client.validate_session():
                self.updateConnectionStatus(False)
                self.client = None
                QtWidgets.QMessageBox.warning(self, "Session Expired", "Your session has expired. Please log in again.")
        except VideoIPathClientError as e:
            self.updateConnectionStatus(False)
            self.client = None
            QtWidgets.QMessageBox.warning(self, "Session Check Failed", str(e))

    def _rebuildProfileCheckboxes(self, used_profile_ids):
        while self.layoutProfiles.count() > 0:
            item = self.layoutProfiles.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.profileCheckBoxes.clear()

        sorted_pids = sorted(used_profile_ids, 
                        key=lambda pid: self.service_manager.profile_mapping.get(pid, pid).lower())
        for pid in sorted_pids:
            pname = self.service_manager.profile_mapping.get(pid, pid)
            cb = QtWidgets.QCheckBox(pname, self.scrollAreaWidgetProfilesFilters)
            cb.stateChanged.connect(self.onProfilesFilterChanged)
            self.layoutProfiles.addWidget(cb)
            self.profileCheckBoxes.append((cb, pname))

    def onSourceFilterChanged(self, text: str):
        self.filterProxy.setSourceFilterText(text)
        schedule_ui_task(self.updateServiceSelection)

    def onDestinationFilterChanged(self, text: str):
        self.filterProxy.setDestinationFilterText(text)
        schedule_ui_task(self.updateServiceSelection)

    def onTimeFilterChanged(self):
        if self.checkBoxEnableTimeFilter.isChecked():
            start_dt = self.dateTimeEditStart.dateTime()
            end_dt = self.dateTimeEditEnd.dateTime()
            if not start_dt.isValid():
                start_dt = None
            if not end_dt.isValid():
                end_dt = None
        else:
            start_dt = None
            end_dt = None
        self.filterProxy.setStartRange(start_dt, end_dt)
        schedule_ui_task(self.updateServiceSelection)

    def onProfilesFilterChanged(self):
        chosen = []
        for cb, pname in self.profileCheckBoxes:
            if cb.isChecked():
                chosen.append(pname)
        self.filterProxy.setActiveProfiles(chosen)
        schedule_ui_task(self.updateServiceSelection)

    def onResetFilters(self):
        self.lineEditSourceFilter.clear()
        self.lineEditDestinationFilter.clear()
        self.checkBoxEnableTimeFilter.setChecked(False)
        today = QtCore.QDate.currentDate()
        self.dateTimeEditStart.setDateTime(QtCore.QDateTime(today, QtCore.QTime(0, 0, 0)))
        self.dateTimeEditEnd.setDateTime(QtCore.QDateTime(today, QtCore.QTime(23, 59, 59)))
        for cb, _ in self.profileCheckBoxes:
            cb.setChecked(False)
        schedule_ui_task(self.updateServiceSelection)

    def onServiceClicked(self, index: QtCore.QModelIndex):
        selected_indexes = self.tableViewServices.selectionModel().selectedRows()
        if len(selected_indexes) != 1:
            return
        svc_id = self.filterProxy.index(selected_indexes[0].row(), 0).data()
        self.displayServiceDetails(svc_id)

    def onServiceSelectionChanged(self, selected, deselected):
        indexes = self.tableViewServices.selectionModel().selectedRows()
        if len(indexes) == 1:
            row = indexes[0].row()
            svc_id = self.filterProxy.index(row, 0).data()
            self.displayServiceDetails(svc_id)
        else:
            self.tableWidgetServiceDetails.setRowCount(0)

    def updateServiceSelection(self):
        selection = self.tableViewServices.selectionModel().selectedRows()
        if not selection:
            self.tableWidgetServiceDetails.setRowCount(0)
            return

        selected_index = selection[0]
        service_id = self.filterProxy.index(selected_index.row(), 0).data()

        found = False
        new_index = None
        for row in range(self.filterProxy.rowCount()):
            idx = self.filterProxy.index(row, 0)
            if idx.data() == service_id:
                found = True
                new_index = idx
                break

        if not found:
            self.tableViewServices.clearSelection()
            self.tableWidgetServiceDetails.setRowCount(0)
        else:
            if selected_index.row() != new_index.row():
                self.tableViewServices.selectionModel().select(
                    new_index,
                    QtCore.QItemSelectionModel.ClearAndSelect | QtCore.QItemSelectionModel.Rows
                )
            self.onServiceSelectionChanged(None, None)

    def clearServiceSelection(self):
        self.tableViewServices.clearSelection()
        self.tableWidgetServiceDetails.setRowCount(0)

def main():
    """Main application entry point."""
    # Configure logging first
    log_path = configure_logging()
    logger = logging.getLogger(__name__)
    
    logger.debug("Starting application and creating QApplication...")
    app = QtWidgets.QApplication(sys.argv)
    
    # Set up exception handler
    exception_handler.set_application(app)
    exception_handler.install_global_handler()
    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # Initialize splash screen
    splash_manager = SplashManager(app)
    splash_manager.show()
    
    # Create the main window (hidden)
    logger.debug("Creating MainWindow instance (hidden).")
    main_window = MainWindow()
    
    # Update exception handler with main window reference
    exception_handler.set_application(app, main_window)
    
    splash_manager.show()
    splash_manager.finish(main_window)
    
    # Apply essential styling first
    styling.setup_essential_styling(app, main_window)
    
    # Ensure the remote systems configuration is in a user-writable location.
    # This is a file operation that could be done after showing the window
    schedule_ui_task(ensure_remote_systems_config, 500)
    
    # Check for updates using the ApplicationUpdater
    updater = ApplicationUpdater(main_window, splash_manager)
    updater.check_for_updates_async()
    
    # Apply complete styling after the window is shown
    schedule_ui_task(lambda: styling.setup_complete_styling(app, main_window), 100)
    
    logger.debug("Starting the event loop.")
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()