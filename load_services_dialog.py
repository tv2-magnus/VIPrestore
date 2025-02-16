from PyQt6.QtCore import Qt
from PyQt6 import QtWidgets

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