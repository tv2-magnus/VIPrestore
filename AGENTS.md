# VIPrestore Agent Guidelines

## Build/Package Commands
- **Build executable**: `pyinstaller viprestore.spec` (requires UPX in PATH)
- **Create release**: `powershell -ExecutionPolicy Bypass -File create_release.ps1`
- **Install dependencies**: `pip install -r requirements.txt`
- **No test framework** - this is a GUI application without automated tests

## Code Style & Conventions
- **Language**: Python 3.x with PyQt6 for GUI
- **Imports**: Group stdlib, third-party, then local imports with blank lines between groups
- **Classes**: Use PascalCase (e.g. `MainWindow`, `ServiceManager`)
- **Functions/variables**: Use snake_case (e.g. `fetch_services_data`, `current_services`)
- **Constants**: UPPER_CASE in separate constants.py file
- **Type hints**: Use type hints on function parameters and returns
- **Async**: Use async/await pattern with asyncio for non-blocking operations
- **Error handling**: Custom exceptions (e.g. `ServiceManagerError`, `VideoIPathClientError`)
- **Logging**: Use Python logging module with getLogger(__name__)
- **Comments**: Minimal inline comments, comprehensive docstrings for classes/methods
- **String formatting**: Use f-strings for interpolation
- **File paths**: Use pathlib.Path for cross-platform compatibility
- **UI files**: Load with uic.loadUi(), use resource_path() for bundled resources
- **Threading**: Use ThreadPoolExecutor for blocking I/O operations in async context

## API Documentation
- **VideoIPath API Guide**: See `VideoIPath API Guide.pdf` in project root for complete API reference
- Main API endpoints used: `/api/_session`, `/api/services`, `/api/profiles`, `/api/group-connections`
- Authentication via cookie-based session with XSRF token support

## Project Structure
- Main application entry point: `main.py`
- Client communication: `vipclient.py` 
- Business logic: `service_manager.py`
- UI dialogs: `*_dialog.py` files with corresponding `.ui` files
- Utilities: `utils.py`, styling in `styling.py`
- Resources: fonts/, logos/, UI files in root