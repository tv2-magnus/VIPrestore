import sys
import os
import re
import json
import asyncio
from datetime import datetime, timedelta
from qasync import QEventLoop
from PyQt6.QtGui import QGuiApplication
from PyQt6 import QtWidgets, uic, QtGui, QtCore
from PyQt6.QtCore import QSize
from vipclient import VideoIPathClient, VideoIPathClientError
from login_dialog import LoginDialog
from load_services_dialog import LoadServicesDialog
from group_detail_dialog import GroupDetailDialog
from PyQt6.QtCore import Qt
from concurrent.futures import ThreadPoolExecutor
from services_filter import ServicesFilterProxy
import socket
import ssl
import urllib.parse

def resource_path(relative_path):
    """Get the absolute path to a resource, supporting PyInstaller."""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

def set_app_icon(app, window):
    """
    Sets the application icon using a high-quality multi-size .ico on Windows,
    and .png on other platforms. Also sets any OS-specific attributes like
    the Windows app user model ID.
    """
    from PyQt6.QtGui import QIcon, QGuiApplication
    from PyQt6 import QtCore
    import ctypes

    # Determine icon path based on platform
    if sys.platform == 'win32':
        icon_path = resource_path(os.path.join("logos", "viprestore_icon.ico"))
    else:
        icon_path = resource_path(os.path.join("logos", "viprestore_icon.png"))

    # Create and set the icon if it exists
    if os.path.exists(icon_path):
        icon = QIcon(icon_path)
        app.setWindowIcon(icon)
        window.setWindowIcon(icon)

    # OS-specific settings
    if sys.platform.startswith('linux'):
        app.setDesktopFileName('viprestore.desktop')
    elif sys.platform == 'win32':
        myappid = 'mycompany.viprestore.client.1.0'  # must be unique
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

def load_custom_fonts():
    """Load all required Roboto font variants and return a dict of font families."""
    from PyQt6 import QtGui
    import os
    
    font_files = {
        'regular': 'Roboto-Regular.ttf',
        'bold': 'Roboto-Bold.ttf',
    }

    loaded_fonts = {}
    fonts_dir = resource_path("fonts")
    
    # Debug information
    print(f"Looking for fonts in: {fonts_dir}")
    print(f"Full path to Regular: {os.path.join(fonts_dir, 'Roboto-Regular.ttf')}")
    print(f"Full path to Bold: {os.path.join(fonts_dir, 'Roboto-Bold.ttf')}")

    for variant, filename in font_files.items():
        font_path = os.path.join(fonts_dir, filename)
        if not os.path.exists(font_path):
            print(f"Warning: Font file not found: {font_path}")
            continue

        font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print(f"Failed to load font: {filename}")
            continue

        families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded_fonts[variant] = families[0]
            print(f"Successfully loaded font: {filename}")
        else:
            print(f"No font families found for: {filename}")

    return loaded_fonts

def verify_ssl_cert(server_url: str) -> bool:
    parsed = urllib.parse.urlparse(server_url)
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                return True
    except ssl.SSLError:
        return False
    except Exception:
        return False

