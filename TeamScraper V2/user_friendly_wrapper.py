#!/usr/bin/env python3
"""
Team Scraper - User-Friendly Wrapper
Run this script to scrape team member data without knowing Python!
"""

import os
import sys
import subprocess
from datetime import datetime
import json


def print_banner():
    """Display welcome banner"""
    print("=" * 70)
    print("  TEAM MEMBER SCRAPER")
    print("  Extract names and emails from team directory pages")
    print("  ✓ Advanced Anti-Detection Enabled")
    print("=" * 70)
    print()


def get_input(prompt, default=None):
    """Get user input with optional default value"""
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()


def yes_no(prompt, default=True):
    """Ask yes/no question"""
    choice = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{choice}]: ").strip().lower()
    if not answer:
        return default
    return answer in ['y', 'yes']


def print_selector_test_guide(selector, selector_type="container", data_attr=None):
    """Print browser console commands to test a selector"""
    print("\n" + "─"*70)
    print(f"🧪 TEST YOUR {selector_type.upper()} SELECTOR")
    print("─"*70)
    print("\nOpen browser console (F12 → Console tab) and run:\n")

    if selector_type == "container":
        print(f"  document.querySelectorAll('{selector}').length")
        print("\n  ✅ Should return: Number of people/items on the page")
        print(f"\n  // Preview first item:")
        print(f"  document.querySelector('{selector}')")
    elif selector_type == "pagination":
        print(f"  document.querySelectorAll('{selector}').length")
        print("\n  ✅ Should return: Number of pagination links/buttons")
        print(f"\n  // Check first link:")
        print(f"  document.querySelector('{selector}')")
        if data_attr:
            print(f"\n  // Check data attribute value:")
            print(f"  document.querySelector('{selector}').getAttribute('{data_attr}')")
            print(f"\n  ✅ Should return: The value from the {data_attr} attribute")
    elif selector_type == "name":
        print(f"  document.querySelector('{selector}').textContent")
        print("\n  ✅ Should return: A person's name")
    elif selector_type == "email":
        print(f"  document.querySelector('{selector}').href")
        print("\n  ✅ Should return: An email address (mailto: link)")

    print("─"*70)


