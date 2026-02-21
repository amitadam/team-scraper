# PyInstaller hook for scrapy-playwright

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = (
    collect_submodules('scrapy_playwright') +
    [
        'scrapy_playwright.handler',
        'scrapy_playwright.page',
        'scrapy_playwright.headers',
    ]
)

datas = collect_data_files('scrapy_playwright')