class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(dict)
    error = QtCore.pyqtSignal(str)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("main.ui", self)

        # Add this right after super().__init__()
        self.bold_font_family = None  # Will be set from main()
        
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
        
        self.actionSettings = QtGui.QAction("Settings", self)
        self.actionSettings.setShortcut("Ctrl+,")
        
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
        self.menuHelp.addAction(self.actionSettings)
        
        # Connect Action Signals
        self.actionLogin.triggered.connect(lambda: asyncio.create_task(self.doLogin()))
        self.actionLogout.triggered.connect(self.doLogout)
        self.actionLoadServices.triggered.connect(lambda: asyncio.create_task(self.load_and_create_services()))
        self.actionSaveSelectedServices.triggered.connect(self.saveSelectedServices)
        self.actionExit.triggered.connect(self.close)
        self.actionRefresh.triggered.connect(lambda: asyncio.create_task(self.refreshServicesAsync()))
        self.actionEditSystems.triggered.connect(self.editSystems)
        self.actionAbout.triggered.connect(self.showAbout)
        self.actionSettings.triggered.connect(self.showSettings)
        
        self.setSplitterPlacement()
        
        # Instance Variables
        self.client = None
        self._profile_mapping = {}
        self._endpoint_map = {}
        self.profileCheckBoxes = []
        self.currentServices = {}
        
        # Executor for blocking calls
        self.executor = ThreadPoolExecutor()
        
        # Configure Service View Table
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
        self.labelServiceCount.setVisible(False)  # Hide when no connection

        # User info (name and role)
        self.labelUserInfo = QtWidgets.QLabel("User: N/A | Role: N/A")
        status_bar.addWidget(self.labelUserInfo)

        # Loading spinner
        self.loadingLabel = QtWidgets.QLabel("")
        self.loadingMovie = QtGui.QMovie("spinner.gif")
        self.loadingLabel.setMovie(self.loadingMovie)
        status_bar.addWidget(self.loadingLabel)
        self.loadingLabel.setVisible(False)

        # Temporary status message on the far right
        self.statusMsgLabel = QtWidgets.QLabel("")
        status_bar.addPermanentWidget(self.statusMsgLabel)

        # Set Initial Connection Status
        self.updateConnectionStatus(False)

    def update_table_fonts(self):
        """Update table fonts explicitly"""
        if self.bold_font_family:
            print(f"Updating table fonts to: {self.bold_font_family}")  # Debug print
            bold_font = QtGui.QFont(self.bold_font_family, 10, QtGui.QFont.Weight.Bold)
            self.tableViewServices.setFont(bold_font)
            self.tableWidgetServiceDetails.setFont(bold_font)

    def set_bold_font_family(self, font_family):
        """Set the bold font family and update all table styles"""
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
            self.setStyleSheet(table_style)
            self.tableWidgetServiceDetails.setStyleSheet(table_style)
            
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
            self.server_url = server_url  # Store for later reference in updateConnectionStatus
            self.client = VideoIPathClient(server_url)
            loop = asyncio.get_running_loop()
            try:
                # If using HTTPS, verify the SSL certificate.
                if server_url.startswith("https://"):
                    ssl_verified = await loop.run_in_executor(self.executor, verify_ssl_cert, server_url)
                else:
                    ssl_verified = False  # HTTP has no SSL verification.
                
                await loop.run_in_executor(self.executor, self.client.login, username, password)
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

    def saveSelectedServices(self):
        indexes = self.tableViewServices.selectionModel().selectedRows()
        if not indexes:
            QtWidgets.QMessageBox.information(
                self,
                "No Selection",
                "Please select at least one service to save."
            )
            return

        modern_services_to_save = {}
        
        for index in indexes:
            service_id = self.filterProxy.index(index.row(), 0).data()
            service_data = self.currentServices.get(service_id)
            
            if service_data:
                booking = service_data.get("booking", {})
                
                # Parse timestamps
                try:
                    start_ts = int(booking.get("start", 0))
                except:
                    start_ts = 0
                    
                try:
                    end_ts = int(booking.get("end", 0))
                except:
                    end_ts = 0

                # Extract device labels from descriptor label if formatted as "Source -> Destination"
                descriptor = booking.get("descriptor", {})
                descriptor_label = descriptor.get("label", "")
                
                if "->" in descriptor_label:
                    parts = descriptor_label.split("->")
                    from_label = parts[0].strip()
                    to_label = parts[1].strip() if len(parts) > 1 else ""
                else:
                    from_label = booking.get("from", "")
                    to_label = booking.get("to", "")

                # Get profile id and then the profile name from the mapping
                profile_id = booking.get("profile", "")
                profile_name = self._profile_mapping.get(profile_id, profile_id) if profile_id else ""

                modern_entry = {
                    "scheduleInfo": {
                        "startTimestamp": start_ts,
                        "type": "once",
                        "endTimestamp": end_ts
                    },
                    "locked": False,
                    "serviceDefinition": {
                        "from": booking.get("from", ""),
                        "to": booking.get("to", ""),
                        "fromLabel": from_label,  # new field: device label for source
                        "toLabel": to_label,      # new field: device label for destination
                        "allocationState": booking.get("allocationState", 0),
                        "descriptor": {
                            "desc": descriptor.get("desc", ""),
                            "label": descriptor_label
                        },
                        "profileId": profile_id,
                        "profileName": profile_name,  # new field: user-friendly profile name
                        "tags": booking.get("tags", []),
                        "type": "connection",
                        "ctype": 2
                    }
                }
                
                modern_services_to_save[service_id] = modern_entry

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Modern Services",
            "",
            "JSON Files (*.json)"
        )
        
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(modern_services_to_save, f, indent=2)
            
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"Saved {len(modern_services_to_save)} service(s) to {file_path}."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error Saving File",
                str(e)
            )

    def load_services_from_file(self) -> dict | None:
        """
        Opens a file dialog for the user to select a JSON file containing modern-format services.
        Returns the loaded JSON as a dictionary or None if loading fails.
        """
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Services File",
            "",
            "JSON Files (*.json)"
        )

        if not file_path:
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error Loading File",
                f"Failed to load file: {e}"
            )
            return None

    async def load_and_create_services(self):
        """
        Loads modern-format services from a file, presents them in a confirmation dialog,
        and then creates the selected services via the modern API.
        """
        services = self.load_services_from_file()
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

    async def create_services_from_file(self, services: dict, selected_ids: set):
        """
        Creates services using the modern API endpoint /api/setModernServices.
        Reports to the user how many services were successfully created,
        how many failed, and lists the IDs of those that failed.
        """
        # Build the list of entries from the selected services
        entries = []
        for service_id in selected_ids:
            if service_id in services:
                entries.append(services[service_id])

        payload = {
            "header": {"id": 1},
            "data": {
                "conflictStrategy": 0,
                "bookingStrategy": 2,
                "entries": entries
            }
        }

        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                self.executor,
                lambda: self.client._request(
                    "POST",
                    f"{self.client.base_url}/api/setModernServices",
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
            )
            resp_json = response.json()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Service Creation Error",
                f"Failed to create services: {e}"
            )
            return

        # Parse the response
        data = resp_json.get("data", {})
        entriesLink = data.get("entriesLink", [])
        bookresult = data.get("bookresult", {})
        details = bookresult.get("details", {})
        
        success_count = 0
        failed_services = []

        # Iterate over each entry result
        for link in entriesLink:
            entry_id = link.get("id")
            if link.get("error") is None and entry_id:
                detail = details.get(entry_id, {})
                # A status of 0 indicates success
                if detail.get("status", 0) == 0:
                    success_count += 1
                else:
                    failed_services.append(entry_id)
            else:
                failed_services.append(entry_id if entry_id else "Unknown")

        total = len(entriesLink)
        failure_count = total - success_count
        
        msg = f"Successfully created {success_count} service(s).\n"
        if failure_count > 0:
            msg += f"Failed to create {failure_count} service(s): {', '.join(failed_services)}"
        else:
            msg += "All services were created successfully."

        QtWidgets.QMessageBox.information(
            self,
            "Service Creation Results",
            msg
        )

    def editSystems(self):
        from systems_editor_dialog import SystemsEditorDialog
        dlg = SystemsEditorDialog(self)
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
                else:
                    self.frameConnectionIndicator.setStyleSheet("background-color: green;")
                    self.labelConnectionStatusText.setText("Connected")
            else:
                self.frameConnectionIndicator.setStyleSheet("background-color: green;")
                self.labelConnectionStatusText.setText("Connected")
        else:
            self.frameConnectionIndicator.setStyleSheet("background-color: grey;")
            self.labelConnectionStatusText.setText("No Connection")
        
        self.actionLogout.setEnabled(connected)
        self.actionSaveSelectedServices.setEnabled(connected)
        
        # Show or hide user role and service count based on connection state.
        self.labelUserInfo.setVisible(connected)
        self.labelServiceCount.setVisible(connected)
        
        # Always hide spinner when not loading.
        self.loadingLabel.setVisible(False)


    def showAbout(self):
        dlg = QtWidgets.QDialog()
        uic.loadUi("about_dialog.ui", dlg)
        dlg.exec()

    def showSettings(self):
        dlg = QtWidgets.QDialog()
        uic.loadUi("settings_dialog.ui", dlg)
        dlg.exec()

    def _onDetailsCellClicked(self, row: int, col: int):
        if col != 1:
            return

        item = self.tableWidgetServiceDetails.item(row, col)
        if not item:
            return

        parent_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not parent_id:
            return

        group_svc = self.currentServices.get(parent_id)
        if not group_svc:
            group_svc = self.client.fetch_single_group_connection(parent_id)
            if not group_svc:
                QtWidgets.QMessageBox.information(
                    self,
                    "Group Parent",
                    f"Could not locate group parent '{parent_id}' in the remote system."
                )
                return
            self.currentServices[parent_id] = group_svc

        dlg = GroupDetailDialog(parent_id, group_svc, parent=self)
        dlg.exec()

    async def refreshServicesAsync(self):
        if not self.client:
            QtWidgets.QMessageBox.information(
                self, "Not Connected", "Not connected to a remote VideoIPath system."
            )
            return
        self.startLoadingAnimation()  # Start spinner animation
        self.statusMsgLabel.setText("Refreshing services...")
        try:
            responses = await self._fetchServicesData()
            result = self._processServicesData(responses)
            self.onServicesRetrieved(result)
        except Exception as e:
            self.onServicesError(str(e))
        finally:
            self.stopLoadingAnimation()  # Stop spinner animation
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
        self.currentServices = merged

        # Update the profile mapping so that profile names are used.
        self._profile_mapping = result["profile_mapping"]

        # Create a model with six columns in the specified order.
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
            prof_name = self._profile_mapping.get(pid, pid)
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
            
            # Create QStandardItem for the Start column and store the raw timestamp in UserRole.
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
        
        # Update the total services label to count only non-group services
        total_services = len([svc for svc in merged.values() if svc.get("type", "") != "group"])
        self.labelServiceCount.setText(f"Total services: {total_services}")

        self.update_table_fonts()

    def onServicesError(self, error_msg):
        QtWidgets.QMessageBox.critical(self, "Error Refreshing Services", error_msg)
        self.statusMsgLabel.setText("Error refreshing services")
        QtCore.QTimer.singleShot(3000, lambda: self.statusMsgLabel.setText(""))

    def displayServiceDetails(self, svc_id: str):
        raw_svc = self.currentServices.get(svc_id, {})
        self.tableWidgetServiceDetails.setRowCount(0)

        def add_detail(field: str, val: str, user_data=None, is_link=False):
            r = self.tableWidgetServiceDetails.rowCount()
            self.tableWidgetServiceDetails.insertRow(r)

            item_field = QtWidgets.QTableWidgetItem(field)
            item_field.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
            self.tableWidgetServiceDetails.setItem(r, 0, item_field)

            item_val = QtWidgets.QTableWidgetItem(val)
            item_val.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
            if is_link:
                brush = QtGui.QBrush(QtGui.QColor("blue"))
                item_val.setForeground(brush)
                font = item_val.font()
                font.setUnderline(True)
                item_val.setFont(font)
                if user_data is not None:
                    item_val.setData(QtCore.Qt.ItemDataRole.UserRole, user_data)
            self.tableWidgetServiceDetails.setItem(r, 1, item_val)

        svc_type = raw_svc.get("type", "")
        if svc_type == "group":
            add_detail("Service Kind", "Group-Based Service")
        else:
            group_par = raw_svc.get("groupParent", "")
            if group_par:
                add_detail("Service Kind", f"Endpoint-Based (Child of group {group_par})")
            else:
                add_detail("Service Kind", "Endpoint-Based Service")
        if svc_type:
            add_detail("type", str(svc_type))
        booking = raw_svc.get("booking", {})
        add_detail("serviceId", str(booking.get("serviceId", svc_id)))
        if "allocationState" in booking:
            add_detail("allocationState", str(booking["allocationState"]))
        add_detail("createdBy", str(booking.get("createdBy", "")))
        add_detail("lockedBy", str(booking.get("lockedBy", "")))
        add_detail("isRecurrentInstance", str(booking.get("isRecurrentInstance", False)))
        add_detail("timestamp", str(booking.get("timestamp", "")))
        group_parent_id = raw_svc.get("groupParent", "")
        if group_parent_id:
            add_detail("Group Parent", group_parent_id, user_data=group_parent_id, is_link=True)

        from_uid = booking.get("from", "")
        to_uid   = booking.get("to", "")
        from_label = self._endpoint_map.get(from_uid, from_uid)
        to_label   = self._endpoint_map.get(to_uid, to_uid)
        descriptor = booking.get("descriptor", {})
        desc_label = descriptor.get("label", "")
        add_detail("descriptor.label", desc_label)
        add_detail("descriptor.desc", descriptor.get("desc", ""))
        m = re.match(r'(.+?)\s*->\s*(.+)', desc_label)
        if m:
            from_label, to_label = m.group(1).strip(), m.group(2).strip()
        add_detail("from label", from_label)
        add_detail("from device", from_uid)
        add_detail("to label", to_label)
        add_detail("to device", to_uid)

        # Convert start timestamp
        start_ts = booking.get("start", "")
        if start_ts:
            try:
                dt_val = datetime.fromtimestamp(int(start_ts) / 1000)
                start_str = dt_val.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                start_str = start_ts
        else:
            start_str = ""
        add_detail("start", start_str)

        # Convert end timestamp with check for >10 years in the future
        end_ts = booking.get("end", "")
        if end_ts:
            try:
                dt_val = datetime.fromtimestamp(int(end_ts) / 1000)
                if dt_val - datetime.now() > timedelta(days=3650):
                    end_str = "∞"
                else:
                    end_str = dt_val.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                end_str = end_ts
        else:
            end_str = ""
        add_detail("end", end_str)

        add_detail("cancelTime", str(booking.get("cancelTime", "")))
        prof_id = booking.get("profile", "")
        prof_name = self._profile_mapping.get(prof_id, prof_id)
        add_detail("profile name", prof_name)
        add_detail("profile ID", prof_id)
        for i, audit in enumerate(booking.get("auditHistory", []), start=1):
            combined = (
                f"msg: {audit.get('msg','')}\n"
                f"user: {audit.get('user','')}\n"
                f"rev: {audit.get('rev','')}\n"
                f"ts: {audit.get('ts','')}"
            )
            add_detail(f"auditHistory[{i}]", combined)
        res_data = raw_svc.get("res")
        if res_data is not None:
            add_detail("res", json.dumps(res_data, indent=2))

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

        sorted_pids = sorted(used_profile_ids, key=lambda pid: self._profile_mapping.get(pid, pid).lower())
        for pid in sorted_pids:
            pname = self._profile_mapping.get(pid, pid)
            cb = QtWidgets.QCheckBox(pname, self.scrollAreaWidgetProfilesFilters)
            cb.stateChanged.connect(self.onProfilesFilterChanged)
            self.layoutProfiles.addWidget(cb)
            self.profileCheckBoxes.append((cb, pname))

    def onSourceFilterChanged(self, text: str):
        self.filterProxy.setSourceFilterText(text)
        QtCore.QTimer.singleShot(0, self.updateServiceSelection)

    def onDestinationFilterChanged(self, text: str):
        self.filterProxy.setDestinationFilterText(text)
        QtCore.QTimer.singleShot(0, self.updateServiceSelection)

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
        QtCore.QTimer.singleShot(0, self.updateServiceSelection)

    def onProfilesFilterChanged(self):
        chosen = []
        for cb, pname in self.profileCheckBoxes:
            if cb.isChecked():
                chosen.append(pname)
        self.filterProxy.setActiveProfiles(chosen)
        QtCore.QTimer.singleShot(0, self.updateServiceSelection)

    def onResetFilters(self):
        self.lineEditSourceFilter.clear()
        self.lineEditDestinationFilter.clear()
        self.checkBoxEnableTimeFilter.setChecked(False)
        today = QtCore.QDate.currentDate()
        self.dateTimeEditStart.setDateTime(QtCore.QDateTime(today, QtCore.QTime(0, 0, 0)))
        self.dateTimeEditEnd.setDateTime(QtCore.QDateTime(today, QtCore.QTime(23, 59, 59)))
        for cb, _ in self.profileCheckBoxes:
            cb.setChecked(False)
        QtCore.QTimer.singleShot(0, self.updateServiceSelection)

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

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QtWidgets.QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # (Load fonts, etc.)
    loaded_fonts = load_custom_fonts()
    print(f"Loaded fonts: {loaded_fonts}")  # Debug print

    if 'regular' in loaded_fonts:
        print(f"Setting regular font: {loaded_fonts['regular']}")  # Debug print
        default_font = QtGui.QFont(loaded_fonts['regular'], 10)
        app.setFont(default_font)
    else:
        print("Falling back to default system font.")

    window = MainWindow()

    # (Set fonts if needed)
    if 'bold' in loaded_fonts:
        window.set_bold_font_family(loaded_fonts['bold'])

    # Set application/window icon with best practices
    set_app_icon(app, window)
    window.show()

    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()