def main():
    print_banner()

    # Check if scrapy is installed
    try:
        subprocess.run(['scrapy', 'version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ ERROR: Scrapy is not installed!")
        print("   Please run: pip install scrapy scrapy-playwright")
        sys.exit(1)

    print("Let's configure your scraper. I'll guide you through each step.\n")

    # 1. URL
    print("STEP 1: Target Website")
    print("Enter the URL of the team/staff page you want to scrape.")
    url = get_input("URL (e.g., https://example.com/team)")

    if not url.startswith('http'):
        print("⚠️  Warning: URL should start with http:// or https://")
        url = 'https://' + url

    print()

    # 2. Container
    print("STEP 2: Container Selector")
    print("This is the CSS selector for each team member's card/box.")
    print("Example: div.team-member, article.staff-card, li.employee")
    print()
    print("💡 How to find it:")
    print("   1. Open the page in your browser")
    print("   2. Right-click on a person's card → Inspect")
    print("   3. Look for the element wrapping ONE person")
    print("   4. Copy its class (e.g., 'team-member' or 'staff-card')")
    container = get_input("Container selector")

    if yes_no("\nWould you like to see how to test this selector?", default=False):
        print_selector_test_guide(container, "container")
    print()

    # 3. Name
    print("STEP 3: Name Selector (Optional)")
    print("CSS selector for the person's name within each container.")
    print("Example: h3.name, h2.employee-name, .staff-title")
    name_sel = get_input("Name selector", default="h3, h2, h4, .name")
    print()

    # 4. Email
    print("STEP 4: Email Selector")
    print("Where is the email address located?")
    print("  1. On the listing page (same page as names)")
    print("  2. On individual profile pages (need to click each person)")

    email_location = get_input("Choose location (1-2)", default="1")

    profile_link_sel = None
    profile_email_sel = None

    if email_location == "2":
        print("\nYou'll need to provide:")
        print("a) Selector for the link to each person's profile")
        print("   - Use 'self' if the container itself is the link")
        print("   - Use 'a' if there's a link inside the container")
        print("   - Or use a specific selector like 'a.profile-link'")
        profile_link_sel = get_input("Profile link selector", default="self")

        print("\nb) Email selector on the profile page (optional)")
        print("   Example: a[href^='mailto:'], .email-link")
        print("   Leave empty to use same selector as listing page")
        profile_email_sel = get_input("Profile email selector (optional)", default="")

        if not profile_email_sel:
            print("   Using default: a[href^='mailto:']")
            email_sel = "a[href^='mailto:']"
        else:
            email_sel = profile_email_sel
    else:
        print("CSS selector for email links on the listing page.")
        print("Example: a[href^='mailto:'], a.email-link, .contact a")
        email_sel = get_input("Email selector", default="a[href^='mailto:']")

    print()

    # 5. Pagination
    print("STEP 5: Pagination (Optional)")
    pagination_sel = None
    pagination_type = "link"
    param_name = "letter"
    data_attr = "data-value"
    page_delay = "10"

    if yes_no("Does the page have multiple pages/pagination?", default=True):
        print("\n" + "="*70)
        print("PAGINATION STRATEGY")
        print("="*70)
        print("\n📋 Choose how the site handles multiple pages:\n")
        print("  1. Link-based pagination")
        print("     • Standard page links: /team/page/2, /team/page/3")
        print("     • Query parameters: /team?page=2, /staff?p=3")
        print("     • Next/Previous buttons with hrefs")
        print("     👉 Look for: <a href=\"...\"> tags with URLs\n")
        print("  2. Button-based pagination")
        print("     • Buttons with data attributes: <button data-letter=\"A\">")
        print("     • Filter elements: <div data-page=\"2\">")
        print("     • Custom attributes: <span data-value=\"xyz\">")
        print("     👉 Look for: Elements with data-* attributes\n")
        print("  3. Infinite Scroll / Load More")
        print("     • Content loads as you scroll down")
        print("     • 'Load More' button that adds items to the same page")
        print("     👉 No page numbers, just more content appearing\n")

        strategy = get_input("Choose strategy (1-3)", default="1")

        if strategy == "1":
            print("\n" + "-"*70)
            print("LINK-BASED PAGINATION SETUP")
            print("-"*70)
            print("\n💡 How to find the selector:")
            print("   1. Open browser DevTools (F12)")
            print("   2. Find the pagination area")
            print("   3. Look for <a> tags with href attributes")
            print("   4. Note the parent class or the link class\n")
            print("Examples:")
            print("   • <div class=\"pagination\"><a href=\"/page/2\">2</a></div>")
            print("     → Selector: div.pagination a")
            print("   • <a href=\"?page=2\" class=\"next\">Next</a>")
            print("     → Selector: a.next")
            print("   • <ul class=\"pages\"><li><a href=\"/p/2\">2</a></li></ul>")
            print("     → Selector: ul.pages a\n")
            pagination_sel = get_input("\nPagination selector", default="div.pagination a")

            if yes_no("\nWould you like to see how to test this selector?", default=False):
                print_selector_test_guide(pagination_sel, "pagination")

            pagination_type = "link"
        elif strategy == "2":
            print("\n" + "-"*70)
            print("BUTTON-BASED PAGINATION SETUP")
            print("-"*70)
            print("\n💡 How to find the information:\n")
            print("STEP 1: Find the buttons/elements")
            print("   1. Open browser DevTools (F12)")
            print("   2. Find the pagination buttons/filters")
            print("   3. Look for data-* attributes (data-letter, data-page, etc.)\n")
            print("Examples:")
            print("   • <button class=\"letter\" data-letter=\"A\">A</button>")
            print("     → Selector: button.letter or button[data-letter]")
            print("   • <div data-page=\"2\" class=\"page-btn\">2</div>")
            print("     → Selector: div.page-btn or div[data-page]")
            print("   • <span data-filter=\"active\" class=\"filter\">Active</span>")
            print("     → Selector: span.filter or span[data-filter]\n")
            pagination_sel = get_input("\nButton/Element selector", default="button.letter")

            print("\n" + "-"*70)
            print("STEP 2: Identify the data attribute")
            print("-"*70)
            print("\nLook at the HTML and find the attribute name AFTER 'data-'")
            print("Examples:")
            print("   • <button data-letter=\"A\"> → Attribute name: letter")
            print("   • <div data-page=\"2\"> → Attribute name: page")
            print("   • <span data-value=\"xyz\"> → Attribute name: value")
            data_attr_name = get_input("\nAttribute name (without 'data-' prefix)", default="value")
            data_attr = f"data-{data_attr_name}"

            print("\n" + "-"*70)
            print("STEP 3: URL parameter name")
            print("-"*70)
            print("\nThis determines how the URL will be built.")
            print("Check the actual site URL to see the parameter name:")
            print("   • https://site.com/team?letter=A → Parameter: letter")
            print("   • https://site.com/staff?page=2 → Parameter: page")
            print("   • https://site.com/list?filter=active → Parameter: filter")
            param_name = get_input("\nURL parameter name", default="letter")

            if yes_no("\nWould you like to see how to test this selector and data attribute?", default=False):
                print_selector_test_guide(pagination_sel, "pagination", data_attr)

            pagination_type = "param"
        else: # Infinite Scroll
            print("\n" + "-"*70)
            print("INFINITE SCROLL SETUP")
            print("-"*70)
            print("\nThis strategy will simply scroll to the bottom of the page repeatedly")
            print("to trigger content loading.\n")
            
            scroll_count = get_input("Number of times to scroll down", default="5")
            scroll_delay = get_input("Delay between scrolls (seconds)", default="2")
            
            pagination_type = "infinite"
            pagination_sel = None # No selector needed

        if pagination_type != "infinite":
            max_pages = get_input("Maximum pages to scrape", default="10")
            page_delay = get_input("Delay between pages (seconds)", default="10")
        else:
            max_pages = "1" # Infinite scroll happens on the single page
    else:
        max_pages = "1"
    print()

    # 6. Output format
    print("STEP 6: Output Format")
    print("Choose output format:")
    print("  1. JSON (recommended for international/special characters)")
    print("  2. CSV (works in Excel)")
    print("  3. Excel (XLSX)")

    format_choice = get_input("Choose format (1-3)", default="1")

    format_map = {
        "1": "json",
        "2": "csv",
        "3": "xlsx"
    }
    output_format = format_map.get(format_choice, "json")

    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    domain = url.split('/')[2].replace('www.', '').replace('.', '_')
    output_file = f"scraped_{domain}_{timestamp}.{output_format}"
    print()

    # 7. Build command
    print("=" * 70)
    print("CONFIGURATION COMPLETE!")
    print("=" * 70)
    print("\nYour scraper will:")
    print(f"  • Target URL: {url}")
    print(f"  • Container: {container}")
    print(f"  • Name selector: {name_sel}")
    if profile_link_sel:
        print(f"  • Email location: Individual profile pages")
        print(f"  • Profile link: {profile_link_sel}")
        print(f"  • Email selector: {email_sel}")
    else:
        print(f"  • Email selector: {email_sel} (on listing page)")
    
    if pagination_type == "infinite":
        print(f"  • Pagination type: Infinite Scroll")
        print(f"  • Scrolls: {scroll_count} times")
        print(f"  • Scroll delay: {scroll_delay}s")
    elif pagination_sel:
        print(f"  • Pagination type: {pagination_type}")
        print(f"  • Pagination selector: {pagination_sel}")
        if pagination_type == "param":
            print(f"  • Data attribute: {data_attr}")
            print(f"  • URL parameter: {param_name}")
        print(f"  • Max pages: {max_pages}")
        print(f"  • Page delay: {page_delay}s")
    
    print(f"  • Output file: {output_file}")
    print()

    if not yes_no("Ready to start scraping?", default=True):
        print("Scraping cancelled.")
        sys.exit(0)

    # Build scrapy command - use output_file parameter (pipeline handles it)
    cmd = [
        'scrapy', 'crawl', 'team',
        '-a', f'url={url}',
        '-a', f'container={container}',
        '-a', f'name_sel={name_sel}',
        '-a', f'email_sel={email_sel}',
        '-a', f'max_pages={max_pages}',
        '-a', f'output_file={output_file}',  # Incremental pipeline uses this
    ]
    
    # Add page_delay if defined (might not be for infinite scroll)
    if 'page_delay' in locals():
        cmd.extend(['-a', f'page_delay={page_delay}'])

    if pagination_type == "infinite":
        cmd.extend(['-a', 'infinite_scroll=true'])
        cmd.extend(['-a', f'scroll_count={scroll_count}'])
        cmd.extend(['-a', f'scroll_delay={scroll_delay}'])
    elif pagination_sel:
        cmd.extend(['-a', f'pagination_sel={pagination_sel}'])
        cmd.extend(['-a', f'pagination_type={pagination_type}'])
        if pagination_type == 'param':
            cmd.extend(['-a', f'param_name={param_name}'])
            cmd.extend(['-a', f'data_attr={data_attr}'])

    if profile_link_sel:
        cmd.extend(['-a', f'profile_link_sel={profile_link_sel}'])
        if profile_email_sel:
            cmd.extend(['-a', f'profile_email_sel={profile_email_sel}'])

    print("\n" + "=" * 70)
    print("STARTING SCRAPER...")
    print("=" * 70)
    print()

    # Run scrapy
    try:
        result = subprocess.run(cmd, check=True)
        print()
        print("=" * 70)
        print("✅ SCRAPING COMPLETE!")
        print("=" * 70)
        print(f"\nResults saved to: {output_file}")
        print(f"File location: {os.path.abspath(output_file)}")
        print("\n💡 Anti-detection features used:")
        print("   • Stealth browser mode (Playwright)")
        print("   • Smart resource loading (CSS + fonts)")
        print("   • Current Chrome User-Agent (131.0.0.0)")
        print("   • Human-like delays and timing")

        # Check if file exists and show stats
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"File size: {file_size:,} bytes")

            # Try to count items
            if output_format == 'json':
                try:
                    import json
                    with open(output_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        print(f"Total records extracted: {len(data)}")
                except:
                    pass

    except subprocess.CalledProcessError as e:
        print()
        print("=" * 70)
        print("❌ SCRAPING FAILED")
        print("=" * 70)
        print("\nPossible issues:")
        print("  • The website is blocking the scraper (403 Forbidden)")
        print("  • Wrong CSS selectors - check your selectors using browser DevTools")
        print("  • Network connectivity issues")
        print("  • Cloudflare/bot protection (try with Next button strategy)")
        print("\nCheck the error messages above for more details.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nScraping cancelled by user.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)