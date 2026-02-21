# Scrapy settings for TeamScraper project
import scrapy
import os

BOT_NAME = "TeamScraper"
SPIDER_MODULES = ["TeamScraper.spiders"]
NEWSPIDER_MODULE = "TeamScraper.spiders"

# ═══════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════

# Show only INFO and above (hides DEBUG noise from Scrapy/Playwright)
LOG_LEVEL = 'INFO'
# HEADLESS MODE: Controlled by env var 'SCRAPER_HEADLESS' (default: False/Visible for manual bypass)
# Set to 'true' for background mode.
HEADLESS = os.getenv('SCRAPER_HEADLESS', 'False').lower() == 'true'
# STORAGE STATE: Path to save/load browser cookies (e.g. after solving CAPTCHA)
STORAGE_STATE_PATH = 'auth.json'


# For diagnostics: Change to 'DEBUG' to see detailed activity during waits/delays
# Useful if scraper appears frozen - DEBUG will show download delays, browser launches, etc.
# Remember to change back to 'INFO' after diagnosing to avoid log spam

# ═══════════════════════════════════════════════════════════════════════
# REQUEST SETTINGS
# ═══════════════════════════════════════════════════════════════════════

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

ROBOTSTXT_OBEY = False

# ═══════════════════════════════════════════════════════════════════════
# ANTI-BOT & THROTTLING
# ═══════════════════════════════════════════════════════════════════════

CONCURRENT_REQUESTS = 1
DOWNLOAD_DELAY = 3  # Reduced from 6 - configure in GUI based on site flexibility
RANDOMIZE_DOWNLOAD_DELAY = False  # Disabled by default - enable in GUI if needed

# Increase retries for pages that timeout due to complex page rendering
RETRY_ENABLED = True
RETRY_TIMES = 4  # Increased from 3 to handle temporary blocks
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]  # 403 removed - bot detection, not worth retrying

AUTOTHROTTLE_ENABLED = False  # Disabled by default - enable in GUI for adaptive delays
AUTOTHROTTLE_START_DELAY = 1  # Reduced from 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 0.5  # More conservative throttling

# ═══════════════════════════════════════════════════════════════════════
# HTTP ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════

# Allow non-200 responses through so we can handle them in the spider
HTTPERROR_ALLOWED_CODES = [403, 404, 429]  # Bot blocks, not found, rate limits

# ═══════════════════════════════════════════════════════════════════════
# PLAYWRIGHT CONFIGURATION (Stealth Background Mode)
# ═══════════════════════════════════════════════════════════════════════

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Base browser args (always applied)
_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--ignore-certifcate-errors",
    "--ignore-certifcate-errors-spki-list",
    "--disable-dev-shm-usage",  # Overcome limited resource problems
    "--disable-accelerated-2d-canvas",  # Reduce GPU fingerprinting
    "--disable-gpu",  # Disable GPU hardware acceleration
    "--hide-scrollbars",  # Hide scrollbars
    "--mute-audio",  # Mute audio
    "--disable-background-timer-throttling",  # Disable timer throttling
    "--disable-backgrounding-occluded-windows",
    "--disable-breakpad",
    "--disable-component-extensions-with-background-pages",
    # Critical for Windows: Prevent throttling when minimized/backgrounded
    "--disable-features=TranslateUI,BlinkGenPropertyTrees,CalculateNativeWinOcclusion",
    "--disable-ipc-flooding-protection",
    "--disable-renderer-backgrounding",
    "--enable-features=NetworkService,NetworkServiceInProcess",
]

# Start off-screen if visible (so it doesn't pop up over work)
# Will be brought to front when CAPTCHA is detected
if not HEADLESS:
    _BROWSER_ARGS.append("--window-position=-32000,-32000")

PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": HEADLESS,  # Toggle via HEADLESS variable above
    "args": _BROWSER_ARGS,
    "ignore_default_args": ["--enable-automation"],
}

PLAYWRIGHT_CONTEXT_OPTIONS = {
    # If visible, let the browser determine size (minimized). If headless, use 1920x1080.
    "viewport": None if not HEADLESS else {"width": 1920, "height": 1080},
    "user_agent": USER_AGENT,
    "locale": "en-US",
    "timezone_id": "UTC",
    "ignore_https_errors": True,  # Ignore HTTPS errors
    "java_script_enabled": True,  # Ensure JavaScript is enabled
    "has_touch": False,  # Desktop simulation
    "is_mobile": False,  # Desktop simulation
    "device_scale_factor": 1,  # Standard display scaling
}

import os
if os.path.exists(STORAGE_STATE_PATH):
    PLAYWRIGHT_CONTEXT_OPTIONS['storage_state'] = STORAGE_STATE_PATH


# Resource filtering - ONLY block heavy resources that don't affect detection
# CSS and fonts are kept to appear more like a real browser
def should_abort_request(request):
    # Block only images and media (videos/audio) - these are heavy and less detectable
    # Keep: document, script, fetch (XHR), stylesheet (CSS), font
    return request.resource_type in ["image", "media"]

PLAYWRIGHT_ABORT_REQUEST = should_abort_request

# ═══════════════════════════════════════════════════════════════════════
# EXPORT SETTINGS
# ═══════════════════════════════════════════════════════════════════════

FEED_EXPORT_ENCODING = "utf-8"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"

# ═══════════════════════════════════════════════════════════════════════
# PIPELINES - Incremental saving and state tracking
# ═══════════════════════════════════════════════════════════════════════

ITEM_PIPELINES = {
    'TeamScraper.pipelines.IncrementalJsonWriterPipeline': 100,   # JSON format
    'TeamScraper.pipelines.IncrementalCsvWriterPipeline': 101,    # CSV format
    'TeamScraper.pipelines.IncrementalExcelWriterPipeline': 102,  # Excel format
    'TeamScraper.pipelines.StateTrackerPipeline': 200,           # Progress tracking
}
