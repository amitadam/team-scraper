# Universal Team Scraper 🚀

**Extract employee names and emails from any team directory page with advanced anti-detection technology and human-in-the-loop support.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Scrapy](https://img.shields.io/badge/scrapy-2.11+-green.svg)](https://scrapy.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## ✨ Key Features

### 🛡️ **Advanced Anti-Detection & Stealth**
- **Stealth Browser Mode** - Integrated Playwright with stealth plugins to bypass advanced bot detection.
- **Smart Resource Loading** - Loads CSS and fonts like real browsers to avoid fingerprinting.
- **Human-Like Behavior** - Random delays, natural scrolling patterns, and proper timing.
- **Current User-Agent** - Automatically uses a modern Chrome identity.
- **Bypasses reCAPTCHA & Cloudflare** on most sites.

### 🤖 **Human-in-the-Loop (HITL)**
- **Visible Browser Mode** - Toggle headfull mode to manually solve CAPTCHAs or log in if a site challenges the scraper.
- **Session Persistence** - Automatically saves and loads authentication states to stay logged in.

### 🎯 **Universal & Flexible**
- **Three usage modes**: Modern GUI, Interactive CLI, or Direct Scrapy commands.
- **Profile Page Extraction** - Automatically visit individual profile pages to extract hidden emails.
- **Split Name Support** - Combine first, middle, and last names from separate HTML elements.
- **Comprehensive Pagination** - Supports:
  - **Standard Links**: Multi-page directories with real URLs.
  - **URL Parameters**: Search-based sites (e.g., `?page=2` or `?letter=A`).
  - **Dynamic SPA Navigation**: **Single Page Applications** where clicking buttons/categories loads content without changing the URL.
  - **AJAX "Load More"**: Infinite scroll or "View More" button support.
- **Pre-Scrape Actions** - Automate clicking cookie banners, closing popups, or navigating menus before scraping.

### 💾 **Reliability & Performance**
- **Incremental Saving** - Saves data immediately as items are scraped (JSON, CSV, or Excel).
- **Real-time Monitoring** - Live progress counters and color-coded logs in the GUI.
- **Error Resilience** - Intelligent error handling ensures the scraper continues even if some items fail.
- **Performance Presets** - Choose between Fast, Balanced, or Careful (Stealth) modes.

---

## 📦 Quick Start

### 1. Install Dependencies
```bash
pip install scrapy scrapy-playwright playwright-stealth openpyxl
playwright install chromium
```

### 2. Launch the Interface
```bash
# Graphical Interface (Easiest)
python gui_scraper.py

# Interactive Command Line
python user_friendly_wrapper.py
```

---

## 🎓 Advanced Usage Example

### Complex SPA Scraping with Pre-Clicks & AJAX Pagination
```bash
scrapy crawl team \
  -a url="https://example.com/team" \
  -a container=".member-card" \
  -a pre_scrape_clicks="#accept-cookies;;.open-menu" \
  -a pagination_type="button" \
  -a pagination_sel=".letter-filter" \
  -a data_attr="data-letter" \
  -a post_pagination_clicks=".apply-filter" \
  -a output_file="team_data.xlsx"
```

---

## 🎨 GUI Features

The modern tabbed interface includes:
- ✓ **Visual Setup**: Easy form builder with dynamic help text.
- ✓ **Real-time Console**: Live, color-coded status updates.
- ✓ **Performance Tab**: Fine-tune speed, delays, and auto-throttling.
- ✓ **Advanced Tab**: Configure pre-scrape actions and technical page loading states.

---

## 📖 Documentation

- **[USER_GUIDE.md](USER_GUIDE.md)** - 📘 Full guide covering selectors, pagination, and troubleshooting.
- **[CHANGELOG.md](CHANGELOG.md)** - Detailed version history.

---

## ⚖️ Legal & Ethics

This tool is for legitimate research and business purposes. Always respect `robots.txt` and a website's Terms of Service. Use appropriate delays to avoid overwhelming servers.

**Made with ❤️ for professional web scraping**
