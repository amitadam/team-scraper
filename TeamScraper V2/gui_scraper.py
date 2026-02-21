import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import subprocess
import threading
import queue
import os
import sys
import json
import re
from datetime import datetime

# --- AZURE THEME CONSTANTS ---
class AzureTheme:
    BG_ROOT = "#2b2b2b"      # Main window background
    BG_SIDEBAR = "#252526"   # VS Code / Azure sidebar
    BG_CONTENT = "#1e1e1e"   # Editor area
    BG_INPUT = "#3c3c3c"     # Input fields
    
    TEXT_MAIN = "#cccccc"    # Primary text
    TEXT_MUTED = "#858585"   # Secondary text
    
    ACCENT = "#007fd4"       # Azure Blue
    ACCENT_HOVER = "#006ca3"
    
    BORDER = "#3e3e42"       # Subtle borders
    SUCCESS = "#89d185"
    WARNING = "#dbab09"
    ERROR = "#f48771"

    FONT_UI = ('Segoe UI', 10)
    FONT_HEADER = ('Segoe UI', 14, 'bold')
    FONT_LABEL = ('Segoe UI', 11)
    FONT_MONO = ('Consolas', 10)

CONFIG_FILE = "scraper_config.json"

class ToolTip:
    """Modern ToolTip implementation"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        try:
            x, y, _, _ = self.widget.bbox("insert")
            x += self.widget.winfo_rootx() + 25
            y += self.widget.winfo_rooty() + 25

            self.tooltip = tk.Toplevel(self.widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")

            label = tk.Label(self.tooltip, text=self.text, justify='left',
                            background=AzureTheme.BG_SIDEBAR, 
                            foreground=AzureTheme.TEXT_MAIN,
                            relief='solid', borderwidth=1,
                            font=AzureTheme.FONT_UI,
                            padx=8, pady=4)
            label.pack()
        except: pass

    def hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class ModernButton(tk.Button):
    """Custom flat button with hover effects"""
    def __init__(self, master, text, command, bg=AzureTheme.ACCENT, fg="white", font=('Segoe UI', 10, 'bold'), padx=15, pady=6, **kwargs):
        super().__init__(master, text=text, command=command, 
                        bg=bg, fg=fg, 
                        relief="flat", activebackground=AzureTheme.ACCENT_HOVER, 
                        activeforeground="white", font=font, 
                        padx=padx, pady=pady, bd=0, **kwargs)
        self.default_bg = bg
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        self['bg'] = AzureTheme.ACCENT_HOVER

    def on_leave(self, e):
        self['bg'] = self.default_bg

class SidebarButton(tk.Button):
    """Sidebar navigation button"""
    def __init__(self, master, text, command, selected=False):
        bg = AzureTheme.BG_CONTENT if selected else AzureTheme.BG_SIDEBAR
        fg = "white" if selected else AzureTheme.TEXT_MAIN
        super().__init__(master, text=text, command=command,
                        bg=bg, fg=fg,
                        relief="flat", activebackground=AzureTheme.BG_CONTENT,
                        activeforeground="white", font=('Segoe UI', 11),
                        anchor="w", padx=20, pady=10, bd=0)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.is_selected = selected

    def on_enter(self, e):
        if not self.is_selected:
            self['bg'] = "#3c3c3c"

    def on_leave(self, e):
        if not self.is_selected:
            self['bg'] = AzureTheme.BG_SIDEBAR

    def set_select(self, selected):
        self.is_selected = selected
        if selected:
            self['bg'] = AzureTheme.BG_CONTENT
            self['fg'] = "white"
            self['font'] = ('Segoe UI', 11, 'bold')
        else:
            self['bg'] = AzureTheme.BG_SIDEBAR
            self['fg'] = AzureTheme.TEXT_MAIN
            self['font'] = ('Segoe UI', 11)

class VisualScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Team Scraper V2")
        self.root.geometry("1150x750")
        self.root.configure(bg=AzureTheme.BG_ROOT)
        
        # Win10 Dark Title Bar Hack
        try:
            import ctypes
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.windll.user32.GetParent(root.winfo_id()), 20, ctypes.byref(ctypes.c_int(1)), 4)
        except: pass

        self._init_variables()
        self.load_config()
        self._setup_ui()
        
        # Start log processor
        self.root.after(100, self.process_log_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

    def _init_variables(self):
        self.url_var = tk.StringVar()
        self.container_var = tk.StringVar(value="div.team-member")
        self.visible_browser = tk.BooleanVar(value=True)
        self.show_selectors = tk.BooleanVar(value=True) # Default true for power users
        self.name_var = tk.StringVar(value="h3.name")
        self.split_names = tk.BooleanVar(value=False)
        self.first_name_var = tk.StringVar(value=".first-name")
        self.middle_name_var = tk.StringVar(value=".middle-name")
        self.last_name_var = tk.StringVar(value=".last-name")
        self.email_var = tk.StringVar(value="a[href^='mailto:']")
        self.position_var = tk.StringVar(value=".position, .title")
        self.use_profile = tk.BooleanVar(value=False)
        self.profile_link_var = tk.StringVar(value="a.profile-link")
        self.profile_email_var = tk.StringVar(value="a[href^='mailto:']")
        self.has_pagination = tk.BooleanVar(value=True)
        self.pagination_type = tk.StringVar(value="link")
        self.pagination_sel_var = tk.StringVar(value="div.pagination a")
        self.data_attr_var = tk.StringVar(value="data-letter")
        self.param_name_var = tk.StringVar(value="letter")
        self.scroll_count_var = tk.StringVar(value="5")
        self.scroll_delay_var = tk.StringVar(value="2")
        self.max_pages_var = tk.StringVar(value="10")
        self.page_delay_var = tk.StringVar(value="5")
        self.pre_scrape_clicks = tk.StringVar(value="")
        self.pre_scrape_all_pages = tk.BooleanVar(value=False)
        self.post_pagination_clicks = tk.StringVar(value="")
        self.format_var = tk.StringVar(value="json")
        self.download_delay_var = tk.StringVar(value="2")
        self.timeout_var = tk.StringVar(value="60")
        self.wait_state = tk.StringVar(value="networkidle")
        self.randomize_delays = tk.BooleanVar(value=True)
        self.auto_throttle = tk.BooleanVar(value=True)
        self.throttle_start_var = tk.StringVar(value="403, 429, 503")
        self.preset_var = tk.StringVar(value="Balanced (recommended)")
        
        self.is_scraping = False
        self.scraping_process = None
        self.log_queue = queue.Queue()
        self.items_found = 0
        self.pages_scraped = 0

    def _setup_ui(self):
        # Main Split (Sidebar | Content)
        main_split = tk.Frame(self.root, bg=AzureTheme.BG_ROOT)
        main_split.pack(fill=tk.BOTH, expand=True)
        
        # Sidebar
        self.sidebar = tk.Frame(main_split, bg=AzureTheme.BG_SIDEBAR, width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        
        # Sidebar Header
        tk.Label(self.sidebar, text="TEAM SCRAPER", bg=AzureTheme.BG_SIDEBAR, fg=AzureTheme.ACCENT, 
                font=('Segoe UI', 14, 'bold'), anchor="w").pack(fill=tk.X, padx=20, pady=20)
        
        # Navigation Buttons
        self.nav_buttons = {}
        self.nav_buttons['general'] = SidebarButton(self.sidebar, "🏠  Start & Target", lambda: self.show_tab('general'), True)
        self.nav_buttons['general'].pack(fill=tk.X)
        
        self.nav_buttons['data'] = SidebarButton(self.sidebar, "🔍  Data Selection", lambda: self.show_tab('data'))
        self.nav_buttons['data'].pack(fill=tk.X)
        
        self.nav_buttons['pagination'] = SidebarButton(self.sidebar, "📄  Pagination", lambda: self.show_tab('pagination'))
        self.nav_buttons['pagination'].pack(fill=tk.X)
        
        self.nav_buttons['advanced'] = SidebarButton(self.sidebar, "⚙️  Advanced", lambda: self.show_tab('advanced'))
        self.nav_buttons['advanced'].pack(fill=tk.X)

        self.nav_buttons['run'] = SidebarButton(self.sidebar, "🚀  Run Scanner", lambda: self.show_tab('run'))
        self.nav_buttons['run'].pack(fill=tk.X)

        
        # Action Buttons (Bottom of sidebar) - REMOVED (User request: declutter)
        spacer = tk.Frame(self.sidebar, bg=AzureTheme.BG_SIDEBAR)
        spacer.pack(fill=tk.BOTH, expand=True)
        
        # Content Area
        self.content_area = tk.Frame(main_split, bg=AzureTheme.BG_CONTENT)
        self.content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Log Console (Bottom Panel)
        self.log_panel = tk.Frame(self.content_area, bg=AzureTheme.BG_INPUT, height=200)
        self.log_panel.pack(side=tk.BOTTOM, fill=tk.X)
        self.log_panel.pack_propagate(False)
        
        # Log Header
        log_header = tk.Frame(self.log_panel, bg="#252526", height=28)
        log_header.pack(fill=tk.X)
        tk.Label(log_header, text="OUTPUT LOGS", bg="#252526", fg="#cccccc", font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=10, pady=4)
        
        self.status_lbl = tk.Label(log_header, text="Ready", bg="#252526", fg=AzureTheme.SUCCESS, font=('Segoe UI', 9))
        self.status_lbl.pack(side=tk.RIGHT, padx=10)
        
        # Scrolled Text
        self.log_text = scrolledtext.ScrolledText(self.log_panel, bg="#1e1e1e", fg="#cccccc", 
                                                 font=AzureTheme.FONT_MONO, state=tk.DISABLED, bd=0)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self._configure_log_tags()

        # --- Tab Frames ---
        self.tabs = {}
        self.tabs['general'] = self._build_general_tab()
        self.tabs['data'] = self._build_data_tab()
        self.tabs['pagination'] = self._build_pagination_tab()
        self.tabs['advanced'] = self._build_advanced_tab()
        self.tabs['run'] = self._build_run_tab()
        
        # Show default
        self.show_tab('general')

    def show_tab(self, tab_name):
        # Update Nav Styles
        for name, btn in self.nav_buttons.items():
            btn.set_select(name == tab_name)
            
        # Hide all tabs
        for tab in self.tabs.values():
            tab.pack_forget()
            
        # Show selected
        self.tabs[tab_name].pack(fill=tk.BOTH, expand=True, padx=40, pady=30)

    # --- BUILDERS ---
    def _lbl(self, parent, text, h=False):
        font = AzureTheme.FONT_HEADER if h else AzureTheme.FONT_LABEL
        fg = AzureTheme.ACCENT if h else AzureTheme.TEXT_MAIN
        tk.Label(parent, text=text, bg=AzureTheme.BG_CONTENT, fg=fg, font=font).pack(anchor="w", pady=(20 if h else 10, 5))

    def _hint(self, parent, text):
        """Add a muted hint/description below a field"""
        tk.Label(parent, text=text, bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MUTED,
                font=('Segoe UI', 9), wraplength=500, justify="left").pack(anchor="w", pady=(0, 8))

    def _entry(self, parent, var, width=40, title=None, hint=None):
        if title: self._lbl(parent, title)
        e = tk.Entry(parent, textvariable=var, width=width, bg=AzureTheme.BG_INPUT, fg="white",
                    insertbackground="white", bd=1, relief="solid", font=('Segoe UI', 10))
        e.pack(anchor="w", pady=(0, 5), ipady=4)
        if hint: self._hint(parent, hint)
        return e

    def _create_scrollable_frame(self, parent):
        """Create a scrollable frame for tab content"""
        # Canvas for scrolling
        canvas = tk.Canvas(parent, bg=AzureTheme.BG_CONTENT, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=AzureTheme.BG_CONTENT)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        return scrollable_frame

    def _build_general_tab(self):
        wrapper = tk.Frame(self.content_area, bg=AzureTheme.BG_CONTENT)
        f = self._create_scrollable_frame(wrapper)

        self._lbl(f, "What do you want to scrape?", h=True)

        self._entry(f, self.url_var, 60, "Website URL",
                   hint="The page that shows the list of team members, employees, or people you want to extract.")

        self._entry(f, self.container_var, 50, "Person Card Selector",
                   hint="CSS selector for each person's card/box. Example: div.team-member, .profile-card, or a.employee-link")

        tk.Label(f, text="", bg=AzureTheme.BG_CONTENT).pack(pady=10)

        self._lbl(f, "Browser Mode", h=True)
        cb = tk.Checkbutton(f, text="Keep browser available for CAPTCHAs", variable=self.visible_browser,
                           bg=AzureTheme.BG_CONTENT, fg="white", selectcolor=AzureTheme.BG_INPUT,
                           activebackground=AzureTheme.BG_CONTENT, activeforeground="white",
                           font=AzureTheme.FONT_UI)
        cb.pack(anchor="w", pady=10)
        self._hint(f, "The browser runs hidden in the background. If a CAPTCHA appears, it will pop up so you can solve it manually. Uncheck for fully invisible (headless) mode.")

        return wrapper

    def _build_data_tab(self):
        wrapper = tk.Frame(self.content_area, bg=AzureTheme.BG_CONTENT)
        f = self._create_scrollable_frame(wrapper)

        self._lbl(f, "What data to extract from each person?", h=True)

        # Name Section
        self._lbl(f, "Name")
        self.name_entry = self._entry(f, self.name_var, 40,
                                      hint="CSS selector for the person's name. Example: h3.name, .employee-name")

        cb_split = tk.Checkbutton(f, text="Name is split into separate fields (First / Last)", variable=self.split_names,
                           bg=AzureTheme.BG_CONTENT, fg="white", selectcolor=AzureTheme.BG_INPUT,
                           activebackground=AzureTheme.BG_CONTENT, activeforeground="white",
                           command=lambda: self._toggle_split_names())
        cb_split.pack(anchor="w", pady=(5,0))

        split_frame = tk.Frame(f, bg=AzureTheme.BG_CONTENT)
        split_frame.pack(anchor="w", pady=5)

        self.fname_entry = tk.Entry(split_frame, textvariable=self.first_name_var, width=12, bg=AzureTheme.BG_INPUT, fg="white", bd=1, relief="solid")
        self.fname_entry.pack(side=tk.LEFT, padx=(0,5))
        self.mname_entry = tk.Entry(split_frame, textvariable=self.middle_name_var, width=12, bg=AzureTheme.BG_INPUT, fg="white", bd=1, relief="solid")
        self.mname_entry.pack(side=tk.LEFT, padx=5)
        self.lname_entry = tk.Entry(split_frame, textvariable=self.last_name_var, width=12, bg=AzureTheme.BG_INPUT, fg="white", bd=1, relief="solid")
        self.lname_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(split_frame, text="(First / Middle / Last)", bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=5)

        self._toggle_split_names()  # Init state

        # Position
        self._entry(f, self.position_var, 40, "Job Title / Role",
                   hint="CSS selector for position/role text. Example: .job-title, span.role")

        tk.Label(f, text="", bg=AzureTheme.BG_CONTENT).pack(pady=5)

        # Email - Two modes explained clearly
        self._lbl(f, "Email Extraction", h=True)
        self._hint(f, "Choose ONE of the two methods below based on how the website displays emails:")

        # Option A: Direct email on listing
        email_frame_a = tk.LabelFrame(f, text=" Option A: Email visible on the listing page ",
                                      bg=AzureTheme.BG_CONTENT, fg=AzureTheme.ACCENT,
                                      font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
        email_frame_a.pack(fill=tk.X, pady=10)

        tk.Label(email_frame_a, text="Use this when emails are shown directly on the team listing page.",
                bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 9)).pack(anchor="w")
        self.email_entry = tk.Entry(email_frame_a, textvariable=self.email_var, width=40, bg=AzureTheme.BG_INPUT, fg="white",
                    insertbackground="white", bd=1, relief="solid", font=('Segoe UI', 10))
        self.email_entry.pack(anchor="w", pady=5, ipady=4)
        tk.Label(email_frame_a, text="Example: a[href^='mailto:'], .email-link",
                bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 8)).pack(anchor="w")

        # Option B: Email on profile page
        email_frame_b = tk.LabelFrame(f, text=" Option B: Need to click into each profile to find email ",
                                      bg=AzureTheme.BG_CONTENT, fg=AzureTheme.ACCENT,
                                      font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
        email_frame_b.pack(fill=tk.X, pady=10)

        cb = tk.Checkbutton(email_frame_b, text="Enable profile page visits", variable=self.use_profile,
                           bg=AzureTheme.BG_CONTENT, fg="white", selectcolor=AzureTheme.BG_INPUT,
                           activebackground=AzureTheme.BG_CONTENT, activeforeground="white",
                           command=lambda: self._toggle_profile())
        cb.pack(anchor="w", pady=5)
        tk.Label(email_frame_b, text="Use this when you need to click on each person to see their email.",
                bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 9)).pack(anchor="w")

        tk.Label(email_frame_b, text="Link selector (what to click on listing page):",
                bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MAIN, font=('Segoe UI', 10)).pack(anchor="w", pady=(10,2))
        tk.Entry(email_frame_b, textvariable=self.profile_link_var, width=40, bg=AzureTheme.BG_INPUT, fg="white",
                bd=1, relief="solid", font=('Segoe UI', 10)).pack(anchor="w", ipady=4)
        tk.Label(email_frame_b, text="Use 'self' if the whole card is clickable, or a selector like a.view-profile",
                bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 8)).pack(anchor="w", pady=(2,10))

        tk.Label(email_frame_b, text="Email selector (on the individual profile page):",
                bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MAIN, font=('Segoe UI', 10)).pack(anchor="w", pady=(5,2))
        tk.Entry(email_frame_b, textvariable=self.profile_email_var, width=40, bg=AzureTheme.BG_INPUT, fg="white",
                bd=1, relief="solid", font=('Segoe UI', 10)).pack(anchor="w", ipady=4)
        tk.Label(email_frame_b, text="Example: a[href^='mailto:'], .contact-email",
                bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 8)).pack(anchor="w")

        self._toggle_profile()  # Init state

        return wrapper

    def _toggle_split_names(self):
        if self.split_names.get():
            self.name_entry.config(state='disabled', bg=AzureTheme.BG_SIDEBAR)
            self.fname_entry.config(state='normal', bg=AzureTheme.BG_INPUT)
            self.mname_entry.config(state='normal', bg=AzureTheme.BG_INPUT)
            self.lname_entry.config(state='normal', bg=AzureTheme.BG_INPUT)
        else:
            self.name_entry.config(state='normal', bg=AzureTheme.BG_INPUT)
            self.fname_entry.config(state='disabled', bg=AzureTheme.BG_SIDEBAR)
            self.mname_entry.config(state='disabled', bg=AzureTheme.BG_SIDEBAR)
            self.lname_entry.config(state='disabled', bg=AzureTheme.BG_SIDEBAR)

    def _toggle_profile(self):
        if self.use_profile.get():
            self.email_entry.config(state='disabled', bg=AzureTheme.BG_SIDEBAR)
        else:
            self.email_entry.config(state='normal', bg=AzureTheme.BG_INPUT)

    def _build_pagination_tab(self):
        wrapper = tk.Frame(self.content_area, bg=AzureTheme.BG_CONTENT)
        f = self._create_scrollable_frame(wrapper)

        self._lbl(f, "How does the site show more people?", h=True)
        self._hint(f, "If all team members are on one page, you can skip this section.")

        cb = tk.Checkbutton(f, text="Site has multiple pages or sections to scrape", variable=self.has_pagination,
                           bg=AzureTheme.BG_CONTENT, fg="white", selectcolor=AzureTheme.BG_INPUT,
                           activebackground=AzureTheme.BG_CONTENT, activeforeground="white")
        cb.pack(anchor="w", pady=5)

        self._lbl(f, "Navigation Type")

        # Radio Frame with descriptions
        rf = tk.Frame(f, bg=AzureTheme.BG_CONTENT)
        rf.pack(anchor="w", pady=10)

        modes = [
            ("Next/Previous links", "link", "Site has clickable page links (1, 2, 3... or Next button)"),
            ("URL changes (?page=2)", "param", "Page number appears in the URL"),
            ("Letter/Category buttons (A-Z)", "button", "Buttons that filter without changing URL"),
            ("'Load More' button", "click", "Single button that loads more results"),
            ("Infinite scroll", "infinite", "Content loads automatically as you scroll down")
        ]

        for text, val, desc in modes:
            row = tk.Frame(rf, bg=AzureTheme.BG_CONTENT)
            row.pack(anchor="w", fill=tk.X)
            b = tk.Radiobutton(row, text=text, variable=self.pagination_type, value=val,
                              bg=AzureTheme.BG_CONTENT, fg="white", selectcolor=AzureTheme.BG_INPUT,
                              activebackground=AzureTheme.BG_CONTENT, activeforeground="white",
                              command=self._update_pag_ui)
            b.pack(side=tk.LEFT, pady=2)
            tk.Label(row, text=f"  - {desc}", bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MUTED,
                    font=('Segoe UI', 9)).pack(side=tk.LEFT)

        # Dynamic Settings Area
        tk.Label(f, text="", bg=AzureTheme.BG_CONTENT).pack(pady=5)
        self._lbl(f, "Settings for selected type")
        self.pag_settings_frame = tk.Frame(f, bg=AzureTheme.BG_CONTENT, bd=0)
        self.pag_settings_frame.pack(fill=tk.X, pady=5)

        self._update_pag_ui()

        return wrapper

    def _update_pag_ui(self):
        for w in self.pag_settings_frame.winfo_children(): w.destroy()

        ptype = self.pagination_type.get()
        p = self.pag_settings_frame

        if ptype == 'infinite':
            self._entry(p, self.scroll_count_var, 10, "How many times to scroll down",
                       hint="Each scroll loads more content. 5-10 is usually enough.")
        elif ptype == 'param':
            self._entry(p, self.param_name_var, 20, "URL parameter name",
                       hint="The part that changes in the URL. Usually 'page' or 'p'. Example: ?page=2")
            self._entry(p, self.pagination_sel_var, 40, "Page number buttons selector (optional)",
                       hint="If the site shows page numbers (1,2,3...), enter their selector here.")
        elif ptype == 'button':
            self._entry(p, self.pagination_sel_var, 40, "Category buttons selector",
                       hint="Selector for the A-Z letters or category buttons. Example: .option[data-target]")
            self._entry(p, self.data_attr_var, 20, "Data attribute (optional)",
                       hint="If buttons have attributes like data-target='35', enter 'data-target' here.")
            self._entry(p, self.post_pagination_clicks, 40, "Then click 'Search' button (optional)",
                       hint="If you need to hit a 'Search' or 'Apply' button after choosing a category, enter its selector here.")
        else:
            self._entry(p, self.pagination_sel_var, 40, "Next button / Link selector",
                       hint="Selector for the 'Next' button or pagination links. Example: a.next-page, .pagination a")

    def _build_advanced_tab(self):
        wrapper = tk.Frame(self.content_area, bg=AzureTheme.BG_CONTENT)
        f = self._create_scrollable_frame(wrapper)

        # ══════════════════════════════════════════════════════════════
        # SPEED & STEALTH - Preset-controlled settings
        # ══════════════════════════════════════════════════════════════
        self._lbl(f, "Speed & Stealth", h=True)

        preset_box = tk.LabelFrame(f, text=" Quick Presets ", bg=AzureTheme.BG_CONTENT,
                                   fg=AzureTheme.ACCENT, font=('Segoe UI', 10, 'bold'), padx=15, pady=15)
        preset_box.pack(fill=tk.X, pady=10)

        # Preset description
        tk.Label(preset_box, text="Presets automatically adjust the 3 settings below:",
                bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 9)).pack(anchor="w")

        # Preset dropdown
        preset_row = tk.Frame(preset_box, bg=AzureTheme.BG_CONTENT)
        preset_row.pack(anchor="w", pady=(10, 15))

        def apply_preset(event=None):
            p = self.preset_var.get()
            if p == "Fast (risky)":
                self.download_delay_var.set("0.5")
                self.randomize_delays.set(False)
                self.auto_throttle.set(False)
            elif p == "Balanced (recommended)":
                self.download_delay_var.set("2")
                self.randomize_delays.set(True)
                self.auto_throttle.set(True)
            elif p == "Careful (slow but safe)":
                self.download_delay_var.set("5")
                self.randomize_delays.set(True)
                self.auto_throttle.set(True)

        combo = ttk.Combobox(preset_row, textvariable=self.preset_var,
                            values=["Fast (risky)", "Balanced (recommended)", "Careful (slow but safe)", "Custom"],
                            state="readonly", width=24)
        combo.pack(side=tk.LEFT)
        combo.bind("<<ComboboxSelected>>", apply_preset)

        # The 3 settings controlled by presets (indented to show relationship)
        controlled_frame = tk.Frame(preset_box, bg=AzureTheme.BG_CONTENT)
        controlled_frame.pack(fill=tk.X, padx=10)

        # 1. Wait between pages
        row1 = tk.Frame(controlled_frame, bg=AzureTheme.BG_CONTENT)
        row1.pack(anchor="w", pady=3)
        tk.Label(row1, text="① Wait between pages:", bg=AzureTheme.BG_CONTENT,
                fg=AzureTheme.TEXT_MAIN, width=22, anchor="w").pack(side=tk.LEFT)
        tk.Entry(row1, textvariable=self.download_delay_var, bg=AzureTheme.BG_INPUT, fg="white", width=6).pack(side=tk.LEFT)
        tk.Label(row1, text=" seconds", bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MUTED).pack(side=tk.LEFT)

        # 2. Randomize
        row2 = tk.Frame(controlled_frame, bg=AzureTheme.BG_CONTENT)
        row2.pack(anchor="w", pady=3)
        tk.Label(row2, text="② ", bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MAIN).pack(side=tk.LEFT)
        tk.Checkbutton(row2, text="Randomize wait times", variable=self.randomize_delays,
                      bg=AzureTheme.BG_CONTENT, fg="white", selectcolor=AzureTheme.BG_INPUT,
                      activebackground=AzureTheme.BG_CONTENT, activeforeground="white").pack(side=tk.LEFT)
        tk.Label(row2, text="(vary timing to look more human)", bg=AzureTheme.BG_CONTENT,
                fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 9)).pack(side=tk.LEFT)

        # 3. Auto-throttle
        row3 = tk.Frame(controlled_frame, bg=AzureTheme.BG_CONTENT)
        row3.pack(anchor="w", pady=3)
        tk.Label(row3, text="③ ", bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MAIN).pack(side=tk.LEFT)
        tk.Checkbutton(row3, text="Auto slow-down if blocked", variable=self.auto_throttle,
                      bg=AzureTheme.BG_CONTENT, fg="white", selectcolor=AzureTheme.BG_INPUT,
                      activebackground=AzureTheme.BG_CONTENT, activeforeground="white").pack(side=tk.LEFT)
        tk.Label(row3, text="(backs off on 403/429 errors)", bg=AzureTheme.BG_CONTENT,
                fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 9)).pack(side=tk.LEFT)

        # ══════════════════════════════════════════════════════════════
        # LIMITS - Not controlled by presets
        # ══════════════════════════════════════════════════════════════
        self._lbl(f, "Limits", h=True)

        limits_row = tk.Frame(f, bg=AzureTheme.BG_CONTENT)
        limits_row.pack(anchor="w", pady=5)
        tk.Label(limits_row, text="Maximum pages to scrape:", bg=AzureTheme.BG_CONTENT,
                fg=AzureTheme.TEXT_MAIN).pack(side=tk.LEFT)
        tk.Entry(limits_row, textvariable=self.max_pages_var, bg=AzureTheme.BG_INPUT, fg="white", width=6).pack(side=tk.LEFT, padx=10)
        tk.Label(limits_row, text="(prevents runaway scraping)", bg=AzureTheme.BG_CONTENT,
                fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 9)).pack(side=tk.LEFT)

        # ══════════════════════════════════════════════════════════════
        # PAGE LOADING - Technical settings (not in presets)
        # ══════════════════════════════════════════════════════════════
        self._lbl(f, "Page Loading (Technical)", h=True)
        self._hint(f, "Usually you don't need to change these. Adjust if pages aren't loading properly.")

        tech_grid = tk.Frame(f, bg=AzureTheme.BG_CONTENT)
        tech_grid.pack(anchor="w", pady=5)

        # Timeout
        tk.Label(tech_grid, text="Give up waiting after:", bg=AzureTheme.BG_CONTENT,
                fg=AzureTheme.TEXT_MAIN).grid(row=0, column=0, sticky='w', pady=5)
        tk.Entry(tech_grid, textvariable=self.timeout_var, bg=AzureTheme.BG_INPUT, fg="white", width=6).grid(row=0, column=1, padx=5)
        tk.Label(tech_grid, text="seconds (for slow-loading pages)", bg=AzureTheme.BG_CONTENT,
                fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 9)).grid(row=0, column=2, sticky='w')

        # Wait strategy
        tk.Label(tech_grid, text="Consider page ready when:", bg=AzureTheme.BG_CONTENT,
                fg=AzureTheme.TEXT_MAIN).grid(row=1, column=0, sticky='w', pady=5)
        wait_combo = ttk.Combobox(tech_grid, textvariable=self.wait_state,
                                 values=["networkidle", "domcontentloaded", "load"], state="readonly", width=15)
        wait_combo.grid(row=1, column=1, columnspan=2, sticky='w', padx=5)

        # Wait strategy explanation in a subtle box
        wait_explain = tk.Label(f, text="  • networkidle - All requests finished (safest for JavaScript sites)\n"
                                        "  • domcontentloaded - HTML loaded (faster, good for simple sites)\n"
                                        "  • load - Basic load done (fastest, may miss dynamic content)",
                bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MUTED, font=('Segoe UI', 9), justify="left")
        wait_explain.pack(anchor="w", pady=(0, 10))

        # ══════════════════════════════════════════════════════════════
        # PRE-SCRAPE ACTIONS
        # ══════════════════════════════════════════════════════════════
        self._lbl(f, "Run Before Scraping", h=True)
        self._entry(f, self.pre_scrape_clicks, 50, "Click these elements first (optional)",
                   hint="Useful for accepting cookie banners or closing popups. Example: #accept-cookies, button.close-popup")
        
        cb_pre_all = tk.Checkbutton(f, text="Run these clicks on every page/category load", variable=self.pre_scrape_all_pages,
                           bg=AzureTheme.BG_CONTENT, fg="white", selectcolor=AzureTheme.BG_INPUT,
                           activebackground=AzureTheme.BG_CONTENT, activeforeground="white",
                           font=AzureTheme.FONT_UI)
        cb_pre_all.pack(anchor="w", pady=(5, 10))
        self._hint(f, "Check this if you need to open a menu or click a button to reveal the team list on every page visit.")

        return wrapper

    def _build_run_tab(self):
        wrapper = tk.Frame(self.content_area, bg=AzureTheme.BG_CONTENT)
        f = self._create_scrollable_frame(wrapper)

        # Centered Run Button
        c = tk.Frame(f, bg=AzureTheme.BG_CONTENT)
        c.pack(expand=True, pady=20)

        tk.Label(c, text="Ready to Scrape?", font=('Segoe UI', 20), bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MAIN).pack(pady=20)

        self.start_btn_lg = ModernButton(c, "START SCRAPING", self.start_scraping, font=('Segoe UI', 14, 'bold'), padx=30, pady=15)
        self.start_btn_lg.pack(pady=10)

        self.stop_btn_lg = ModernButton(c, "STOP", self.stop_scraping, bg=AzureTheme.ERROR, state=tk.DISABLED)
        self.stop_btn_lg.pack(pady=10)

        tk.Label(c, text="", bg=AzureTheme.BG_CONTENT).pack(pady=10)

        # Output Format
        format_frame = tk.Frame(c, bg=AzureTheme.BG_CONTENT)
        format_frame.pack(pady=10)
        tk.Label(format_frame, text="Save results as:", bg=AzureTheme.BG_CONTENT, fg=AzureTheme.TEXT_MAIN,
                font=('Segoe UI', 11)).pack(side=tk.LEFT, padx=5)
        ttk.Combobox(format_frame, textvariable=self.format_var, values=["json", "csv", "xlsx"], state="readonly", width=10).pack(side=tk.LEFT)

        self._hint(c, "Results are saved automatically as the scraper runs.")

        return wrapper

    # --- LOGGING & PROCESS ---
    def _configure_log_tags(self):
        self.log_text.tag_config('error', foreground=AzureTheme.ERROR)
        self.log_text.tag_config('success', foreground=AzureTheme.SUCCESS)
        self.log_text.tag_config('warning', foreground=AzureTheme.WARNING)
        self.log_text.tag_config('info', foreground="#4dabf7")

    def log_message(self, msg, tag=None):
        self.log_queue.put((msg, tag))

    def process_log_queue(self):
        while not self.log_queue.empty():
            item = self.log_queue.get()
            msg, tag = item if isinstance(item, tuple) else (item, None)
            
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + "\n", tag)
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            
        self.root.after(100, self.process_log_queue)

    def start_scraping(self):
        self.save_config()
        self.is_scraping = True
        self._set_state(True)
        self.log_message("Starting scraper...", "info")
        
        # ... (Same Run Logic as before) ...
        cmd = ["scrapy", "crawl", "team",
               "-a", f"url={self.url_var.get().strip()}",
               "-a", f"container={self.container_var.get().strip()}",
               "-a", f"format={self.format_var.get()}"]
        
        # Selectors
        if self.show_selectors.get():
            cmd.extend(["-a", f"name_sel={self.name_var.get()}"])
            if self.split_names.get():
                cmd.extend(["-a", "split_names=true"])
            if self.first_name_var.get(): cmd.extend(["-a", f"first_name_sel={self.first_name_var.get()}"])
            if self.last_name_var.get(): cmd.extend(["-a", f"last_name_sel={self.last_name_var.get()}"])
            if self.position_var.get(): cmd.extend(["-a", f"position_sel={self.position_var.get()}"])
            if self.email_var.get(): cmd.extend(["-a", f"email_sel={self.email_var.get()}"])
            
            if self.use_profile.get():
                cmd.extend(["-a", "use_playwright_profile=true"])
                cmd.extend(["-a", f"profile_link_sel={self.profile_link_var.get()}"])
                cmd.extend(["-a", f"profile_email_sel={self.profile_email_var.get()}"])

        # Pagination
        if self.has_pagination.get():
            ptype = self.pagination_type.get()
            if ptype == 'infinite':
                cmd.extend(["-a", "infinite_scroll=true"])
            else:
                cmd.extend(["-a", f"pagination_sel={self.pagination_sel_var.get()}"])
                cmd.extend(["-a", f"pagination_type={ptype}"])
                
            if self.data_attr_var.get(): cmd.extend(["-a", f"data_attr={self.data_attr_var.get()}"])
            if self.param_name_var.get(): cmd.extend(["-a", f"param_name={self.param_name_var.get()}"])
            if self.post_pagination_clicks.get(): cmd.extend(["-a", f"post_pagination_clicks={self.post_pagination_clicks.get()}"])
            cmd.extend(["-a", f"scroll_count={self.scroll_count_var.get()}"])
            cmd.extend(["-a", f"max_pages={self.max_pages_var.get()}"])

        # Delays (Always apply, affects first page too)
        cmd.extend(["-a", f"scroll_delay={self.scroll_delay_var.get()}"])
        cmd.extend(["-a", f"page_delay={self.page_delay_var.get()}"])
        
        # Performance / Limits
        cmd.extend(["-a", f"timeout={int(self.timeout_var.get()) * 1000}"]) # Scrapy/Playwright expects ms usually, but let's check spider. Spider expects ms. Input is s.
        cmd.extend(["-a", f"wait_state={self.wait_state.get()}"])

        if self.pre_scrape_clicks.get():
             cmd.extend(["-a", f"pre_scrape_clicks={self.pre_scrape_clicks.get()}"])
             if self.pre_scrape_all_pages.get():
                 cmd.extend(["-a", "pre_scrape_all_pages=true"])

        settings = [
            f'DOWNLOAD_DELAY={self.download_delay_var.get()}',
            'LOG_LEVEL=INFO'
        ]
        
        if self.randomize_delays.get(): settings.append('RANDOMIZE_DOWNLOAD_DELAY=True')
        if self.auto_throttle.get(): settings.append('AUTOTHROTTLE_ENABLED=True')
            
        for s in settings: cmd.extend(['-s', s])

        env = os.environ.copy()
        env['SCRAPER_HEADLESS'] = 'False' if self.visible_browser.get() else 'True'
        # Fix encoding for international characters/emoji on Windows
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        threading.Thread(target=self._run_process, args=(cmd, env)).start()

    def _run_process(self, cmd, env):
        try:
            if sys.platform == 'win32':
                creationflags = subprocess.CREATE_NO_WINDOW
            else:
                creationflags = 0
                
            print(f"DEBUG COMMAND: {' '.join(cmd)}") # <--- DEBUG PRINT
            self.scraping_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, env=env, encoding='utf-8', errors='replace',
                creationflags=creationflags
            )
            
            for line in iter(self.scraping_process.stdout.readline, ''):
                self.log_message(line.strip(), self._categorize_line(line))
                
            rc = self.scraping_process.wait()
            self.root.after(0, lambda: self.scraping_complete(rc))
            
        except Exception as e:
            self.root.after(0, lambda: self.scraping_failed(str(e)))
            
    def _categorize_line(self, line):
        if 'ERROR' in line or '[X]' in line: return 'error'
        if 'WARNING' in line or '[!]' in line: return 'warning'
        if 'Found' in line or 'Saved' in line: return 'success'
        if 'DEBUG' in line: return None
        return 'info'

    def stop_scraping(self):
        if self.scraping_process:
            self.scraping_process.terminate()
        self.is_scraping = False
        self._set_state(False)
        self.status_lbl.config(text="Stopped", fg=AzureTheme.ERROR)

    def scraping_complete(self, rc):
        self.is_scraping = False
        self._set_state(False)
        self.status_lbl.config(text="Finished", fg=AzureTheme.SUCCESS)
        self.log_message("Process finished.", "success")
        
    def scraping_failed(self, msg):
        self.is_scraping = False
        self._set_state(False)
        self.status_lbl.config(text="Error", fg=AzureTheme.ERROR)
        self.log_message(msg, "error")

    def _set_state(self, is_running):
        state_start = tk.DISABLED if is_running else tk.NORMAL
        state_stop = tk.NORMAL if is_running else tk.DISABLED
        
        if hasattr(self, 'start_btn') and self.start_btn:
            self.start_btn.config(state=state_start)
        if hasattr(self, 'stop_btn') and self.stop_btn:
            self.stop_btn.config(state=state_stop)
        
        # Also update the big buttons in the run tab
        if hasattr(self, 'start_btn_lg') and self.start_btn_lg:
            self.start_btn_lg.config(state=state_start)
        if hasattr(self, 'stop_btn_lg') and self.stop_btn_lg:
            self.stop_btn_lg.config(state=state_stop)
            
        if is_running:
            self.status_lbl.config(text="Running...", fg=AzureTheme.WARNING)

    def on_exit(self):
        if self.is_scraping:
            self.stop_scraping()
        self.save_config()
        self.root.destroy()

    def load_config(self):
        if not os.path.exists(CONFIG_FILE): return
        try:
            with open(CONFIG_FILE, 'r') as f: config = json.load(f)
            # Simplified loading (just map keys)
            mapping = {
                'url': self.url_var, 'container': self.container_var,
                'visible_browser': self.visible_browser, 'show_selectors': self.show_selectors,
                'pre_scrape_clicks': self.pre_scrape_clicks, 'name': self.name_var,
                'first_name': self.first_name_var, 'last_name': self.last_name_var,
                'email': self.email_var, 'position': self.position_var,
                'use_profile': self.use_profile, 'profile_link': self.profile_link_var,
                'profile_email': self.profile_email_var, 'has_pagination': self.has_pagination,
                'pagination_type': self.pagination_type, 'pagination_sel': self.pagination_sel_var,
                'data_attr': self.data_attr_var, 'param_name': self.param_name_var,
                'scroll_count': self.scroll_count_var, 'scroll_delay': self.scroll_delay_var,
                'max_pages': self.max_pages_var, 'page_delay': self.page_delay_var,
                'pre_scrape_all_pages': self.pre_scrape_all_pages,
                'post_pagination_clicks': self.post_pagination_clicks,
                'format': self.format_var, 'download_delay': self.download_delay_var,
                'timeout': self.timeout_var, 'wait_state': self.wait_state,
                'randomize': self.randomize_delays, 'auto_throttle': self.auto_throttle
            }
            for k, v in mapping.items():
                if k in config: v.set(config[k])
        except: pass

    def save_config(self):
        config = {
            'url': self.url_var.get(), 'container': self.container_var.get(),
            'visible_browser': self.visible_browser.get(), 'show_selectors': self.show_selectors.get(),
            'pre_scrape_clicks': self.pre_scrape_clicks.get(), 'name': self.name_var.get(),
            'first_name': self.first_name_var.get(), 'last_name': self.last_name_var.get(),
            'email': self.email_var.get(), 'position': self.position_var.get(),
            'use_profile': self.use_profile.get(), 'profile_link': self.profile_link_var.get(),
            'profile_email': self.profile_email_var.get(), 'has_pagination': self.has_pagination.get(),
            'pagination_type': self.pagination_type.get(), 'pagination_sel': self.pagination_sel_var.get(),
            'data_attr': self.data_attr_var.get(), 'param_name': self.param_name_var.get(),
            'scroll_count': self.scroll_count_var.get(), 'scroll_delay': self.scroll_delay_var.get(),
            'max_pages': self.max_pages_var.get(), 'page_delay': self.page_delay_var.get(),
            'pre_scrape_all_pages': self.pre_scrape_all_pages.get(),
            'post_pagination_clicks': self.post_pagination_clicks.get(),
            'format': self.format_var.get(), 'download_delay': self.download_delay_var.get(),
            'timeout': self.timeout_var.get(), 'wait_state': self.wait_state.get(),
            'randomize': self.randomize_delays.get(), 'auto_throttle': self.auto_throttle.get()
        }
        try:
            with open(CONFIG_FILE, 'w') as f: json.dump(config, f, indent=4)
        except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = VisualScraperApp(root)
    root.mainloop()
