import sys
import re
import json
import asyncio
from datetime import datetime, timedelta
from qasync import QEventLoop

from PyQt6 import QtWidgets, uic, QtGui, QtCore
from PyQt6.QtCore import Qt
from vipclient import VideoIPathClient, VideoIPathClientError
from login_dialog import LoginDialog

from concurrent.futures import ThreadPoolExecutor

import socket
import ssl
import urllib.parse

# This is a test comment
def load_custom_font():
    font_id = QtGui.QFontDatabase.addApplicationFont("fonts/Roboto-Regular.ttf")
    if font_id == -1:
        print("Failed to load Roboto font!")
        return None
    
    families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
    if families:
        return families[0]  # Use the first available font family
    return None

def verify_ssl_cert(server_url: str) -> bool:
    parsed = urllib.parse.urlparse(server_url)
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                # If no exception occurs, the certificate is valid.
                return True
    except ssl.SSLError:
        return False
    except Exception:
        return False

class ServicesFilterProxy(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.source_filter = ""
        self.destination_filter = ""
        self.start_range = (None, None)
        self.active_profiles = set()

    def setSourceFilterText(self, text):
        self.source_filter = text.lower()
        self.invalidateFilter()

    def setDestinationFilterText(self, text):
        self.destination_filter = text.lower()
        self.invalidateFilter()

    def setStartRange(self, start_dt, end_dt):
        self.start_range = (start_dt, end_dt)
        self.invalidateFilter()

    def setActiveProfiles(self, profile_names):
        self.active_profiles = set(profile_names)
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        idx_source = model.index(source_row, 1, source_parent)  # Source col
        idx_dest   = model.index(source_row, 2, source_parent)  # Destination col
        idx_start  = model.index(source_row, 3, source_parent)  # Start col
        idx_prof   = model.index(source_row, 4, source_parent)  # Profile col

        source_text = (model.data(idx_source) or "").lower()
        dest_text   = (model.data(idx_dest)   or "").lower()
        start_text  = (model.data(idx_start)  or "")
        profile_txt = (model.data(idx_prof)   or "")

        # 1) Source filter
        if self.source_filter not in source_text:
            return False

        # 2) Destination filter
        if self.destination_filter not in dest_text:
            return False

        # 3) Time range filter
        if start_text:
            dt_val = QtCore.QDateTime.fromString(start_text, "yyyy-MM-dd HH:mm:ss")
            if self.start_range[0] and dt_val < self.start_range[0]:
                return False
            if self.start_range[1] and dt_val > self.start_range[1]:
                return False

        # 4) Profile filter
        if self.active_profiles and profile_txt not in self.active_profiles:
            return False

        return True


class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(dict)
    error = QtCore.pyqtSignal(str)

class LoadServicesDialog(QtWidgets.QDialog):
   def __init__(self, services, parent=None):
       """
       services: dict of modern-format services loaded from file.
       Each service is expected to have in its serviceDefinition:
       fromLabel, toLabel, and profileName.
       """
       super().__init__(parent)
       self.setWindowTitle("Confirm Service Creation")
       self.setModal(True)
       self.services = services 
       self.selected_services = set()

       layout = QtWidgets.QVBoxLayout(self)

       # Informational label
       info_label = QtWidgets.QLabel("Review the services below and select the ones you wish to create:")
       layout.addWidget(info_label)

       # Create table with 4 columns: Select, Source, Destination, Profile
       self.table = QtWidgets.QTableWidget(self)
       self.table.setColumnCount(4)
       self.table.setHorizontalHeaderLabels(["Select", "Source", "Destination", "Profile"])
       self.table.setRowCount(len(services))
       self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)

       for row, (service_id, service) in enumerate(services.items()):
           service_def = service.get("serviceDefinition", {})
           source_label = service_def.get("fromLabel", service_def.get("from", "N/A"))
           dest_label = service_def.get("toLabel", service_def.get("to", "N/A"))
           profile_name = service_def.get("profileName", service_def.get("profileId", "N/A"))

           # Column 0: Checkbox for selection
           checkbox = QtWidgets.QCheckBox()
           checkbox.setChecked(True)
           checkbox.stateChanged.connect(self._update_selection)
           self.table.setCellWidget(row, 0, checkbox)

           # Column 1: Source label. Store service_id in user data
           source_item = QtWidgets.QTableWidgetItem(source_label)
           source_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
           source_item.setData(QtCore.Qt.ItemDataRole.UserRole, service_id)
           self.table.setItem(row, 1, source_item)

           # Column 2: Destination label
           dest_item = QtWidgets.QTableWidgetItem(dest_label)
           dest_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
           self.table.setItem(row, 2, dest_item)

           # Column 3: Profile name
           profile_item = QtWidgets.QTableWidgetItem(profile_name)
           profile_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
           self.table.setItem(row, 3, profile_item)

           # Initially add service_id to selection
           self.selected_services.add(service_id)

       self.table.horizontalHeader().setStretchLastSection(True)
       self.table.resizeColumnsToContents()
       layout.addWidget(self.table)

       # Add OK and Cancel buttons
       self.buttonBox = QtWidgets.QDialogButtonBox(
           QtWidgets.QDialogButtonBox.StandardButton.Ok |
           QtWidgets.QDialogButtonBox.StandardButton.Cancel
       )
       self.buttonBox.accepted.connect(self.accept)
       self.buttonBox.rejected.connect(self.reject)
       layout.addWidget(self.buttonBox)

   def _update_selection(self):
       """Refresh the set of selected services based on checkbox states."""
       self.selected_services.clear()
       for row in range(self.table.rowCount()):
           checkbox = self.table.cellWidget(row, 0)
           if checkbox and checkbox.isChecked():
               source_item = self.table.item(row, 1)
               if source_item:
                   service_id = source_item.data(QtCore.Qt.ItemDataRole.UserRole)
                   self.selected_services.add(service_id)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("main.ui", self)
        
        self.setSplitterPlacement()
        
        # Instance Variables
        self.client = None
        self._profile_mapping = {}
        self._endpoint_map = {}
        self.profileCheckBoxes = []
        self.currentServices = {}
        
        # Executor for blocking calls
        self.executor = ThreadPoolExecutor()
        
        # Build Actions and Add to Menus
        self.actionLogin = QtGui.QAction("Login", self)
        self.actionLogout = QtGui.QAction("Logout", self)
        self.actionEditSystems = QtGui.QAction("Edit Systems", self)
        self.actionSaveSelectedServices = QtGui.QAction("Save Selected Services", self)
        
        self.menuFile.addAction(self.actionLogin)
        self.menuFile.addAction(self.actionLogout)
        self.menuFile.addAction(self.actionEditSystems)
        self.menuFile.addAction(self.actionSaveSelectedServices)

        self.actionLoadServices = QtGui.QAction("Load Services", self)
        self.menuFile.addAction(self.actionLoadServices)
        self.actionLoadServices.triggered.connect(
            lambda: asyncio.create_task(self.load_and_create_services())
        )

        # Connect Action Signals
        self.actionLogin.triggered.connect(lambda: asyncio.create_task(self.doLogin()))
        self.actionRefresh.triggered.connect(lambda: asyncio.create_task(self.refreshServicesAsync()))
        self.actionLogout.triggered.connect(self.doLogout)
        self.actionEditSystems.triggered.connect(self.editSystems)
        self.actionAbout.triggered.connect(self.showAbout)
        self.actionSettings.triggered.connect(self.showSettings)
        self.actionSaveSelectedServices.triggered.connect(self.saveSelectedServices)

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
        
        # Set StyleSheet for Service View
        self.setStyleSheet("""
            QTableView, QTableWidget {
                background-color: #f5f5f5;
                alternate-background-color: #e5e5e5;
                color: black;
            }
            QTableView::item:selected, QTableWidget::item:selected {
                background-color: #bdc8ff;
                color: black;
            }
        """)

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
        self.tableWidgetServiceDetails.setStyleSheet("""
            QTableWidget {
                background-color: #f5f5f5;
                alternate-background-color: #e5e5e5;
            }
        """)
        
        # Setup Session Timer
        self.sessionTimer = QtCore.QTimer(self)
        self.sessionTimer.setInterval(30000)
        self.sessionTimer.timeout.connect(self.checkSession)
        self.sessionTimer.start()
        
        # --- Status Bar Setup ---
        # Create a new status bar (ignoring any pre-defined in the .ui file)
        status_bar = QtWidgets.QStatusBar(self)
        self.setStatusBar(status_bar)
        
        # Add user role label (to be updated by updateUserStatus)
        self.labelUserInfo = QtWidgets.QLabel("User: N/A | Role: N/A")
        status_bar.addWidget(self.labelUserInfo)
        
        # Add service count label immediately to the right of the user role.
        self.labelServiceCount = QtWidgets.QLabel("Total services: 0")
        status_bar.addWidget(self.labelServiceCount)
        self.labelServiceCount.setVisible(False)  # Hide when no connection
        
        # Create connection indicator (a small colored frame)
        self.frameConnectionIndicator = QtWidgets.QFrame()
        self.frameConnectionIndicator.setMinimumSize(QtCore.QSize(20, 20))
        self.frameConnectionIndicator.setMaximumSize(QtCore.QSize(20, 20))
        self.frameConnectionIndicator.setFrameShape(QtWidgets.QFrame.Shape.Box)
        self.frameConnectionIndicator.setFrameShadow(QtWidgets.QFrame.Shadow.Raised)
        self.frameConnectionIndicator.setStyleSheet("background-color: grey;")
        status_bar.addWidget(self.frameConnectionIndicator)
        
        # Add connection status text
        self.labelConnectionStatusText = QtWidgets.QLabel("No Connection")
        status_bar.addWidget(self.labelConnectionStatusText)
        
        # Add loading spinner (using an animated GIF "spinner.gif")
        self.loadingLabel = QtWidgets.QLabel("")
        self.loadingMovie = QtGui.QMovie("spinner.gif")
        self.loadingLabel.setMovie(self.loadingMovie)
        status_bar.addWidget(self.loadingLabel)
        self.loadingLabel.setVisible(False)
        
        # Add temporary status message label on the far right.
        self.statusMsgLabel = QtWidgets.QLabel("")
        status_bar.addPermanentWidget(self.statusMsgLabel)

        # Set Initial Connection Status
        self.updateConnectionStatus(False)

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
        label_user_info = self.findChild(QtWidgets.QLabel, "labelUserInfo")
        if label_user_info:
            label_user_info.setText(text)

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
            group_svc = self._fetchSingleGroupConnection(parent_id)
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
        future_profiles = self._run_api_call(lambda: self.client.get("/rest/v1/data/config/profiles/*/id,name,description,tags/**"))
        future_ep_local = self._run_api_call(lambda: self.client.get("/rest/v1/data/config/network/nGraphElements/**"))
        future_ep_ext = self._run_api_call(lambda: self.client.get("/rest/v1/data/status/network/externalEndpoints/**"))
        future_group = self._run_api_call(self._retrieve_group_connections)
        
        normal_services, profiles_resp, resp_local, resp_ext, group_res = await asyncio.gather(
            future_normal, future_profiles, future_ep_local, future_ep_ext, future_group
        )
        
        return {
            "normal_services": normal_services,
            "profiles_resp": profiles_resp,
            "resp_local": resp_local,
            "resp_ext": resp_ext,
            "group_res": group_res,
        }

    def _processServicesData(self, responses: dict) -> dict:
        normal_services = responses["normal_services"]
        profiles_resp = responses["profiles_resp"]
        resp_local = responses["resp_local"]
        resp_ext = responses["resp_ext"]
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

        endpoint_map = {}
        try:
            ngraph = resp_local.get("data", {}).get("config", {}).get("network", {}).get("nGraphElements", {})
            for node_id, node_data in ngraph.items():
                val = node_data.get("value", {})
                label = val.get("descriptor", {}).get("label", "")
                endpoint_map[node_id] = label if label else node_id
        except Exception:
            pass
        try:
            ext_data = resp_ext.get("data", {}).get("status", {}).get("network", {}).get("externalEndpoints", {})
            for ext_id, ext_val in ext_data.items():
                desc_obj = ext_val.get("descriptor", {})
                lbl = desc_obj.get("label") or ""
                endpoint_map[ext_id] = lbl if lbl else ext_id
        except Exception:
            pass

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

        new_model = QtGui.QStandardItemModel(self)
        new_model.setHorizontalHeaderLabels(["Service ID", "Source", "Destination", "Start", "Profile"])
        
        for svc_id, svc_data in merged.items():
            booking = svc_data.get("booking", {})
            label = booking.get("descriptor", {}).get("label", "")
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
                    dt_val = datetime.fromtimestamp(int(start_ts) / 1000)
                    start_str = dt_val.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
            pid = booking.get("profile", "")
            prof_name = self._profile_mapping.get(pid, pid)
            row_items = [
                QtGui.QStandardItem(str(booking.get("serviceId", svc_id))),
                QtGui.QStandardItem(src),
                QtGui.QStandardItem(dst),
                QtGui.QStandardItem(start_str),
                QtGui.QStandardItem(str(prof_name)),
            ]
            new_model.appendRow(row_items)
        
        self.filterProxy.setSourceModel(new_model)
        self.serviceModel = new_model

        self._rebuildProfileCheckboxes(used_profile_ids)
        self._setTableViewColumnWidths()
        
        # Update the total services label.
        total_services = len(merged)
        self.labelServiceCount.setText(f"Total services: {total_services}")

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
        for col in range(self.serviceModel.columnCount()):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.tableViewServices.setColumnWidth(0, 100)
        self.tableViewServices.setColumnWidth(1, 250)
        self.tableViewServices.setColumnWidth(2, 250)
        self.tableViewServices.setColumnWidth(3, 150)
        self.tableViewServices.setColumnWidth(4, 150)

    def _fetchSingleGroupConnection(self, group_id: str) -> dict | None:
        try:
            url = (
                "/rest/v1/data/status/conman/services/"
                "*%20where%20type='group'/connection/"
                "connection.generic,generic/**/.../.../connection.to,from,to,id,rev,specific/"
                "specific.breakAway,breakAway,complete,missingActiveConnections,numChildren,children/*"
            )
            resp = self.client.get(url)
            conman = resp.get("data", {}).get("status", {}).get("conman", {})
            raw_services = conman.get("services", {})

            for svc_key, svc_data in raw_services.items():
                connection = svc_data.get("connection", {})
                g_id = connection.get("id", svc_key)
                if g_id == group_id:
                    gen = connection.get("generic", {})
                    spec = connection.get("specific", {})
                    desc = gen.get("descriptor", {})

                    service_dict = {
                        "type": "group",
                        "booking": {
                            "serviceId": g_id,
                            "from": connection.get("from",""),
                            "to": connection.get("to",""),
                            "allocationState": None,
                            "createdBy": "",
                            "lockedBy": ("GroupLocked" if gen.get("locked") else ""),
                            "isRecurrentInstance": False,
                            "timestamp": "",
                            "descriptor": {
                                "label": desc.get("label",""),
                                "desc": desc.get("desc","")
                            },
                            "profile": "",
                            "auditHistory": [],
                        },
                        "res": {
                            "breakAway": spec.get("breakAway"),
                            "complete": spec.get("complete"),
                            "missingActiveConnections": spec.get("missingActiveConnections", {}),
                            "numChildren": spec.get("numChildren", 0),
                            "children": spec.get("children", {}),
                            "rev": connection.get("rev", ""),
                            "state": gen.get("state", None)
                        }
                    }
                    return service_dict
        except VideoIPathClientError:
            pass
        return None

    def _retrieve_group_connections(self) -> tuple:
        group_services = {}
        child_to_group = {}
        try:
            url = (
                "/rest/v1/data/status/conman/services/"
                "*%20where%20type='group'/connection/"
                "connection.generic,generic/**/.../.../connection.to,from,to,id,rev,specific/"
                "specific.breakAway,breakAway,complete,missingActiveConnections,numChildren,children/*"
            )
            resp = self.client.get(url)
            conman = resp.get("data", {}).get("status", {}).get("conman", {})
            raw_services = conman.get("services", {})

            for svc_key, svc_data in raw_services.items():
                connection = svc_data.get("connection", {})
                group_id = connection.get("id", svc_key)
                gen = connection.get("generic", {})
                spec = connection.get("specific", {})
                desc = gen.get("descriptor", {})

                group_services[group_id] = {
                    "type": "group",
                    "booking": {
                        "serviceId": group_id,
                        "from": connection.get("from", ""),
                        "to": connection.get("to", ""),
                        "allocationState": None,
                        "createdBy": "",
                        "lockedBy": ("GroupLocked" if gen.get("locked") else ""),
                        "isRecurrentInstance": False,
                        "timestamp": "",
                        "descriptor": {
                            "label": desc.get("label", ""),
                            "desc": desc.get("desc", "")
                        },
                        "profile": "",
                        "auditHistory": [],
                    },
                    "res": {
                        "breakAway": spec.get("breakAway"),
                        "complete": spec.get("complete"),
                        "missingActiveConnections": spec.get("missingActiveConnections", {}),
                        "numChildren": spec.get("numChildren", 0),
                        "children": spec.get("children", {}),
                        "rev": connection.get("rev", ""),
                        "state": gen.get("state", None)
                    }
                }

                children_map = spec.get("children", {})
                for child_id in children_map.keys():
                    child_to_group[child_id] = group_id

        except VideoIPathClientError:
            child_to_group = {}
        return group_services, child_to_group

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

    def _loadEndpointData(self):
        self._endpoint_map = {}

        try:
            resp_local = self.client.get("/rest/v1/data/config/network/nGraphElements/**")
            ngraph = resp_local.get("data", {}).get("config", {}).get("network", {}).get("nGraphElements", {})
            for node_id, node_data in ngraph.items():
                val = node_data.get("value", {})
                label = val.get("descriptor", {}).get("label", "")
                if label:
                    self._endpoint_map[node_id] = label
                else:
                    self._endpoint_map[node_id] = node_id
        except VideoIPathClientError:
            pass

        try:
            resp_ext = self.client.get("/rest/v1/data/status/network/externalEndpoints/**")
            ext_data = resp_ext.get("data", {}).get("status", {}).get("network", {}).get("externalEndpoints", {})
            for ext_id, ext_val in ext_data.items():
                desc_obj = ext_val.get("descriptor", {})
                lbl = desc_obj.get("label") or ""
                if lbl:
                    self._endpoint_map[ext_id] = lbl
                else:
                    self._endpoint_map[ext_id] = ext_id
        except VideoIPathClientError:
            pass

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

