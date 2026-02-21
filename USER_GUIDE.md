# Team Scraper - Complete User Guide

**Extract employee/member information from any website - No coding required!**

Version 2.3.2 | Last Updated: February 2026

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Choosing Your Interface](#choosing-your-interface)
4. [Finding & Testing Selectors](#finding--testing-selectors)
5. [Advanced Extraction: Split Names](#advanced-extraction-split-names)
6. [Pagination & Navigation Strategies](#pagination--navigation-strategies)
7. [Stealth & Anti-Detection](#stealth--anti-detection)
8. [Performance & Speed Tuning](#performance--speed-tuning)
9. [Pre-Scrape Actions (Clicks)](#pre-scrape-actions-clicks)
10. [Output Formats](#output-formats)
11. [Troubleshooting](#troubleshooting)

---

## Quick Start

**In 5 minutes:**
1. Install Python & dependencies.
2. Open GUI: `python gui_scraper.py`.
3. Enter target URL and container selector (e.g., `.team-member`).
4. Choose output format (JSON, CSV, or Excel).
5. Click **START SCRAPING**.

---

## Installation

### Step 1: Install Python
Download Python 3.8 or higher from [python.org](https://www.python.org/downloads/)
**⚠️ Important:** Check "Add Python to PATH" during installation.

### Step 2: Install Dependencies
Open your terminal and run:
```bash
pip install -r requirements.txt
playwright install chromium
```

### Step 3: Navigate to Folder
```bash
cd team-scraper
```

---

## Choosing Your Interface

### Option 1: GUI (Recommended)
Launch the modern tabbed interface with `python gui_scraper.py`.
- **General Tab**: URL, Container, and Browser Mode (Visible/Hidden).
- **Data Selection**: Name, Email, Position, and Split Name settings.
- **Pagination**: Choose your navigation strategy.
- **Advanced**: Speed tuning and pre-scrape actions.

---

## Pagination & Navigation Strategies

The scraper supports four professional-grade navigation strategies to handle different website architectures.

### 1. Link-Based Pagination (Standard Multi-page)
Use this for traditional websites where clicking a page number loads a new URL.
- **Behavior**: Scraper extracts URLs from `<a>` tags and visits them.
- **Selector Example**: `.pagination a.next`

### 2. Parameter-Based Pagination (Search/Query)
Use this when pages are determined by a URL parameter, even if no direct links are visible.
- **Behavior**: Scraper builds URLs like `?page=2`, `?page=3` automatically.
- **Config**: Provide the **Parameter Name** (e.g., `page` or `p`).

### 3. Dynamic SPA Navigation (Single Page Application)
Use this for modern **Single Page Applications (SPAs)** where clicking buttons (like A-Z filters or category tabs) loads content via **AJAX** without changing the URL.
- **Behavior**: The scraper uses Playwright to physically click each button, wait for the content to update, and then extract the data.
- **Selector Example**: `.filter-buttons button[data-category]`
- **Pro Tip**: You can also configure **Post-Pagination Clicks** if you need to hit a "Search" or "Apply" button after choosing a filter.

### 4. AJAX "Load More" & Infinite Scroll
Use this for modern feeds that keep growing as you interact.
- **Infinite Scroll**: Scraper smoothly scrolls to the bottom multiple times to trigger content loading.
- **Load More Button**: Scraper clicks a specific "View More" button repeatedly until all items are visible.

---

## Stealth & Anti-Detection

### 🤖 Human-in-the-Loop (HITL)
If a website shows a CAPTCHA or requires login:
1. **Enable Visible Browser**: Uncheck "Run in background" in the General tab.
2. **Solve Manually**: The browser will pop up when a challenge is detected.
3. **Solve & Resume**: Once you solve the challenge, the scraper detects the content change and automatically resumes.
4. **Session Saving**: Your login session is saved to `auth.json` to bypass future challenges.

---

## Pre-Scrape Actions (Clicks)

**Automate interactions before the scraping process starts.**
- **Use Case**: Accept cookie banners, close intrusive popups, or open a hidden side-menu that contains the team list.
- **Selector**: `#accept-cookies;;.close-modal` (Use `;;` to separate multiple steps).

---

## Output Formats

**JSON**: High performance, best for large datasets.
**CSV**: Best for importing into Google Sheets or simple Excel use.
**Excel (XLSX)**: Professional reports with bold headers and auto-column sizing.

---

## Troubleshooting

### "No items found"
- Verify your **Container Selector** in the browser console: `document.querySelectorAll('.your-selector').length`.
- Ensure you aren't on a login wall (use **Visible Browser** mode to check).

### Getting Blocked (403 Forbidden)
- Switch to **Stealth Mode** in the Advanced tab.
- Increase the **Download Delay** to 5-10 seconds.

---

**Made with ❤️ for professional web scraping** 🚀
