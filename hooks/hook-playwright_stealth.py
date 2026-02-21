# PyInstaller hook for playwright_stealth
# CRITICAL: playwright_stealth reads .js files from its package at runtime

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules('playwright_stealth')

# Include the JavaScript evasion files that are loaded at runtime
datas = collect_data_files('playwright_stealth', include_py_files=False)