class GroupDetailDialog(QtWidgets.QDialog):
    def __init__(self, group_id: str, group_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Group Service: {group_id}")
        self.resize(700, 400)

        layout = QtWidgets.QVBoxLayout(self)
        self.detailsTable = QtWidgets.QTableWidget(self)
        self.detailsTable.setColumnCount(2)
        self.detailsTable.horizontalHeader().setVisible(False)
        self.detailsTable.verticalHeader().setVisible(False)
        self.detailsTable.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.detailsTable.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.detailsTable.setWordWrap(True)
        layout.addWidget(self.detailsTable)

        self._populateTable(group_id, group_data)

    def _populateTable(self, group_id: str, group_data: dict):
        self.detailsTable.setRowCount(0)

        def add_row(field: str, val: str):
            r = self.detailsTable.rowCount()
            self.detailsTable.insertRow(r)
            item_field = QtWidgets.QTableWidgetItem(field)
            item_field.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.detailsTable.setItem(r, 0, item_field)

            item_val = QtWidgets.QTableWidgetItem(val)
            item_val.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
            item_val.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
            self.detailsTable.setItem(r, 1, item_val)

        add_row("Service Kind", "Group-Based Service")
        booking = group_data.get("booking", {})
        add_row("serviceId", booking.get("serviceId", group_id))
        add_row("lockedBy", booking.get("lockedBy", ""))
        add_row("from", booking.get("from", ""))
        add_row("to", booking.get("to", ""))
        descriptor = booking.get("descriptor", {})
        add_row("descriptor.label", descriptor.get("label", ""))
        add_row("descriptor.desc", descriptor.get("desc", ""))
        res_obj = group_data.get("res", {})
        json_str = json.dumps(res_obj, indent=2)
        add_row("res", json_str)

def main():
    app = QtWidgets.QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # Load and apply Roboto globally
    roboto_font = load_custom_font()
    if roboto_font:
        font = QtGui.QFont(roboto_font, 10)  # Adjust size as needed
        app.setFont(font)
    else:
        print("Falling back to default system font.")
    
    window = MainWindow()
    window.show()
    
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()