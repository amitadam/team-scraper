import scrapy
import re
import json
from urllib.parse import urljoin, urlencode, urlparse, parse_qs
from scrapy_playwright.page import PageMethod
from playwright_stealth import Stealth
from ..items import EmployeeItem


class TeamSpider(scrapy.Spider):
    name = "team"

    def __init__(self, *args, **kwargs):
        super(TeamSpider, self).__init__(*args, **kwargs)

        # ── Required ──────────────────────────────────────────
        self.start_url = kwargs.get('url')
        self.container_sel = kwargs.get('container')
        if self.container_sel:
            self.container_sel = self.container_sel.replace(';;', ',')

        if not self.start_url or not self.container_sel:
            raise ValueError("Missing 'url' or 'container' parameters.")

        # ── Selectors ─────────────────────────────────────────
        self.name_sel = kwargs.get('name_sel') or 'h3, .name, .employee-name'
        self.email_sel = kwargs.get('email_sel') or 'a[href^="mailto:"], .email'
        self.position_sel = kwargs.get('position_sel') or '.position, .title, .job-title, .role'

        # Multi-selector support for split names (first/middle/last)
        first_name_sel = kwargs.get('first_name_sel')
        last_name_sel = kwargs.get('last_name_sel')
        middle_name_sel = kwargs.get('middle_name_sel')

        if first_name_sel or last_name_sel:
            # Build list of selectors in order: first, middle (optional), last
            self.name_selectors = []
            if first_name_sel:
                self.name_selectors.append(first_name_sel)
            if middle_name_sel:
                self.name_selectors.append(middle_name_sel)
            if last_name_sel:
                self.name_selectors.append(last_name_sel)
        else:
            self.name_selectors = None  # Use single selector mode

        self.profile_link_sel = kwargs.get('profile_link_sel')
        self.profile_email_sel = kwargs.get('profile_email_sel')

        # Pagination Settings
        self.pagination_sel = kwargs.get('pagination_sel')
        self.pagination_type = kwargs.get('pagination_type', 'link').lower()
        self.param_name = kwargs.get('param_name', 'letter')
        self.data_attr = kwargs.get('data_attr', 'data-value')  # Custom data attribute name

        self.max_pages = int(kwargs.get('max_pages', '30'))
        self.page_delay = int(kwargs.get('page_delay', '5'))

        # Infinite Scroll Settings
        self.infinite_scroll = kwargs.get('infinite_scroll', 'false').lower() == 'true'
        self.scroll_count = int(kwargs.get('scroll_count', '5'))
        self.scroll_delay = int(kwargs.get('scroll_delay', '2'))
        
        # Timeout Settings (Default 60s)
        self.timeout = int(kwargs.get('timeout', '60000'))
        self.wait_state = kwargs.get('wait_state', 'networkidle') # networkidle, domcontentloaded, load

        # Click Sequence Settings
        self.pre_scrape_clicks = kwargs.get('pre_scrape_clicks')  # Sequence of selectors separated by ';;'
        self.pre_scrape_all_pages = kwargs.get('pre_scrape_all_pages', 'false').lower() == 'true'
        self.post_pagination_clicks = kwargs.get('post_pagination_clicks')
        
        # Backward compatibility for 'load_more' -> 'click'
        if self.pagination_type == 'load_more':
            self.pagination_type = 'click'

        # State
        self.use_playwright = kwargs.get('use_playwright', 'true').lower() == 'true'
        self.visited_urls = set()
        self.page_count = 0
        # Don't use persistent context - creates new context per request group to avoid corruption
        self.shared_context_name = None

        # Output format (for pipeline selection)
        self.output_format = kwargs.get('format', 'json').lower()
        if self.output_format not in ['json', 'csv', 'xlsx']:
            raise ValueError(f"Invalid format '{self.output_format}'. Must be: json, csv, or xlsx")

        # Output file (for incremental pipeline)
        self.output_file = kwargs.get('output_file')

    def start_requests(self):
        self.logger.info(f"🚀 Starting scraper")
        self.logger.info(f"📦 Container: {self.container_sel} | Pagination: {self.pagination_sel or 'None'} | Max pages: {self.max_pages}")
        if self.infinite_scroll:
            self.logger.info(f"📜 Infinite Scroll: Enabled (Max {self.scroll_count} scrolls, {self.scroll_delay}s delay)")

        # DEBUG: Print the actual meta used in request
        meta = self._get_playwright_meta(self.container_sel, wait_time=self.page_delay * 1000, selector_optional=True)
        self.logger.info(f"DEBUG META: {meta}")

        yield scrapy.Request(
            url=self.start_url,
            callback=self.parse,
            # Revert to optional validation (selector_optional=True) - Just wait and scrape
            # The wait_time (5s) ensures page has loaded
            meta=self._get_playwright_meta(self.container_sel, wait_time=self.page_delay * 1000, selector_optional=True),
            errback=self.errback_playwright,
        )

    async def parse(self, response):
        self.page_count += 1
        self.visited_urls.add(response.url)

        # Check if we've exceeded max_pages BEFORE processing (prevent over-scraping)
        if self.page_count > self.max_pages:
            self.logger.info(f"⏭️ Skipping page {self.page_count}/{self.max_pages} (over limit): {response.url}")
            # Close page if exists
            page = response.meta.get("playwright_page")
            if page:
                await page.close()
            return  # Don't process this page

        self.logger.info(f"📄 Parsing page {self.page_count}/{self.max_pages}: {response.url}")

        # ── Cloudflare / Bot Protection Check ─────────────────
        # Check if we hit a protection page
        # Check title strongly for blocking indicators
        title = response.xpath('//title/text()').get() or ''
        is_blocking_title = 'Just a moment...' in title or 'Security Challenge' in title or 'Attention Required' in title
        
        is_cloudflare = (response.status == 403 or 
                         is_blocking_title or
                         'Waiting for you to skip the captcha' in response.text)

        if is_cloudflare:
            self.logger.warning(f"🛡️ Protection detected on {response.url}")
            
            # Check if we can do Human-in-the-Loop
            headless = self.settings.getbool('HEADLESS')
            page = response.meta.get("playwright_page")
            
            if not headless and page:
                self.logger.info("🤖 HEADLESS=False detected. Initiating 'Human in the Loop' bypass...")
                self.logger.info(f"👉 ACTION REQUIRED: Please manually solve the CAPTCHA in the browser window.")
                self.logger.info(f"⏳ Waiting for you to solve it... (Max 5 minutes)")

                # Bring browser window to front (it starts off-screen)
                try:
                    await page.bring_to_front()
                    # Move window to visible position using CDP
                    cdp = await page.context.new_cdp_session(page)
                    await cdp.send('Browser.setWindowBounds', {
                        'windowId': (await cdp.send('Browser.getWindowForTarget'))['windowId'],
                        'bounds': {'left': 100, 'top': 100, 'width': 1280, 'height': 900, 'windowState': 'normal'}
                    })
                    self.logger.info("🪟 Browser window brought to front for manual CAPTCHA solving")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not bring window to front: {e}")

                try:
                    # Wait loop - check every 1s if protection is gone
                    # We check title changes or specific element disappearance
                    for i in range(300): # 300 seconds = 5 mins
                        # Check if title changed from "Just a moment..." or protection markers are gone
                        title = await page.title()
                        content = await page.content()
                        
                        still_protected = ('Just a moment...' in title or 
                                         'Security Challenge' in title or
                                         'Waiting for you to skip the captcha' in content)
                        
                        if not still_protected:
                            self.logger.info("✅ CAPTCHA solved! Resuming scraper...")
                            
                            # Save state for future runs
                            storage_path = self.settings.get('STORAGE_STATE_PATH')
                            if storage_path:
                                context = page.context
                                await context.storage_state(path=storage_path)
                                self.logger.info(f"💾 Session saved to {storage_path}")
                            
                            # Update response with new content
                            body = await page.content()
                            response = response.replace(body=body, encoding='utf-8')
                            
                            # Break the loop and continue processing logic below
                            break
                        
                        if i % 10 == 0:
                            self.logger.info(f"⏳ Still waiting... ({i}s elapsed)")
                        
                        await page.wait_for_timeout(1000)
                    else:
                        self.logger.error("❌ Timed out waiting for manual solution.")
                        await page.close()
                        return

                except Exception as e:
                    self.logger.error(f"⚠️ Error during manual bypass: {e}")
                    await page.close()
                    return

            else:
                self.logger.error(f"🛡️ Advanced bot protection detected.")
                self.logger.warning(f"⚠️ Cannot bypass in HEADLESS mode. Set HEADLESS=False in settings.py to solve manually.")
                self.logger.info(f"⏹️ Stopping scraper - protection block.")

                # Close page if exists
                if page:
                    await page.close()

                # Stop the entire spider immediately
                self.crawler.engine.close_spider(self, 'cloudflare_protection_detected')
                return

        page = response.meta.get("playwright_page")
        if page:
            # Stealth is now applied in init_page callback

            # ── Infinite Scroll Handling ──────────────────────────
            if self.infinite_scroll:
                self.logger.info(f"📜 Starting infinite scroll ({self.scroll_count} times)...")
                previous_height = await page.evaluate("document.body.scrollHeight")
                
                for i in range(self.scroll_count):
                    # Scroll to bottom smoothly using JS
                    self.logger.info(f"   Scroll {i+1}/{self.scroll_count}...")
                    
                    await page.evaluate("""
                        async () => {
                            await new Promise((resolve) => {
                                var timer = setInterval(() => {
                                    var scrollHeight = document.body.scrollHeight;
                                    var currentScroll = window.innerHeight + window.scrollY;
                                    
                                    if(currentScroll >= scrollHeight){
                                        clearInterval(timer);
                                        resolve();
                                    }
                                    
                                    window.scrollBy(0, 150);
                                }, 100);
                            });
                        }
                    """)
                    
                    # Wait for load
                    await page.wait_for_timeout(self.scroll_delay * 1000)
                    
                    # Optional: Check if height changed to stop early (if desired, but simple loop is safer for now)
                    # new_height = await page.evaluate("document.body.scrollHeight")
                    # if new_height == previous_height:
                    #     self.logger.info("   Height didn't change, stopping scroll.")
                    #     break
                    # previous_height = new_height

                content = await page.content()
                response = response.replace(body=content, encoding='utf-8')
                self.logger.info("📜 Infinite scroll complete. Page content updated.")

            # ── Pre-Scraping Actions (First Page or All Pages) ────────────────
            if (self.page_count == 1 or self.pre_scrape_all_pages) and self.pre_scrape_clicks:
                self.logger.info(f"🖱️ Performing pre-scraping clicks...")
                selectors = [s.strip() for s in self.pre_scrape_clicks.split(';;') if s.strip()]
                
                for i, sel in enumerate(selectors):
                    try:
                        self.logger.info(f"   Clicking pre-scrape {i+1}/{len(selectors)}: '{sel}'")
                        el = await page.wait_for_selector(sel, timeout=10000, state='visible')
                        if el:
                            await el.click()
                            await page.wait_for_timeout(self.page_delay * 1000)
                        else:
                            self.logger.warning(f"⚠️ Pre-scrape selector '{sel}' not found or hidden.")
                    except Exception as e:
                        self.logger.warning(f"⚠️ Error clicking pre-scrape selector '{sel}': {e}")
                
                # Update response content
                content = await page.content()
                response = response.replace(body=content, encoding='utf-8')
                self.logger.info("✅ Pre-scraping actions complete. Page content updated.")

            # ── Click Sequence Handling (Pagination) ──────────────
            elif self.pagination_type == 'click' and self.pagination_sel:
                self.logger.info(f"🔘 Starting 'Click Sequence' (Max {self.max_pages} iterations)...")
                
                # Parse sequence
                selectors = [s.strip() for s in self.pagination_sel.split(';;') if s.strip()]
                
                for i in range(self.max_pages):
                    iteration_success = True
                    for sel_idx, sel in enumerate(selectors):
                        try:
                            # Check if button is visible
                            button = await page.query_selector(sel)
                            
                            if not button or not await button.is_visible():
                                self.logger.info(f"   Selector '{sel}' (step {sel_idx+1}) not found or hidden. Stopping sequence.")
                                iteration_success = False
                                break
                                
                            self.logger.info(f"   Iteration {i+1}: Clicking '{sel}'...")
                            await button.click()
                            
                            # Wait depending on if it's the last step or intermediate
                            wait_ms = self.page_delay * 1000 if sel_idx == len(selectors) - 1 else 1000
                            await page.wait_for_timeout(wait_ms)
                            
                        except Exception as e:
                            self.logger.warning(f"⚠️ Error in click sequence at '{sel}': {e}")
                            iteration_success = False
                            break
                    
                    if not iteration_success:
                        break

                # Update response with new content after clicking
                content = await page.content()
                response = response.replace(body=content, encoding='utf-8')
                self.logger.info("🔘 'Click Sequence' complete. Page content updated.")

        # ── 1. Extract Items ──────────────────────────────────
        cards = response.css(self.container_sel)

        if not cards:
            # FALLBACK: Try to parse generic "siteData" or similar JSON variables often used in WP themes
            # We look for "var siteData = {...};" pattern
            # DISABLED BY USER REQUEST: "JSON Fallback" was extracting unwanted fields (phone) and checking for implicit data.
            # try:
            #     # Regex for siteData (non-greedy until first semicolon)
            #     json_match = re.search(r'var siteData\s*=\s*({.*?});', response.text, re.DOTALL)
            #     
            #     if json_match:
            #         json_str = json_match.group(1)
            #         self.logger.info("Found 'siteData' JSON variable. Parsing...")
            #         data = json.loads(json_str)
            #         
            #         # Look for likely keys containing list of members
            #         # Specific to this user's case: "teamMembersForSiteData"
            #         # But let's be slightly generic if possible, or just specific for now
            #         members_list = data.get('teamMembersForSiteData')
            #         
            #         if members_list and isinstance(members_list, list):
            #             self.logger.info(f"🎉 JSON Fallback SUCCESS! Found {len(members_list)} items in variable.")
            #             
            #             for m in members_list:
            #                 item = EmployeeItem() # Use EmployeeItem
            #                 # Map fields
            #                 item['name'] = m.get('name') or m.get('post_title')
            #                 item['position'] = m.get('role') or m.get('job_title') # Changed 'title' to 'position'
            #                 item['email'] = m.get('email', '') # JSON might not have it
            #                 item['phone'] = m.get('phone', '')
            #                 item['image_url'] = m.get('thumbnail') or m.get('image')
            #                 item['profile_url'] = m.get('link') or m.get('url')
            #                 item['description'] = "" # generic
            #                 item['company_url'] = self.start_url # Add company_url
            #                 item['page_url'] = response.url # Add page_url
            #                 
            #                 # Clean up
            #                 if item['profile_url'] and not item['profile_url'].startswith('http'):
            #                     item['profile_url'] = urljoin(response.url, item['profile_url'])
            #                     
            #                 yield item
            #             return # SUCCESS - Stop processing
            #         else:
            #             self.logger.warning("JSON found but 'teamMembersForSiteData' key missing or empty.")
            # except Exception as e:
            #     self.logger.error(f"JSON Fallback failed: {e}")
            
            # If fallback failed, proceed to standard failure handling
            # No items on this page - might be empty pagination page (e.g., letter with no employees)
            if self.page_count == 1:
                # First page has no results.
                if self.pagination_sel:
                    self.logger.warning(f"⚠️ No items found on first page with '{self.container_sel}'. Checking for pagination links...")
                else:
                    self.logger.error(f"❌ No items found with selector '{self.container_sel}' on first page")
                    self.logger.info(f"💡 Test in console: document.querySelectorAll('{self.container_sel}').length")
                    
                    # DEBUG: Save page content to verify what we saw
                    try:
                        with open("debug_failed_page.html", "wb") as f:
                            f.write(response.body)
                        self.logger.info(f"📸 Saved 'debug_failed_page.html' for inspection.")
                    except: pass
                    return # Stop processing this page if first page has no results AND no pagination
            else:
                # Pagination page with no results - this is normal
                self.logger.info(f"ℹ️ No items on this page (empty results)")
            # Don't return - continue to pagination section
        else:
            self.logger.info(f"✅ Found {len(cards)} items")

            # Track if this is a listing page (has cards) vs a detail page
            is_listing_page = len(cards) > 1

            for card in cards:
                name = self._extract_name(card)
                position = self._extract_position(card)

                if self.profile_link_sel:
                    p_url = card.css('::attr(href)').get() if self.profile_link_sel.lower() == 'self' \
                        else card.css(f'{self.profile_link_sel}::attr(href)').get()

                    if p_url:
                        full_p_url = response.urljoin(p_url)
                        meta = {'name': name, 'position': position, 'listing_url': response.url}
                        if self.use_playwright:
                            # Don't block on email selector - make it optional
                            # Profile page will try to extract email even if selector not immediately visible
                            email_sel = self.profile_email_sel or self.email_sel
                            meta.update(self._get_playwright_meta(selector=None, wait_time=3000, selector_optional=True))
                            meta['email_sel'] = email_sel  # Pass selector for parsing

                        yield response.follow(full_p_url, self.parse_profile, meta=meta)
                        continue

                yield self._extract_item_from_card(card, response.url)

        # ── 2. Pagination ─────────────────────────────────────
        # Use buffer (< max_pages - 1) to prevent over-queuing due to async request handling
        if self.pagination_sel and self.page_count < self.max_pages - 1:
            if self.pagination_type == 'link':
                links = response.css(f'{self.pagination_sel}::attr(href)').getall()

                if not links:
                    # Check if selector matches elements but they don't have href
                    elements_count = len(response.css(self.pagination_sel).getall())

                    if elements_count > 0:
                        # Selector matches elements, but no href attributes found
                        self.logger.warning(f"⚠️ Found {elements_count} elements with selector '{self.pagination_sel}', but no href attributes")
                        self.logger.info(f"💡 Your selector might match non-link elements. Try: '{self.pagination_sel} a' or check if links exist")
                    else:
                        # Selector doesn't match anything
                        self.logger.warning(f"⚠️ No pagination links found with selector: '{self.pagination_sel}'")
                        self.logger.info(f"💡 Test in browser console: document.querySelectorAll('{self.pagination_sel}').length")
                else:
                    self.logger.debug(f"Found {len(links)} pagination links: {links[:5]}...")  # Show first 5
                    new_pages = 0
                    for link in links:
                        full_url = response.urljoin(link)
                        if full_url not in self.visited_urls:
                            new_pages += 1
                            self.logger.info(f"🔄 Queuing page: {full_url}")
                            for req in self._safe_follow(response, link):
                                yield req

                    if new_pages > 0:
                        self.logger.info(f"📊 Queued {new_pages} new pages total")

            elif self.pagination_type == 'param':
                values = response.css(f'{self.pagination_sel}::attr({self.data_attr})').getall() or \
                         response.css(f'{self.pagination_sel}::text').getall()

                if not values:
                    self.logger.warning(f"⚠️ No pagination values found")
                else:
                    new_pages = 0
                    for val in [v.strip() for v in values if v.strip()]:
                        base = self.start_url.split('?')[0]
                        link = f"{base}?{self.param_name}={val}"
                        full_url = response.urljoin(link)
                        if full_url not in self.visited_urls:
                            new_pages += 1
                            self.logger.info(f"🔄 Queuing page: {full_url}")
                            for req in self._safe_follow(response, link):
                                yield req

                    if new_pages > 0:
                        self.logger.info(f"📊 Queued {new_pages} new pages total")

            elif self.pagination_type == 'button':
                # Button-based pagination (Click elements without changing URL)
                values = response.css(f'{self.pagination_sel}::attr({self.data_attr})').getall() or \
                         response.css(f'{self.pagination_sel}::text').getall()

                if not values:
                    self.logger.warning(f"⚠️ No pagination buttons found with selector '{self.pagination_sel}'")
                else:
                    new_pages = 0
                    for val in [v.strip() for v in values if v.strip()]:
                        # Construct a selector for this specific button
                        # Try data attribute first, then text content
                        if response.css(f'{self.pagination_sel}[{self.data_attr}="{val}"]'):
                            btn_selector = f'{self.pagination_sel}[{self.data_attr}="{val}"]'
                        else:
                            # Fallback to text matching (less reliable but works)
                            btn_selector = f'{self.pagination_sel}:contains("{val}")'

                        # Key: We request the SAME URL, but with a click instruction
                        # We use the value as part of the URL fragment to make it unique in Scrapy's dupe filter
                        fake_url = f"{self.start_url}#page={val}"
                        
                        if fake_url not in self.visited_urls:
                            self.visited_urls.add(fake_url)
                            new_pages += 1
                            self.logger.info(f"🔄 Queuing click for: {val}")
                            
                            meta = self._get_playwright_meta(self.container_sel, self.page_delay * 1000, selector_optional=True)
                            
                            # 1. Click the category/letter button
                            meta['playwright_page_methods'].append(PageMethod('click', btn_selector))
                            
                            # 2. Click any post-selection buttons (e.g., "Search", "Apply")
                            if self.post_pagination_clicks:
                                post_sels = [s.strip() for s in self.post_pagination_clicks.split(';;') if s.strip()]
                                for post_sel in post_sels:
                                    meta['playwright_page_methods'].append(PageMethod('wait_for_selector', post_sel, timeout=5000, state='visible'))
                                    meta['playwright_page_methods'].append(PageMethod('click', post_sel))
                                    meta['playwright_page_methods'].append(PageMethod('wait_for_timeout', 1000))
                            
                            # 3. Final wait for results
                            meta['playwright_page_methods'].append(PageMethod('wait_for_load_state', self.wait_state))
                            
                            yield scrapy.Request(self.start_url, callback=self.parse, meta=meta, errback=self.errback_playwright, dont_filter=True)

                    if new_pages > 0:
                        self.logger.info(f"📊 Queued {new_pages} buttons to click")

        elif self.page_count >= self.max_pages - 1:
            self.logger.info(f"🛑 Reached max pages limit ({self.max_pages}), stopping pagination")

        if page:
            await page.close()

    async def parse_profile(self, response):
        page = response.meta.get("playwright_page")
        if page: await page.close()

        item = EmployeeItem()
        item['company_url'] = self.start_url
        item['page_url'] = response.url
        item['name'] = response.meta.get('name', 'Unknown')
        item['position'] = response.meta.get('position', '')

        # Get email selector from meta or use default
        email_sel = response.meta.get('email_sel') or self.profile_email_sel or self.email_sel

        # Try to extract email
        item['email'] = self._regex_email_extract(response, email_sel)

        if item['email']:
            # Build log message with position if available
            log_msg = f"✅ Profile: {item['name']}"
            if item.get('position'):
                log_msg += f" | Position: {item['position']}"
            log_msg += f" | Email: {item['email']}"
            self.logger.info(log_msg)
        else:
            # Check if selector exists at all
            elements_found = response.css(email_sel).getall()
            if elements_found:
                self.logger.warning(f"⚠️ Selector '{email_sel}' found but no email extracted for {item['name']}")
                self.logger.debug(f"Elements content: {elements_found[:200]}")
            else:
                self.logger.warning(f"❌ Selector '{email_sel}' not found on profile page for {item['name']}")
                self.logger.info(f"💡 Tip: Inspect {response.url} to find correct email selector")

        # Always yield item (even without email) so we don't lose the name/URL
        yield item

    def _safe_follow(self, response, link):
        target = response.urljoin(link)
        if target not in self.visited_urls:
            self.visited_urls.add(target)
            # Make container optional for pagination pages (they might have no results)
            meta = self._get_playwright_meta(self.container_sel, self.page_delay * 1000, selector_optional=True)
            yield scrapy.Request(target, callback=self.parse, meta=meta, errback=self.errback_playwright)

    def _get_playwright_meta(self, selector=None, wait_time=None, selector_optional=False):
        methods = [PageMethod('wait_for_load_state', self.wait_state)]

        # If pre-scrape all pages is enabled, inject these clicks at the very beginning of the queue
        if self.pre_scrape_all_pages and self.pre_scrape_clicks:
            selectors = [s.strip() for s in self.pre_scrape_clicks.split(';;') if s.strip()]
            for sel in selectors:
                # We use wait_for_selector + click for each pre-scrape action
                methods.append(PageMethod('wait_for_selector', sel, timeout=10000, state='visible'))
                methods.append(PageMethod('click', sel))
                methods.append(PageMethod('wait_for_timeout', 1000)) # Small breather between menu clicks

        if wait_time: methods.append(PageMethod('wait_for_timeout', wait_time))

        # Only wait for selector if it's explicitly required
        # For main page, we rely on load_state to avoid timeouts on complex selectors
        if selector and not selector_optional and ',' not in selector:
            # Only use strict wait for simple single selectors
            methods.append(PageMethod('wait_for_selector', selector, timeout=self.timeout, state='attached'))

        meta = {
            'playwright': True,
            'playwright_include_page': True,
            'playwright_page_methods': methods
        }

        if self.shared_context_name:
            meta['playwright_context'] = self.shared_context_name
            
        # Add init callback for Stealth (apply BEFORE page loads)
        meta['playwright_page_init_callback'] = self.init_page

        return meta

    async def init_page(self, page, request):
        """Apply stealth mode before page loads"""
        stealth = Stealth()
        await stealth.apply_stealth_async(page)

    async def errback_playwright(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            try:
                # Check for Cloudflare/Protection on error (e.g. Timeout waiting for selector)
                try:
                    title = await page.title()
                    content = await page.content()  # Fetch content for check
                    
                    is_blocking_title = 'Just a moment...' in title or 'Security Challenge' in title
                    
                    is_cloudflare = (is_blocking_title or
                                     'Waiting for you to skip the captcha' in content)

                    headless = self.settings.getbool('HEADLESS')
                    
                    if is_cloudflare and not headless:
                        self.logger.warning(f"🛡️ Protection detected during error (Timeout?): {failure.request.url}")
                        self.logger.info("🤖 HEADLESS=False detected. Initiating 'Human in the Loop' bypass from error handler...")
                        self.logger.info(f"👉 ACTION REQUIRED: Please manually solve the CAPTCHA in the browser window.")

                        # Bring browser window to front (it starts off-screen)
                        try:
                            await page.bring_to_front()
                            cdp = await page.context.new_cdp_session(page)
                            await cdp.send('Browser.setWindowBounds', {
                                'windowId': (await cdp.send('Browser.getWindowForTarget'))['windowId'],
                                'bounds': {'left': 100, 'top': 100, 'width': 1280, 'height': 900, 'windowState': 'normal'}
                            })
                            self.logger.info("🪟 Browser window brought to front for manual CAPTCHA solving")
                        except Exception as e:
                            self.logger.warning(f"⚠️ Could not bring window to front: {e}")

                        # Wait loop
                        for i in range(300):
                            
                            title = await page.title()
                            content = await page.content()
                            
                            still_protected = ('Just a moment...' in title or 
                                             'Security Challenge' in title or
                                             'Waiting for you to skip the captcha' in content)
                            
                            if not still_protected:
                                self.logger.info("✅ CAPTCHA solved! Saving state and RETRYING request...")
                                storage_path = self.settings.get('STORAGE_STATE_PATH')
                                if storage_path:
                                    await page.context.storage_state(path=storage_path)
                                
                                await page.close()
                                # Retry the request (new cookies should work now)
                                yield failure.request.replace(dont_filter=True)
                                return

                            if i % 10 == 0:
                                self.logger.info(f"⏳ Waiting for solution... ({i}s)")
                            await page.wait_for_timeout(1000)
                        
                        self.logger.error("❌ Timed out waiting for manual solution in errback.")

                except Exception as check_e:
                    self.logger.warning(f"⚠️ Error checking for Cloudflare in errback: {check_e}")

                # ── TIMEOUT HANDLING (Graceful Degradation) ───────────────────
                import playwright.async_api
                if isinstance(failure.value, playwright.async_api.TimeoutError):
                    self.logger.warning(f"⚠️ Timeout waiting for selector on {failure.request.url}")
                    self.logger.info("⏳ Attempting to parse page anyway (content might be partial)...")
                    
                    # Capture current state and proceed
                    content = await page.content()
                    from scrapy.http import HtmlResponse
                    response = HtmlResponse(
                        url=failure.request.url,
                        status=200,
                        body=content.encode('utf-8'),
                        request=failure.request,
                        encoding='utf-8'
                    )
                    # Pass the page object in meta so it can be closed later if needed
                    response.meta['playwright_page'] = page
                    
                    # Call parse manually
                    # We must be careful: parse is async generator, we need to iterate it
                    # But errback can be async generator too? Yes.
                    async for item in self.parse(response):
                        yield item
                        
                    await page.close()
                    return

                self.logger.error(f"❌ Playwright Error on {failure.request.url}: {failure.value}")
                await page.screenshot(path="error_screenshot.png", full_page=True)
                self.logger.info("📸 Saved error_screenshot.png")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to handle errback: {e}")
            await page.close()
        else:
             self.logger.error(f"❌ Request failed: {failure.request.url} - {failure.value}")

    def _extract_name(self, card):
        """
        Extract name from card. Supports both single-selector and multi-selector modes.

        Multi-selector mode: Combines text from multiple elements (e.g., first + last name)
        Single-selector mode: Extracts from first matching element (backward compatible)
        """
        # 1. Multi-selector mode (NEW - for split names)
        if hasattr(self, 'name_selectors') and self.name_selectors:
            parts = []
            for selector in self.name_selectors:
                # Extract text from this selector
                text = card.css(f'{selector}::text').get()
                if text and text.strip():
                    parts.append(text.strip())

            # If we found any parts, join them
            if parts:
                return " ".join(parts)

            # If multi-selector mode but nothing found, try fallback
            # (don't return "Unknown" yet - try single selector first)

        # 2. Single selector mode (EXISTING - backward compatible)
        if hasattr(self, 'name_sel') and self.name_sel:
            name = card.css(f'{self.name_sel}::text').get()
            if name and name.strip():
                return name.strip()

        # 3. Fallback to XPath (EXISTING - last resort)
        name = card.xpath('.//text()[normalize-space()]').get()
        return name.strip() if name else "Unknown"

    def _extract_position(self, card):
        """
        Extract position/title from card using CSS selector.
        Returns empty string if not found.
        """
        if not hasattr(self, 'position_sel') or not self.position_sel:
            return ""
        
        # Try each selector in the comma-separated list
        selectors = [s.strip() for s in self.position_sel.split(',')]
        for selector in selectors:
            position = card.css(f'{selector}::text').get()
            if position and position.strip():
                return position.strip()
        
        return ""

    def _extract_item_from_card(self, card, page_url):
        item = EmployeeItem()
        item['company_url'] = self.start_url
        item['page_url'] = page_url
        item['name'] = self._extract_name(card)
        item['email'] = self._regex_email_extract(card, self.email_sel)
        item['position'] = self._extract_position(card)
        
        # Log the extracted item
        if item['email']:
            log_msg = f"✅ Found: {item['name']}"
            if item.get('position'):
                log_msg += f" | Position: {item['position']}"
            log_msg += f" | Email: {item['email']}"
            self.logger.info(log_msg)
        else:
            log_msg = f"ℹ️ Found: {item['name']}"
            if item.get('position'):
                log_msg += f" | Position: {item['position']}"
            log_msg += " | Email: Not found"
            self.logger.info(log_msg)
        
        return item

    def _regex_email_extract(self, sel_obj, css_sel):
        # 1. Mailto
        raw_href = sel_obj.css(f'{css_sel}::attr(href)').get() or ""
        if 'mailto:' in raw_href:
            return raw_href.split('mailto:')[-1].split('?')[0].strip()

        # 2. Visible text
        target_text = " ".join(sel_obj.css(f'{css_sel} ::text').getall()).strip()

        # 3. Regex Fallback
        search_blob = target_text if '@' in target_text else " ".join(sel_obj.css('::text').getall())
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', search_blob)
        return match.group(0) if match else ""

    def errback_httpbin(self, failure):
        request = failure.request
        error_msg = str(failure.value)

        # CRITICAL: Clean up Playwright page if it exists (prevents resource leaks)
        page = request.meta.get("playwright_page")
        if page:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(page.close())
                else:
                    asyncio.run(page.close())
            except Exception as e:
                self.logger.warning(f"⚠️ Could not close page: {e}")

        # Check for Cloudflare Turnstile (advanced bot protection)
        if hasattr(failure.value, 'response'):
            response_body = getattr(failure.value.response, 'text', '')

            # Detect Cloudflare Turnstile challenge
            if ('challenges.cloudflare.com/turnstile' in response_body or
                'cdn-cgi/challenge-platform' in response_body or
                'cf_chl_' in response_body):

                self.logger.error(f"🛡️ CLOUDFLARE TURNSTILE detected on {request.url}")
                self.logger.warning(f"⚠️ This site has advanced bot protection that cannot be bypassed with basic tools")
                self.logger.info(f"💡 Tip: Set max_pages=1 to only scrape first page and avoid protection")
                self.logger.info(f"⏹️ Stopping scraper - first page data saved successfully")

                # Stop the entire spider (don't waste time on queued pages)
                self.crawler.engine.close_spider(self, 'cloudflare_protection_detected')
                return

        # Check for HTTP status code errors (bot detection, rate limits, etc.)
        if hasattr(failure.value, 'response'):
            status = failure.value.response.status
            if status == 403:
                self.logger.error(f"🚫 403 Forbidden - Likely bot detection on {request.url}")
                self.logger.info(f"💡 Website blocked this request. Suggestions:")
                self.logger.info(f"   1. Increase DOWNLOAD_DELAY in settings.py")
                self.logger.info(f"   2. This page will be retried automatically")
                return  # Let retry middleware handle it
            elif status == 429:
                self.logger.error(f"⏱️ 429 Too Many Requests - Rate limited on {request.url}")
                self.logger.info(f"💡 You're requesting too fast. Will retry with backoff.")
                return  # Let retry middleware handle it
            elif status == 404:
                self.logger.warning(f"❓ 404 Not Found - Page doesn't exist: {request.url}")
                return  # Don't retry 404s
            elif status >= 400:
                self.logger.error(f"❌ HTTP {status} error on {request.url}")

        # Check for common errors and provide helpful messages
        if "TimeoutError" in error_msg or "Timeout" in error_msg:
            if "wait_for_selector" in error_msg:
                # Extract selector from error message
                self.logger.error(f"❌ TIMEOUT: Selector not found within 30 seconds on {request.url}")
                self.logger.info(f"💡 Possible issues:")
                self.logger.info(f"   1. Selector is wrong - check browser DevTools")
                self.logger.info(f"   2. Element loads slowly - increase wait time")
                self.logger.info(f"   3. Element doesn't exist on this page type")
                self.logger.info(f"💡 Scraper will continue with other pages...")
            else:
                self.logger.error(f"❌ TIMEOUT: Page took too long to load: {request.url}")
        elif "CAPTCHA" in error_msg.upper():
            self.logger.error(f"🚫 CAPTCHA detected on {request.url}")
            self.logger.info(f"💡 Partial results are saved. You may need to:")
            self.logger.info(f"   1. Increase delays between requests")
            self.logger.info(f"   2. Use residential proxies")
            self.logger.info(f"   3. Try again later")
        else:
            self.logger.error(f"❌ Request failed: {request.url}")
            self.logger.error(f"Error: {error_msg[:200]}")

        # Don't re-raise - continue scraping other pages