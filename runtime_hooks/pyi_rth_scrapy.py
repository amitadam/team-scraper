"""
Runtime hook for Scrapy + Playwright
Sets up environment before any imports
"""
import os
import sys


def _setup_scrapy_env():
    """Configure Scrapy environment for PyInstaller bundle"""

    # Get the base path (where the exe is running from)
    if getattr(sys, 'frozen', False):
        # Running as compiled
        base_path = sys._MEIPASS
        exe_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        base_path = os.path.dirname(os.path.abspath(__file__))
        exe_dir = base_path

    # Set SCRAPY_SETTINGS_MODULE environment variable
    os.environ['SCRAPY_SETTINGS_MODULE'] = 'TeamScraper.settings'

    # Add paths for module discovery
    sys.path.insert(0, base_path)
    sys.path.insert(0, os.path.join(base_path, 'TeamScraper'))

    # Set Playwright to look for browsers in the bundle
    playwright_path = os.path.join(base_path, 'playwright', 'driver')
    if os.path.exists(playwright_path):
        # Use bundled browsers
        browsers_path = os.path.join(playwright_path, 'package', '.local-browsers')
        if os.path.exists(browsers_path):
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_path

    # Ensure output files go to exe directory (not temp extraction folder)
    os.chdir(exe_dir)

    # Set multiprocessing start method for Windows compatibility
    import multiprocessing
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass  # Already set


_setup_scrapy_env()
