# PyInstaller hook for Scrapy
# Scrapy uses dynamic imports that PyInstaller cannot detect automatically

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect ALL scrapy submodules
hiddenimports = (
    collect_submodules('scrapy') +
    collect_submodules('scrapy.pipelines') +
    collect_submodules('scrapy.extensions') +
    collect_submodules('scrapy.downloadermiddlewares') +
    collect_submodules('scrapy.spidermiddlewares') +
    collect_submodules('scrapy.utils') +
    collect_submodules('scrapy.core') +
    collect_submodules('scrapy.commands') +
    collect_submodules('scrapy.contracts') +
    collect_submodules('scrapy.linkextractors') +
    collect_submodules('scrapy.loader') +
    collect_submodules('scrapy.selector') +
    collect_submodules('scrapy.settings') +
    collect_submodules('scrapy.statscollectors') +
    [
        # Twisted reactor (CRITICAL for asyncio support)
        'twisted.internet.asyncioreactor',
        'twisted.internet.selectreactor',
        'twisted.internet.reactor',
        'twisted.internet.defer',
        'twisted.internet.task',
        'twisted.internet.ssl',
        'twisted.web.client',
        'twisted.web.http_headers',

        # itemadapter used by pipelines
        'itemadapter',

        # Parsel (scrapy selector engine)
        'parsel',

        # Other common scrapy dependencies
        'w3lib',
        'queuelib',
        'service_identity',
        'lxml',
        'lxml.etree',
        'cssselect',
        'protego',
    ]
)

# Collect scrapy data files (VERSION file, templates, etc.)
datas = collect_data_files('scrapy')
