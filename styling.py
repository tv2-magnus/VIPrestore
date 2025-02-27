import logging
import os
import sys
import ctypes
from PyQt6 import QtGui
from constants import APP_ID
from utils import resource_path

logger = logging.getLogger(__name__)

class AppearanceManager:
    """Manages application appearance including fonts, styles, and icons."""
    
    def __init__(self):
        """Initialize the appearance manager."""
        self.loaded_fonts = {}
        self.app_id = APP_ID
    
    def load_custom_fonts(self):
        """
        Load all required font variants and register them with the application.
        
        Returns:
            dict: Dictionary of loaded font families by variant name
        """
        font_files = {
            'regular': 'Roboto-Regular.ttf',
            'bold': 'Roboto-Bold.ttf',
        }

        fonts_dir = resource_path("fonts")
        
        # Debug information
        logger.debug(f"Looking for fonts in: {fonts_dir}")
        
        for variant, filename in font_files.items():
            font_path = os.path.join(fonts_dir, filename)
            if not os.path.exists(font_path):
                logger.warning(f"Font file not found: {font_path}")
                continue

            font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
            if font_id == -1:
                logger.warning(f"Failed to load font: {filename}")
                continue

            families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
            if families:
                self.loaded_fonts[variant] = families[0]
                logger.debug(f"Successfully loaded font: {filename} as {families[0]}")
            else:
                logger.warning(f"No font families found for: {filename}")

        return self.loaded_fonts
    
    def apply_fonts(self, app, main_window):
        """
        Apply loaded fonts to the application and main window.
        
        Args:
            app: QApplication instance
            main_window: MainWindow instance
        """
        if not self.loaded_fonts:
            self.load_custom_fonts()
            
        if 'regular' in self.loaded_fonts:
            app.setFont(QtGui.QFont(self.loaded_fonts['regular'], 10))
            logger.debug(f"Set application font to {self.loaded_fonts['regular']}")
            
        if 'bold' in self.loaded_fonts and hasattr(main_window, 'set_bold_font_family'):
            main_window.set_bold_font_family(self.loaded_fonts['bold'])
            logger.debug(f"Set bold font to {self.loaded_fonts['bold']}")
    
    def set_app_icon(self, app, window):
        """
        Sets the application icon using multi-size .ico on Windows and .png on other platforms.
        Also sets OS-specific attributes like the Windows app user model ID.
        
        Args:
            app: QApplication instance
            window: MainWindow instance
        """
        # Determine icon path based on platform
        if sys.platform == 'win32':
            icon_path = resource_path(os.path.join("logos", "viprestore_icon.ico"))
        else:
            icon_path = resource_path(os.path.join("logos", "viprestore_icon.png"))

        # Create and set the icon if it exists
        if os.path.exists(icon_path):
            icon = QtGui.QIcon(icon_path)
            app.setWindowIcon(icon)
            window.setWindowIcon(icon)
            logger.debug(f"Set application icon from {icon_path}")
        else:
            logger.warning(f"Icon file not found: {icon_path}")

        # OS-specific settings
        if sys.platform.startswith('linux'):
            app.setDesktopFileName('viprestore.desktop')
            logger.debug("Set Linux desktop filename")
        elif sys.platform == 'win32':
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(self.app_id)
                logger.debug(f"Set Windows AppUserModelID to {self.app_id}")
            except Exception as e:
                logger.error(f"Failed to set Windows AppUserModelID: {e}")
    
    def apply_table_styles(self, main_window):
        """
        Apply consistent styling to tables in the main window.
        
        Args:
            main_window: MainWindow instance
        """
        if not hasattr(main_window, 'tableViewServices') or not hasattr(main_window, 'tableWidgetServiceDetails'):
            return
            
        table_style = """
            QTableView, QTableWidget {
                background-color: #eeeeee;
                alternate-background-color: #dddddd;
                color: black;
            }
            QTableView::item:selected, QTableWidget::item:selected {
                background-color: #a1aaff;
                color: black;
            }
        """
        
        # Apply font family if available
        if 'bold' in self.loaded_fonts:
            font_family = self.loaded_fonts['bold']
            table_style = f"""
                QTableView, QTableWidget {{
                    background-color: #eeeeee;
                    alternate-background-color: #dddddd;
                    color: black;
                    font-family: "{font_family}";
                    font-weight: bold;
                }}
                QTableView::item:selected, QTableWidget::item:selected {{
                    background-color: #a1aaff;
                    color: black;
                }}
            """
        
        main_window.tableWidgetServiceDetails.setStyleSheet(table_style)
        main_window.tableViewServices.setStyleSheet(table_style)
        logger.debug("Applied table styles")
    
    def setup_essential(self, app, main_window):
        """
        Apply only essential styling needed for initial display.
        
        Args:
            app: QApplication instance
            main_window: MainWindow instance
        """
        # Set application icon - important for window appearance
        self.set_app_icon(app, main_window)
        
        # Load font files but don't apply yet
        self.load_custom_fonts()
        logger.debug("Applied essential styling")
        
    def setup_complete(self, app, main_window):
        """
        Apply complete styling that can be deferred until after window is shown.
        
        Args:
            app: QApplication instance
            main_window: MainWindow instance
        """
        # Apply fonts to UI
        self.apply_fonts(app, main_window)
        
        # Apply table styles - can be deferred
        self.apply_table_styles(main_window)
        
        # Update table fonts
        if hasattr(main_window, 'update_table_fonts'):
            main_window.update_table_fonts()
        
        logger.debug("Applied complete styling")


# Singleton instance for easy access
appearance = AppearanceManager()

def setup_essential_styling(app, main_window):
    """
    Convenience function to set up essential styling.
    
    Args:
        app: QApplication instance
        main_window: MainWindow instance
    """
    appearance.setup_essential(app, main_window)

def setup_complete_styling(app, main_window):
    """
    Convenience function to set up complete styling.
    
    Args:
        app: QApplication instance
        main_window: MainWindow instance
    """
    appearance.setup_complete(app, main_window)

def setup_appearance(app, main_window):
    """
    Convenience function to set up all appearance aspects (legacy function).
    
    Args:
        app: QApplication instance
        main_window: MainWindow instance
    """
    appearance.setup_essential(app, main_window)
    appearance.setup_complete(app, main_window)