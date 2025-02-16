import re
from PyQt6 import QtCore

class ServicesFilterProxy(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.source_filter = ""
        self.destination_filter = ""
        self.start_range = (None, None)
        self.active_profiles = set()
    
    def setSourceFilterText(self, text):
        self.source_filter = text
        self.invalidateFilter()
    
    def setDestinationFilterText(self, text):
        self.destination_filter = text
        self.invalidateFilter()
    
    def setStartRange(self, start_dt, end_dt):
        self.start_range = (start_dt, end_dt)
        self.invalidateFilter()
    
    def setActiveProfiles(self, profile_names):
        self.active_profiles = set(profile_names)
        self.invalidateFilter()

    def evaluate_filter(self, text, filter_str):
        """
        Evaluate whether 'text' (already lower case) matches the filter_str.
        Supports uppercase "OR" and "AND" as operators, even if not surrounded by spaces.
        If no operator is detected, the filter is treated as a literal substring.
        """
        filter_str = filter_str.strip()
        if not filter_str:
            return True
        # Check for OR operator using word boundaries.
        if re.search(r'\bOR\b', filter_str):
            tokens = re.split(r'\bOR\b', filter_str)
            return any(token.strip().lower() in text for token in tokens if token.strip())
        # Check for AND operator using word boundaries.
        elif re.search(r'\bAND\b', filter_str):
            tokens = re.split(r'\bAND\b', filter_str)
            return all(token.strip().lower() in text for token in tokens if token.strip())
        else:
            return filter_str.lower() in text

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        # Adjusted column indices based on the current order:
        # 0: Service ID, 1: Source, 2: Destination, 3: Profile, 4: Created By, 5: Start
        idx_source = model.index(source_row, 1, source_parent)
        idx_dest   = model.index(source_row, 2, source_parent)
        idx_start  = model.index(source_row, 5, source_parent)
        idx_prof   = model.index(source_row, 3, source_parent)
    
        source_text = (model.data(idx_source) or "").lower()
        dest_text   = (model.data(idx_dest)   or "").lower()
        start_text  = (model.data(idx_start)  or "")
        profile_txt = (model.data(idx_prof)   or "")
    
        if not self.evaluate_filter(source_text, self.source_filter):
            return False
        if not self.evaluate_filter(dest_text, self.destination_filter):
            return False
    
        # Time range filter
        if start_text:
            dt_val = QtCore.QDateTime.fromString(start_text, "dd-MM-yyyy - HH:mm:ss")
            if self.start_range[0] and dt_val < self.start_range[0]:
                return False
            if self.start_range[1] and dt_val > self.start_range[1]:
                return False
    
        # Profile filter
        if self.active_profiles and profile_txt not in self.active_profiles:
            return False
    
        return True
    
    def lessThan(self, left, right):
        # Use the raw timestamp for sorting the Start column (index 5).
        if left.column() == 5:
            left_data = self.sourceModel().data(left, QtCore.Qt.ItemDataRole.UserRole)
            right_data = self.sourceModel().data(right, QtCore.Qt.ItemDataRole.UserRole)
            if left_data is not None and right_data is not None:
                return left_data < right_data
        return super().lessThan(left, right)