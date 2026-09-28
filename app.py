import os
import sys 
import shutil
import sqlite3
import hashlib
import hmac
import time
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Enable High-DPI awareness on Windows for razor-sharp typography and icons
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# ==============================================================================
# CONFIGURATION & LOCAL STORAGE PATHS
# ==============================================================================
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "documentapp.db")
DOCS_DIR = os.path.join(BASE_DIR, "documents")

# Ensure the documents directory exists immediately
os.makedirs(DOCS_DIR, exist_ok=True)

# ==============================================================================
# DESIGN SYSTEM & COLOR PALETTE
# ==============================================================================
BG_MAIN = "#F4F7FB"
BG_CARD = "#FFFFFF"

COLOR_PRIMARY = "#2563EB"
COLOR_PRIMARY_HOVER = "#1D4ED8"
COLOR_PRIMARY_ACTIVE = "#1E40AF"

COLOR_TEXT_DARK = "#0F172A"
COLOR_TEXT_SECONDARY = "#64748B"
COLOR_TEXT_MUTED = "#94A3B8"

COLOR_BORDER = "#E2E8F0"
COLOR_BORDER_FOCUS = "#2563EB"

COLOR_SUCCESS = "#16A34A"
COLOR_SUCCESS_BG = "#DCFCE7"
COLOR_SUCCESS_BORDER = "#BBF7D0"
COLOR_SUCCESS_TEXT = "#15803D"

COLOR_DANGER = "#DC2626"
COLOR_DANGER_HOVER = "#B91C1C"
COLOR_DANGER_ACTIVE = "#991B1B"
COLOR_DANGER_BG = "#FEE2E2"
COLOR_DANGER_BORDER = "#FECACA"

COLOR_ROW_ALT = "#F8FAFC"
COLOR_BADGE_BG = "#EFF6FF"
COLOR_BADGE_BORDER = "#DBEAFE"
COLOR_BADGE_TEXT = "#1D4ED8"

FONT_FAMILY = "Segoe UI"


# ==============================================================================
# DATABASE LAYER
# ==============================================================================
def get_db_connection():
    """Returns a SQLite connection configured with Row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initializes the SQLite database tables on first launch:
    1. users: Stores user credentials (name, email, salted & hashed password).
    2. documents: Stores uploaded document metadata linked to user_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Enable foreign keys support
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


# ==============================================================================
# SECURITY & UTILITY FUNCTIONS
# ==============================================================================
def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """
    Securely hashes a password using PBKDF2-HMAC-SHA256 with 100,000 iterations
    and a cryptographically random 16-byte salt.
    Returns: (password_hash_hex, salt_hex)
    """
    if salt is None:
        salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000
    ).hex()
    return pwd_hash, salt


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """
    Validates a password attempt against stored hash using constant-time comparison
    to prevent timing attacks.
    """
    computed_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(computed_hash, expected_hash)


def is_valid_email(email: str) -> bool:
    """Performs a standard regex check for valid email format."""
    email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(email_regex, email.strip()))


def format_file_size(size_bytes: int) -> str:
    """Converts raw byte count into human-readable format (B, KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def sanitize_filename(filename: str) -> str:
    """Removes potentially unsafe path traversal characters from filename."""
    clean_name = os.path.basename(filename)
    return re.sub(r'[\\/*?:"<>|]', "_", clean_name)


def get_file_icon(filename: str) -> str:
    """Returns a visual document type icon based on extension."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".pdf",):
        return "📄"
    elif ext in (".doc", ".docx", ".rtf", ".odt"):
        return "📝"
    elif ext in (".xls", ".xlsx", ".csv", ".tsv"):
        return "📊"
    elif ext in (".ppt", ".pptx", ".key"):
        return "📑"
    elif ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"):
        return "🖼️"
    elif ext in (".zip", ".rar", ".7z", ".tar", ".gz"):
        return "📦"
    elif ext in (".txt", ".md", ".json", ".xml", ".log", ".sql", ".py", ".js", ".html"):
        return "📄"
    elif ext in (".mp3", ".wav", ".ogg", ".flac"):
        return "🎵"
    elif ext in (".mp4", ".mkv", ".avi", ".mov"):
        return "🎬"
    return "📄"


def create_app_icon():
    """Creates a crisp 32x32 document icon for the application window and taskbar."""
    img = tk.PhotoImage(width=32, height=32)
    # Draw blue document page with folded corner
    for y in range(4, 28):
        for x in range(6, 26):
            if x >= 19 and y <= 10 and (x - 19) + (y - 4) >= 7:
                continue  # Corner cutout
            img.put(COLOR_PRIMARY, (x, y))
    # Folded flap
    for y in range(4, 11):
        for x in range(19, 26):
            if (x - 19) + (y - 4) <= 6:
                img.put("#93C5FD", (x, y))
    # Document white content lines
    for lx, ly, lw in [(10, 14, 12), (10, 18, 12), (10, 22, 8)]:
        for dx in range(lw):
            img.put("#FFFFFF", (lx + dx, ly))
            img.put("#FFFFFF", (lx + dx, ly + 1))
    return img


# ==============================================================================
# CUSTOM MODERN UI COMPONENTS
# ==============================================================================
class ModernCard(tk.Frame):
    """
    A polished card container with a crisp 1px border (#E2E8F0)
    and clean white background (#FFFFFF).
    """
    def __init__(self, master, bg=BG_CARD, border_color=COLOR_BORDER, corner_padding=1, inner_padding=24, **kwargs):
        super().__init__(master, bg=border_color, bd=0, highlightthickness=0, **kwargs)
        self.inner = tk.Frame(self, bg=bg, bd=0, highlightthickness=0)
        self.inner.pack(fill=tk.BOTH, expand=True, padx=corner_padding, pady=corner_padding)

        self.content = tk.Frame(self.inner, bg=bg, bd=0, highlightthickness=0)
        if isinstance(inner_padding, (tuple, list)):
            self.content.pack(fill=tk.BOTH, expand=True, padx=inner_padding[0], pady=inner_padding[1])
        else:
            self.content.pack(fill=tk.BOTH, expand=True, padx=inner_padding, pady=inner_padding)


class ModernButton(tk.Button):
    """
    A modern flat button with responsive hover and active states.
    Variants: 'primary', 'secondary', 'danger', 'outline', 'link'
    """
    def __init__(
        self,
        master,
        text="",
        command=None,
        variant="secondary",
        icon=None,
        padx=16,
        pady=7,
        font=None,
        width=None,
        **kwargs
    ):
        display_text = f"{icon}  {text}" if icon else text

        configs = {
            "primary": {
                "bg": COLOR_PRIMARY,
                "fg": "#FFFFFF",
                "hover": COLOR_PRIMARY_HOVER,
                "active": COLOR_PRIMARY_ACTIVE,
                "hover_fg": "#FFFFFF",
                "bd": 0,
                "relief": "flat",
                "font": (FONT_FAMILY, 10, "bold"),
            },
            "secondary": {
                "bg": "#FFFFFF",
                "fg": COLOR_TEXT_DARK,
                "hover": "#F1F5F9",
                "active": "#E2E8F0",
                "hover_fg": COLOR_TEXT_DARK,
                "bd": 1,
                "relief": "solid",
                "font": (FONT_FAMILY, 9, "bold"),
            },
            "danger": {
                "bg": COLOR_DANGER,
                "fg": "#FFFFFF",
                "hover": COLOR_DANGER_HOVER,
                "active": COLOR_DANGER_ACTIVE,
                "hover_fg": "#FFFFFF",
                "bd": 0,
                "relief": "flat",
                "font": (FONT_FAMILY, 9, "bold"),
            },
            "outline": {
                "bg": "#FFFFFF",
                "fg": COLOR_TEXT_SECONDARY,
                "hover": "#F8FAFC",
                "active": "#F1F5F9",
                "hover_fg": COLOR_TEXT_DARK,
                "bd": 1,
                "relief": "solid",
                "font": (FONT_FAMILY, 9),
            },
            "link": {
                "bg": "#FFFFFF",
                "fg": COLOR_PRIMARY,
                "hover": "#FFFFFF",
                "active": "#FFFFFF",
                "hover_fg": COLOR_PRIMARY_HOVER,
                "bd": 0,
                "relief": "flat",
                "font": (FONT_FAMILY, 9, "bold"),
            },
        }

        cfg = configs.get(variant, configs["secondary"])
        self.variant = variant
        self.normal_bg = cfg["bg"]
        self.hover_bg = cfg["hover"]
        self.active_bg = cfg["active"]
        self.normal_fg = cfg["fg"]
        self.hover_fg = cfg.get("hover_fg", cfg["fg"])
        btn_font = font or cfg["font"]

        btn_kwargs = {}
        if width is not None:
            btn_kwargs["width"] = width

        super().__init__(
            master,
            text=display_text,
            command=command,
            bg=self.normal_bg,
            fg=self.normal_fg,
            activebackground=self.active_bg,
            activeforeground=self.hover_fg,
            font=btn_font,
            relief=cfg["relief"],
            bd=cfg["bd"],
            highlightthickness=0,
            cursor="hand2",
            padx=padx,
            pady=pady,
            **btn_kwargs,
            **kwargs
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        self.configure(bg=self.hover_bg, fg=self.hover_fg)

    def _on_leave(self, event):
        self.configure(bg=self.normal_bg, fg=self.normal_fg)


class ModernEntry(tk.Frame):
    """
    A modern input field container:
    - 1px border that highlights in primary blue (#2563EB) upon focus
    - Optional leading icon (✉, 🔒, 👤, 🔍)
    - Optional show/hide password toggle (👁)
    """
    def __init__(
        self,
        master,
        show=None,
        is_password=False,
        icon=None,
        font=(FONT_FAMILY, 10),
        width=None,
        **kwargs
    ):
        super().__init__(master, bg=COLOR_BORDER, bd=0, highlightthickness=0)
        self.is_password = is_password
        self.show_char = show or ("•" if is_password else "")
        self.is_masked = bool(is_password)

        self.inner = tk.Frame(self, bg="#FFFFFF", bd=0, highlightthickness=0)
        self.inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Leading Icon
        if icon:
            self.icon_lbl = tk.Label(
                self.inner,
                text=icon,
                font=(FONT_FAMILY, 10),
                bg="#FFFFFF",
                fg=COLOR_TEXT_MUTED
            )
            self.icon_lbl.pack(side=tk.LEFT, padx=(10, 4), pady=7)

        entry_kwargs = {}
        if width is not None:
            entry_kwargs["width"] = width

        self.entry = tk.Entry(
            self.inner,
            relief="flat",
            bd=0,
            bg="#FFFFFF",
            fg=COLOR_TEXT_DARK,
            font=font,
            insertbackground=COLOR_PRIMARY,
            show=self.show_char if self.is_masked else "",
            highlightthickness=0,
            **entry_kwargs,
            **kwargs
        )
        pad_left = 6 if not icon else 0
        self.entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(pad_left, 8), pady=8)

        # Password visibility toggle
        if is_password:
            self.toggle_btn = tk.Label(
                self.inner,
                text="👁",
                font=(FONT_FAMILY, 10),
                bg="#FFFFFF",
                fg=COLOR_TEXT_MUTED,
                cursor="hand2"
            )
            self.toggle_btn.pack(side=tk.RIGHT, padx=(0, 10), pady=7)
            self.toggle_btn.bind("<Button-1>", self._toggle_show)

        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)

    def _toggle_show(self, event):
        self.is_masked = not self.is_masked
        self.entry.configure(show=self.show_char if self.is_masked else "")
        self.toggle_btn.configure(fg=COLOR_PRIMARY if not self.is_masked else COLOR_TEXT_MUTED)

    def _on_focus_in(self, event):
        self.configure(bg=COLOR_BORDER_FOCUS)

    def _on_focus_out(self, event):
        self.configure(bg=COLOR_BORDER)

    def get(self):
        return self.entry.get()

    def set_text(self, text):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, text)

    def delete(self, *args):
        return self.entry.delete(*args)

    def insert(self, *args):
        return self.entry.insert(*args)

    def focus(self):
        return self.entry.focus()

    def bind(self, sequence, func, add=None):
        return self.entry.bind(sequence, func, add)


def ask_confirm_modern(parent, title, heading, detail, confirm_text="Confirm", is_danger=False):
    """
    Renders an elegant modal confirmation dialog with Keyboard navigation:
    - Escape closes/cancels
    - Enter confirms
    """
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.configure(bg="#FFFFFF")
    dialog.transient(parent)
    dialog.resizable(False, False)

    result = {"confirmed": False}

    # Center dialog on top of the parent window
    parent.update_idletasks()
    dialog_w, dialog_h = 440, 210
    parent_x = parent.winfo_x()
    parent_y = parent.winfo_y()
    parent_w = parent.winfo_width()
    parent_h = parent.winfo_height()

    pos_x = max(0, parent_x + (parent_w - dialog_w) // 2)
    pos_y = max(0, parent_y + (parent_h - dialog_h) // 2)
    dialog.geometry(f"{dialog_w}x{dialog_h}+{pos_x}+{pos_y}")

    def on_confirm(event=None):
        result["confirmed"] = True
        dialog.destroy()

    def on_cancel(event=None):
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", on_cancel)
    dialog.bind("<Escape>", on_cancel)
    dialog.bind("<Return>", on_confirm)

    pad = tk.Frame(dialog, bg="#FFFFFF", padx=24, pady=22)
    pad.pack(fill=tk.BOTH, expand=True)

    header_frame = tk.Frame(pad, bg="#FFFFFF")
    header_frame.pack(fill=tk.X, pady=(0, 8))

    icon_char = "🗑️" if is_danger else "ℹ️"
    icon_bg = COLOR_DANGER_BG if is_danger else COLOR_BADGE_BG
    icon_fg = COLOR_DANGER if is_danger else COLOR_PRIMARY

    icon_box = tk.Label(
        header_frame,
        text=icon_char,
        font=(FONT_FAMILY, 14),
        bg=icon_bg,
        fg=icon_fg,
        width=3,
        height=1
    )
    icon_box.pack(side=tk.LEFT, padx=(0, 10))

    title_lbl = tk.Label(
        header_frame,
        text=heading,
        font=(FONT_FAMILY, 12, "bold"),
        bg="#FFFFFF",
        fg=COLOR_TEXT_DARK
    )
    title_lbl.pack(side=tk.LEFT, anchor="w")

    body_lbl = tk.Label(
        pad,
        text=detail,
        font=(FONT_FAMILY, 9),
        bg="#FFFFFF",
        fg=COLOR_TEXT_SECONDARY,
        justify=tk.LEFT,
        wraplength=380
    )
    body_lbl.pack(fill=tk.X, pady=(0, 20))

    btn_row = tk.Frame(pad, bg="#FFFFFF")
    btn_row.pack(fill=tk.X, side=tk.BOTTOM)

    cancel_btn = ModernButton(
        btn_row,
        text="Cancel",
        command=on_cancel,
        variant="secondary",
        padx=14,
        pady=6
    )
    cancel_btn.pack(side=tk.RIGHT, padx=(8, 0))

    confirm_btn = ModernButton(
        btn_row,
        text=confirm_text,
        command=on_confirm,
        variant="danger" if is_danger else "primary",
        padx=16,
        pady=6
    )
    confirm_btn.pack(side=tk.RIGHT)

    confirm_btn.focus_set()
    dialog.grab_set()
    parent.wait_window(dialog)
    return result["confirmed"]


# ==============================================================================
# MAIN APPLICATION GUI CLASS
# ==============================================================================
class DocumentApp(tk.Tk):
    """
    DocumentApp Main Application:
    Coordinates switching between Authentication View (Login/Register)
    and User Dashboard View (Document listing, uploading, downloading, deletion).
    """

    def __init__(self):
        super().__init__()
        self.title("DocumentApp - Secure Document Management")
        self.geometry("1020x680")
        self.minsize(860, 560)
        self.configure(bg=BG_MAIN)

        # Center the main window on screen
        self.center_window(1020, 680)

        # Set taskbar and window icon
        try:
            self.app_icon = create_app_icon()
            self.iconphoto(True, self.app_icon)
        except Exception:
            pass

        # Session state: stores dict of logged-in user: {"id": int, "name": str, "email": str}
        self.current_user = None

        # Main dynamic container frame
        self.container = tk.Frame(self, bg=BG_MAIN)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.setup_styles()
        self.show_login_view()

    def center_window(self, width: int, height: int):
        """Centers the window on the active monitor."""
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = max(0, (screen_w - width) // 2)
        pos_y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    def setup_styles(self):
        """Applies clean, modern ttk styles for Treeview and scrollbars."""
        self.style = ttk.Style(self)

        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")

        # Treeview styling
        self.style.configure(
            "Custom.Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground=COLOR_TEXT_DARK,
            font=(FONT_FAMILY, 10),
            rowheight=38,
            borderwidth=0,
            relief="flat"
        )
        self.style.configure(
            "Custom.Treeview.Heading",
            background="#F8FAFC",
            foreground="#475569",
            font=(FONT_FAMILY, 9, "bold"),
            relief="flat",
            padding=(10, 8),
            borderwidth=1,
            bordercolor=COLOR_BORDER
        )
        self.style.map(
            "Custom.Treeview.Heading",
            background=[("active", "#F1F5F9")],
            foreground=[("active", COLOR_TEXT_DARK)]
        )
        self.style.map(
            "Custom.Treeview",
            background=[("selected", COLOR_PRIMARY)],
            foreground=[("selected", "#FFFFFF")]
        )

        # Custom Scrollbar styling
        self.style.configure(
            "Custom.Vertical.TScrollbar",
            gripcount=0,
            background="#CBD5E1",
            troughcolor="#F8FAFC",
            bordercolor="#F8FAFC",
            arrowcolor="#64748B",
            relief="flat"
        )
        self.style.map(
            "Custom.Vertical.TScrollbar",
            background=[("active", "#94A3B8")]
        )

    def clear_container(self):
        """Removes all widgets from the main container before switching views."""
        for widget in self.container.winfo_children():
            widget.destroy()

    # --------------------------------------------------------------------------
    # VIEW: AUTHENTICATION (LOGIN & REGISTRATION)
    # --------------------------------------------------------------------------
    def show_auth_view(self, default_tab=0):
        """Backward compatibility wrapper for authentication views."""
        if default_tab == 1:
            self.show_register_view()
        else:
            self.show_login_view()

    def show_login_view(self, prefill_email="", alert_msg=None, is_success=False):
        """Renders the centered, modern Login card."""
        self.clear_container()

        # Use pack for the outer wrapper (consistent with dashboard)
        center_wrapper = tk.Frame(self.container, bg=BG_MAIN)
        center_wrapper.pack(expand=True, fill=tk.BOTH)

        # Use place for pixel-perfect centering of the card
        inner = tk.Frame(center_wrapper, bg=BG_MAIN)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        # Modern White Login Card
        card = ModernCard(inner, bg=BG_CARD, inner_padding=(36, 32))
        card.pack()

        # Top Header & Brand
        header_frame = tk.Frame(card.content, bg=BG_CARD)
        header_frame.pack(fill=tk.X, pady=(0, 20))

        icon_badge = tk.Label(
            header_frame,
            text="📄",
            font=(FONT_FAMILY, 24),
            bg=COLOR_BADGE_BG,
            fg=COLOR_PRIMARY,
            width=3,
            height=1
        )
        icon_badge.pack(pady=(0, 10))

        title_lbl = tk.Label(
            header_frame,
            text="DocumentApp",
            font=(FONT_FAMILY, 20, "bold"),
            bg=BG_CARD,
            fg=COLOR_TEXT_DARK
        )
        title_lbl.pack(pady=(0, 4))

        subtitle_lbl = tk.Label(
            header_frame,
            text="Secure Document Management",
            font=(FONT_FAMILY, 10),
            bg=BG_CARD,
            fg=COLOR_TEXT_SECONDARY
        )
        subtitle_lbl.pack()

        # Inline Alert Message (Error or Success)
        self.login_alert_frame = tk.Frame(card.content, bg=BG_CARD)
        self.login_alert_frame.pack(fill=tk.X, pady=(0, 14))

        self.login_alert_lbl = tk.Label(
            self.login_alert_frame,
            text="",
            font=(FONT_FAMILY, 9),
            wraplength=340,
            justify=tk.LEFT
        )

        def display_alert(msg, success=False):
            if not msg:
                self.login_alert_lbl.pack_forget()
                return
            bg_c = COLOR_SUCCESS_BG if success else COLOR_DANGER_BG
            fg_c = COLOR_SUCCESS_TEXT if success else COLOR_DANGER
            border_c = COLOR_SUCCESS_BORDER if success else COLOR_DANGER_BORDER
            icon = "✓ " if success else "⚠️ "

            self.login_alert_frame.configure(bg=border_c, padx=1, pady=1)
            self.login_alert_lbl.configure(
                text=f"{icon}{msg}",
                bg=bg_c,
                fg=fg_c,
                padx=10,
                pady=6
            )
            self.login_alert_lbl.pack(fill=tk.X)

        if alert_msg:
            display_alert(alert_msg, is_success)

        # Form: Email Address
        tk.Label(
            card.content,
            text="Email Address",
            font=(FONT_FAMILY, 9, "bold"),
            bg=BG_CARD,
            fg=COLOR_TEXT_DARK
        ).pack(anchor="w", pady=(0, 4))

        login_email = ModernEntry(card.content, icon="✉")
        login_email.pack(fill=tk.X, pady=(0, 14))
        if prefill_email:
            login_email.set_text(prefill_email)

        # Form: Password
        tk.Label(
            card.content,
            text="Password",
            font=(FONT_FAMILY, 9, "bold"),
            bg=BG_CARD,
            fg=COLOR_TEXT_DARK
        ).pack(anchor="w", pady=(0, 4))

        login_pwd = ModernEntry(card.content, is_password=True, show="•", icon="🔒")
        login_pwd.pack(fill=tk.X, pady=(0, 20))

        # Login Action Handler
        def handle_login(event=None):
            email = login_email.get().strip().lower()
            password = login_pwd.get()

            if not email or not password:
                display_alert("Please enter both your email address and password.")
                return

            if not is_valid_email(email):
                display_alert("Please enter a valid email address.")
                return

            # Query database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, email, password_hash, salt FROM users WHERE email = ?",
                (email,)
            )
            user = cursor.fetchone()
            conn.close()

            if user and verify_password(password, user["salt"], user["password_hash"]):
                self.current_user = {
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"]
                }
                self.show_dashboard_view()
            else:
                display_alert("Incorrect email or password. Please try again.")

        # Bindings
        login_email.bind("<Return>", lambda e: login_pwd.focus())
        login_pwd.bind("<Return>", handle_login)

        # Large Blue "Log In" button
        login_btn = ModernButton(
            card.content,
            text="Log In",
            command=handle_login,
            variant="primary",
            font=(FONT_FAMILY, 10, "bold"),
            pady=9
        )
        login_btn.pack(fill=tk.X, pady=(0, 12))

        # Secondary "Create an Account" action
        switch_frame = tk.Frame(card.content, bg=BG_CARD)
        switch_frame.pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            switch_frame,
            text="Don't have an account?",
            font=(FONT_FAMILY, 9),
            bg=BG_CARD,
            fg=COLOR_TEXT_SECONDARY
        ).pack(side=tk.LEFT)

        reg_link = ModernButton(
            switch_frame,
            text="Create an Account",
            command=self.show_register_view,
            variant="link",
            padx=4,
            pady=0
        )
        reg_link.pack(side=tk.LEFT)

        # Bottom Privacy & Security note
        bottom_badge = tk.Frame(card.content, bg=BG_CARD)
        bottom_badge.pack(fill=tk.X)

        tk.Label(
            bottom_badge,
            text="🔒 Your documents are private and protected.",
            font=(FONT_FAMILY, 8),
            bg=BG_CARD,
            fg=COLOR_TEXT_MUTED
        ).pack(anchor="center")

        # Focus initial field
        if prefill_email:
            login_pwd.focus()
        else:
            login_email.focus()

    def show_register_view(self):
        """Renders the centered, modern Registration card."""
        self.clear_container()

        # Use pack for the outer wrapper (consistent)
        center_wrapper = tk.Frame(self.container, bg=BG_MAIN)
        center_wrapper.pack(expand=True, fill=tk.BOTH)

        # Use place for pixel-perfect centering of the card
        inner = tk.Frame(center_wrapper, bg=BG_MAIN)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        # Modern White Register Card
        card = ModernCard(inner, bg=BG_CARD, inner_padding=(36, 28))
        card.pack()

        # Top Header & Brand
        header_frame = tk.Frame(card.content, bg=BG_CARD)
        header_frame.pack(fill=tk.X, pady=(0, 16))

        icon_badge = tk.Label(
            header_frame,
            text="📄",
            font=(FONT_FAMILY, 24),
            bg=COLOR_BADGE_BG,
            fg=COLOR_PRIMARY,
            width=3,
            height=1
        )
        icon_badge.pack(pady=(0, 8))

        title_lbl = tk.Label(
            header_frame,
            text="Create your account",
            font=(FONT_FAMILY, 18, "bold"),
            bg=BG_CARD,
            fg=COLOR_TEXT_DARK
        )
        title_lbl.pack(pady=(0, 4))

        subtitle_lbl = tk.Label(
            header_frame,
            text="Secure personal document storage & management",
            font=(FONT_FAMILY, 9),
            bg=BG_CARD,
            fg=COLOR_TEXT_SECONDARY
        )
        subtitle_lbl.pack()

        # Inline Alert Message for Validation
        self.reg_alert_frame = tk.Frame(card.content, bg=BG_CARD)
        self.reg_alert_frame.pack(fill=tk.X, pady=(0, 10))

        self.reg_alert_lbl = tk.Label(
            self.reg_alert_frame,
            text="",
            font=(FONT_FAMILY, 9),
            wraplength=340,
            justify=tk.LEFT
        )

        def display_alert(msg):
            if not msg:
                self.reg_alert_lbl.pack_forget()
                return
            self.reg_alert_frame.configure(bg=COLOR_DANGER_BORDER, padx=1, pady=1)
            self.reg_alert_lbl.configure(
                text=f"⚠️ {msg}",
                bg=COLOR_DANGER_BG,
                fg=COLOR_DANGER,
                padx=10,
                pady=6
            )
            self.reg_alert_lbl.pack(fill=tk.X)

        # Fields: Full Name
        tk.Label(
            card.content,
            text="Full Name",
            font=(FONT_FAMILY, 9, "bold"),
            bg=BG_CARD,
            fg=COLOR_TEXT_DARK
        ).pack(anchor="w", pady=(0, 3))

        reg_name = ModernEntry(card.content, icon="👤")
        reg_name.pack(fill=tk.X, pady=(0, 10))

        # Fields: Email Address
        tk.Label(
            card.content,
            text="Email Address",
            font=(FONT_FAMILY, 9, "bold"),
            bg=BG_CARD,
            fg=COLOR_TEXT_DARK
        ).pack(anchor="w", pady=(0, 3))

        reg_email = ModernEntry(card.content, icon="✉")
        reg_email.pack(fill=tk.X, pady=(0, 10))

        # Fields: Password
        tk.Label(
            card.content,
            text="Password (min 6 characters)",
            font=(FONT_FAMILY, 9, "bold"),
            bg=BG_CARD,
            fg=COLOR_TEXT_DARK
        ).pack(anchor="w", pady=(0, 3))

        reg_pwd = ModernEntry(card.content, is_password=True, show="•", icon="🔒")
        reg_pwd.pack(fill=tk.X, pady=(0, 10))

        # Fields: Confirm Password
        tk.Label(
            card.content,
            text="Confirm Password",
            font=(FONT_FAMILY, 9, "bold"),
            bg=BG_CARD,
            fg=COLOR_TEXT_DARK
        ).pack(anchor="w", pady=(0, 3))

        reg_confirm = ModernEntry(card.content, is_password=True, show="•", icon="🔒")
        reg_confirm.pack(fill=tk.X, pady=(0, 16))

        # Register Action Handler
        def handle_register(event=None):
            name = reg_name.get().strip()
            email = reg_email.get().strip().lower()
            password = reg_pwd.get()
            confirm = reg_confirm.get()

            # Validation
            if not name or not email or not password or not confirm:
                display_alert("Please fill in all registration fields.")
                return

            if len(name) < 2:
                display_alert("Please enter a valid full name (at least 2 characters).")
                return

            if not is_valid_email(email):
                display_alert("Please enter a valid email address (e.g. user@example.com).")
                return

            if len(password) < 6:
                display_alert("Password must be at least 6 characters long.")
                return

            if password != confirm:
                display_alert("Passwords do not match. Please verify and try again.")
                return

            # Hash password securely
            pwd_hash, salt = hash_password(password)

            # Insert into database
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (name, email, password_hash, salt) VALUES (?, ?, ?, ?)",
                    (name, email, pwd_hash, salt)
                )
                conn.commit()
                conn.close()

                # Redirect to login with success alert
                self.show_login_view(
                    prefill_email=email,
                    alert_msg="Account created successfully! Please enter your password to log in.",
                    is_success=True
                )

            except sqlite3.IntegrityError:
                display_alert("An account with this email address already exists.")

        # Bindings
        reg_name.bind("<Return>", lambda e: reg_email.focus())
        reg_email.bind("<Return>", lambda e: reg_pwd.focus())
        reg_pwd.bind("<Return>", lambda e: reg_confirm.focus())
        reg_confirm.bind("<Return>", handle_register)

        # Large Blue "Create Account" button
        reg_btn = ModernButton(
            card.content,
            text="Create Account",
            command=handle_register,
            variant="primary",
            font=(FONT_FAMILY, 10, "bold"),
            pady=9
        )
        reg_btn.pack(fill=tk.X, pady=(0, 12))

        # Secondary "Already have an account? Log in" action
        switch_frame = tk.Frame(card.content, bg=BG_CARD)
        switch_frame.pack(fill=tk.X)

        tk.Label(
            switch_frame,
            text="Already have an account?",
            font=(FONT_FAMILY, 9),
            bg=BG_CARD,
            fg=COLOR_TEXT_SECONDARY
        ).pack(side=tk.LEFT)

        log_link = ModernButton(
            switch_frame,
            text="Log in",
            command=self.show_login_view,
            variant="link",
            padx=4,
            pady=0
        )
        log_link.pack(side=tk.LEFT)

        reg_name.focus()

    # --------------------------------------------------------------------------
    # VIEW: DASHBOARD
    # --------------------------------------------------------------------------
    def show_dashboard_view(self):
        """Renders the redesigned, modern DocumentApp dashboard."""
        self.clear_container()

        # ======================================================================
        # 1. TOP HEADER BAR
        # ======================================================================
        header_outer = tk.Frame(self.container, bg=COLOR_BORDER, bd=0, highlightthickness=0)
        header_outer.pack(fill=tk.X)

        header = tk.Frame(header_outer, bg="#FFFFFF", padx=28, pady=12)
        header.pack(fill=tk.X, pady=(0, 1))

        # Left Header: Brand & App Title
        brand_frame = tk.Frame(header, bg="#FFFFFF")
        brand_frame.pack(side=tk.LEFT)

        brand_badge = tk.Label(
            brand_frame,
            text="📄",
            font=(FONT_FAMILY, 16),
            bg=COLOR_BADGE_BG,
            fg=COLOR_PRIMARY,
            width=2,
            height=1
        )
        brand_badge.pack(side=tk.LEFT, padx=(0, 10))

        brand_text_frame = tk.Frame(brand_frame, bg="#FFFFFF")
        brand_text_frame.pack(side=tk.LEFT)

        tk.Label(
            brand_text_frame,
            text="DocumentApp",
            font=(FONT_FAMILY, 13, "bold"),
            bg="#FFFFFF",
            fg=COLOR_TEXT_DARK
        ).pack(anchor="w")

        tk.Label(
            brand_text_frame,
            text="Secure Document Management",
            font=(FONT_FAMILY, 8),
            bg="#FFFFFF",
            fg=COLOR_TEXT_SECONDARY
        ).pack(anchor="w")

        # Right Header: User Details & Logout Button
        user_header_frame = tk.Frame(header, bg="#FFFFFF")
        user_header_frame.pack(side=tk.RIGHT)

        # User Avatar Circle (Initial)
        initial = (self.current_user["name"][:1] if self.current_user["name"] else "U").upper()
        avatar = tk.Label(
            user_header_frame,
            text=initial,
            font=(FONT_FAMILY, 10, "bold"),
            bg=COLOR_BADGE_BG,
            fg=COLOR_PRIMARY,
            width=3,
            height=1
        )
        avatar.pack(side=tk.LEFT, padx=(0, 8))

        # User Name and Email
        uinfo_frame = tk.Frame(user_header_frame, bg="#FFFFFF")
        uinfo_frame.pack(side=tk.LEFT, padx=(0, 16))

        tk.Label(
            uinfo_frame,
            text=self.current_user["name"],
            font=(FONT_FAMILY, 9, "bold"),
            bg="#FFFFFF",
            fg=COLOR_TEXT_DARK
        ).pack(anchor="w")

        tk.Label(
            uinfo_frame,
            text=self.current_user["email"],
            font=(FONT_FAMILY, 8),
            bg="#FFFFFF",
            fg=COLOR_TEXT_SECONDARY
        ).pack(anchor="w")

        logout_btn = ModernButton(
            user_header_frame,
            text="Log Out",
            command=self.handle_logout,
            variant="outline",
            icon="🚪",
            padx=12,
            pady=5
        )
        logout_btn.pack(side=tk.LEFT)

        # ======================================================================
        # 2. MAIN DASHBOARD CONTENT AREA
        # ======================================================================
        content_frame = tk.Frame(self.container, bg=BG_MAIN, padx=28, pady=16)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Welcome Section
        welcome_frame = tk.Frame(content_frame, bg=BG_MAIN)
        welcome_frame.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            welcome_frame,
            text=f"Welcome back, {self.current_user['name']} 👋",
            font=(FONT_FAMILY, 16, "bold"),
            bg=BG_MAIN,
            fg=COLOR_TEXT_DARK
        ).pack(anchor="w", pady=(0, 2))

        tk.Label(
            welcome_frame,
            text="Manage and securely access your personal documents.",
            font=(FONT_FAMILY, 9),
            bg=BG_MAIN,
            fg=COLOR_TEXT_SECONDARY
        ).pack(anchor="w")

        # Action Area & Search Toolbar
        toolbar = tk.Frame(content_frame, bg=BG_MAIN)
        toolbar.pack(fill=tk.X, pady=(0, 14))

        # Left: Prominent "+ Upload Document" button
        upload_btn = ModernButton(
            toolbar,
            text="Upload Document",
            command=self.handle_upload,
            variant="primary",
            icon="+",
            font=(FONT_FAMILY, 10, "bold"),
            padx=18,
            pady=8
        )
        upload_btn.pack(side=tk.LEFT)

        # Right: Document Count Badge
        self.stats_badge_outer = tk.Frame(toolbar, bg=COLOR_BADGE_BORDER, bd=0, highlightthickness=0)
        self.stats_badge_outer.pack(side=tk.RIGHT, padx=(10, 0))

        self.stats_label = tk.Label(
            self.stats_badge_outer,
            text="0 Documents",
            font=(FONT_FAMILY, 9, "bold"),
            bg=COLOR_BADGE_BG,
            fg=COLOR_BADGE_TEXT,
            padx=12,
            pady=6
        )
        self.stats_label.pack(fill=tk.BOTH)

        # Right: Modern Search Input with live filtering
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.filter_documents())

        search_box = tk.Frame(toolbar, bg=COLOR_BORDER, bd=0, highlightthickness=0)
        search_box.pack(side=tk.RIGHT)

        search_inner = tk.Frame(search_box, bg="#FFFFFF", padx=8, pady=4)
        search_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        search_icon = tk.Label(
            search_inner,
            text="🔍",
            font=(FONT_FAMILY, 9),
            bg="#FFFFFF",
            fg=COLOR_TEXT_MUTED
        )
        search_icon.pack(side=tk.LEFT, padx=(2, 6))

        self.search_entry = tk.Entry(
            search_inner,
            textvariable=self.search_var,
            font=(FONT_FAMILY, 9),
            relief="flat",
            bd=0,
            bg="#FFFFFF",
            fg=COLOR_TEXT_DARK,
            insertbackground=COLOR_PRIMARY,
            width=28
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=2)

        # Clear search button
        self.clear_search_btn = tk.Label(
            search_inner,
            text="✕",
            font=(FONT_FAMILY, 8, "bold"),
            bg="#FFFFFF",
            fg=COLOR_TEXT_MUTED,
            cursor="hand2"
        )
        self.clear_search_btn.pack(side=tk.RIGHT, padx=(4, 2))
        self.clear_search_btn.bind("<Button-1>", lambda e: self.search_var.set(""))

        # Search box focus borders
        def on_search_focus_in(e):
            search_box.configure(bg=COLOR_BORDER_FOCUS)

        def on_search_focus_out(e):
            search_box.configure(bg=COLOR_BORDER)

        self.search_entry.bind("<FocusIn>", on_search_focus_in)
        self.search_entry.bind("<FocusOut>", on_search_focus_out)
        self.search_entry.bind("<Escape>", lambda e: self.search_var.set(""))

        # ======================================================================
        # 3. DOCUMENT CARD CONTAINER (TABLE & EMPTY STATE)
        # ======================================================================
        doc_card = ModernCard(content_frame, bg=BG_CARD, inner_padding=(20, 16))
        doc_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        # Card Header
        card_header = tk.Frame(doc_card.content, bg=BG_CARD)
        card_header.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            card_header,
            text="📁 My Documents",
            font=(FONT_FAMILY, 12, "bold"),
            bg=BG_CARD,
            fg=COLOR_TEXT_DARK
        ).pack(side=tk.LEFT)

        self.card_tip_lbl = tk.Label(
            card_header,
            text="Double-click any file to open  •  Right-click for options",
            font=(FONT_FAMILY, 8),
            bg=BG_CARD,
            fg=COLOR_TEXT_MUTED
        )
        self.card_tip_lbl.pack(side=tk.RIGHT)

        # Divider line
        card_sep = tk.Frame(doc_card.content, bg="#F1F5F9", height=1)
        card_sep.pack(fill=tk.X, pady=(0, 10))

        # Body container hosting either Table or Empty State
        self.card_body = tk.Frame(doc_card.content, bg=BG_CARD)
        self.card_body.pack(fill=tk.BOTH, expand=True)

        # --- A. Table Frame ---
        self.table_frame = tk.Frame(self.card_body, bg=BG_CARD)

        columns = ("filename", "filesize", "uploaded_at", "actions")
        self.tree = ttk.Treeview(
            self.table_frame,
            style="Custom.Treeview",
            columns=columns,
            show="headings",
            selectmode="browse"
        )

        self.tree.heading("filename", text="Document", anchor="w")
        self.tree.heading("filesize", text="Size", anchor="center")
        self.tree.heading("uploaded_at", text="Uploaded On", anchor="center")
        self.tree.heading("actions", text="Actions", anchor="center")

        self.tree.column("filename", width=420, minwidth=240, anchor="w", stretch=True)
        self.tree.column("filesize", width=120, minwidth=80, anchor="center", stretch=False)
        self.tree.column("uploaded_at", width=170, minwidth=140, anchor="center", stretch=False)
        self.tree.column("actions", width=140, minwidth=110, anchor="center", stretch=False)

        # Alternating row tag colors
        self.tree.tag_configure("evenrow", background="#FFFFFF")
        self.tree.tag_configure("oddrow", background=COLOR_ROW_ALT)

        scrollbar = ttk.Scrollbar(
            self.table_frame,
            orient=tk.VERTICAL,
            command=self.tree.yview,
            style="Custom.Vertical.TScrollbar"
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Double click or Enter to open document
        self.tree.bind("<Double-1>", lambda event: self.handle_open())
        self.tree.bind("<Return>", lambda event: self.handle_open())
        self.tree.bind("<Delete>", lambda event: self.handle_delete())

        # Right-Click Context Menu
        self.context_menu = tk.Menu(self, tearoff=0, font=(FONT_FAMILY, 9))
        self.context_menu.add_command(label="📂  Open / View Document", command=self.handle_open)
        self.context_menu.add_command(label="💾  Download / Save As...", command=self.handle_download)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🗑  Delete Document", command=self.handle_delete)

        def show_context_menu(event):
            row_id = self.tree.identify_row(event.y)
            if row_id:
                self.tree.selection_set(row_id)
                self.context_menu.post(event.x_root, event.y_root)

        self.tree.bind("<Button-3>", show_context_menu)

        # --- B. Empty State Frame (No documents in vault) ---
        self.empty_state_frame = tk.Frame(self.card_body, bg=BG_CARD)

        tk.Label(
            self.empty_state_frame,
            text="📂",
            font=(FONT_FAMILY, 42),
            bg=BG_CARD,
            fg=COLOR_TEXT_MUTED
        ).pack(pady=(45, 10))

        tk.Label(
            self.empty_state_frame,
            text="No documents yet",
            font=(FONT_FAMILY, 15, "bold"),
            bg=BG_CARD,
            fg=COLOR_TEXT_DARK
        ).pack(pady=(0, 4))

        tk.Label(
            self.empty_state_frame,
            text="Upload your first document to get started.",
            font=(FONT_FAMILY, 10),
            bg=BG_CARD,
            fg=COLOR_TEXT_SECONDARY
        ).pack(pady=(0, 18))

        ModernButton(
            self.empty_state_frame,
            text="Upload Document",
            command=self.handle_upload,
            variant="primary",
            icon="+",
            font=(FONT_FAMILY, 10, "bold"),
            padx=20,
            pady=8
        ).pack(pady=(0, 45))

        # --- C. Search Empty Frame (No search results match query) ---
        self.search_empty_frame = tk.Frame(self.card_body, bg=BG_CARD)

        tk.Label(
            self.search_empty_frame,
            text="🔍",
            font=(FONT_FAMILY, 32),
            bg=BG_CARD,
            fg=COLOR_TEXT_MUTED
        ).pack(pady=(35, 8))

        self.search_empty_title = tk.Label(
            self.search_empty_frame,
            text="No documents found",
            font=(FONT_FAMILY, 13, "bold"),
            bg=BG_CARD,
            fg=COLOR_TEXT_DARK
        )
        self.search_empty_title.pack(pady=(0, 4))

        tk.Label(
            self.search_empty_frame,
            text="Check your query or clear the filter to see all files.",
            font=(FONT_FAMILY, 9),
            bg=BG_CARD,
            fg=COLOR_TEXT_SECONDARY
        ).pack(pady=(0, 16))

        ModernButton(
            self.search_empty_frame,
            text="Clear Search",
            command=lambda: self.search_var.set(""),
            variant="secondary",
            font=(FONT_FAMILY, 9, "bold"),
            padx=14,
            pady=6
        ).pack(pady=(0, 35))

        # ======================================================================
        # 4. BOTTOM ACTION BUTTONS
        # ======================================================================
        btn_bar = tk.Frame(content_frame, bg=BG_MAIN)
        btn_bar.pack(fill=tk.X, pady=(0, 10))

        # Left bottom buttons
        self.open_btn = ModernButton(
            btn_bar,
            text="Open",
            command=self.handle_open,
            variant="secondary",
            icon="📂",
            padx=16,
            pady=7
        )
        self.open_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.download_btn = ModernButton(
            btn_bar,
            text="Download",
            command=self.handle_download,
            variant="secondary",
            icon="💾",
            padx=16,
            pady=7
        )
        self.download_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.delete_btn = ModernButton(
            btn_bar,
            text="Delete",
            command=self.handle_delete,
            variant="danger",
            icon="🗑",
            padx=16,
            pady=7
        )
        self.delete_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Right bottom button
        self.refresh_btn = ModernButton(
            btn_bar,
            text="Refresh",
            command=self.load_user_documents,
            variant="secondary",
            icon="🔄",
            padx=16,
            pady=7
        )
        self.refresh_btn.pack(side=tk.RIGHT)

        # ======================================================================
        # 5. SUBTLE BOTTOM STATUS BAR
        # ======================================================================
        status_bar = tk.Frame(self.container, bg="#FFFFFF", padx=28, pady=8)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # 1px Top border on status bar
        status_sep = tk.Frame(self.container, bg=COLOR_BORDER, height=1)
        status_sep.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Label(
            status_bar,
            text="🔒 Your documents are stored securely on this computer.",
            font=(FONT_FAMILY, 8),
            bg="#FFFFFF",
            fg=COLOR_TEXT_SECONDARY
        ).pack(side=tk.LEFT)

        tk.Label(
            status_bar,
            text=f"Logged in as: {self.current_user['email']}",
            font=(FONT_FAMILY, 8),
            bg="#FFFFFF",
            fg=COLOR_TEXT_MUTED
        ).pack(side=tk.RIGHT)

        # In-memory document caches
        self.cached_documents = []
        self.doc_lookup = {}

        # Initial load
        self.load_user_documents()

    # --------------------------------------------------------------------------
    # DOCUMENT ACTIONS & ISOLATION LOGIC
    # --------------------------------------------------------------------------
    def load_user_documents(self):
        """
        Fetches documents belonging EXCLUSIVELY to the current logged-in user
        from SQLite and populates the Treeview table.
        """
        if not self.current_user:
            return

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, filename, file_path, file_size, uploaded_at
            FROM documents
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (self.current_user["id"],)
        )
        self.cached_documents = cursor.fetchall()
        conn.close()

        # Update lookup map
        self.doc_lookup = {str(doc["id"]): doc for doc in self.cached_documents}

        self.filter_documents()

    def filter_documents(self):
        """Filters displayed documents based on search query and manages empty states."""
        search_query = self.search_var.get().strip().lower()

        # Toggle clear search icon visibility
        if hasattr(self, "clear_search_btn"):
            if search_query:
                self.clear_search_btn.configure(fg=COLOR_TEXT_DARK)
            else:
                self.clear_search_btn.configure(fg="#FFFFFF")

        # Clear existing rows
        for row in self.tree.get_children():
            self.tree.delete(row)

        total_docs = len(self.cached_documents)

        # Case 1: Total user documents == 0
        if total_docs == 0:
            self.table_frame.pack_forget()
            self.search_empty_frame.pack_forget()
            self.empty_state_frame.pack(fill=tk.BOTH, expand=True)
            self.stats_label.config(text="0 Documents")
            self._set_action_buttons_state(False)
            return

        # Case 2: User has documents
        self.empty_state_frame.pack_forget()

        matching_count = 0
        for index, doc in enumerate(self.cached_documents):
            if not search_query or search_query in doc["filename"].lower():
                icon = get_file_icon(doc["filename"])
                display_filename = f"  {icon}  {doc['filename']}"
                tag = "evenrow" if matching_count % 2 == 0 else "oddrow"

                self.tree.insert(
                    "",
                    tk.END,
                    iid=str(doc["id"]),
                    values=(
                        display_filename,
                        doc["file_size"],
                        doc["uploaded_at"],
                        "Open • Download"
                    ),
                    tags=(tag,)
                )
                matching_count += 1

        # Case 3: Filter query yielded 0 results
        if matching_count == 0 and search_query:
            self.table_frame.pack_forget()
            self.search_empty_title.config(text=f"No results for \"{search_query}\"")
            self.search_empty_frame.pack(fill=tk.BOTH, expand=True)
            self.stats_label.config(text=f"0 of {total_docs} Documents")
            self._set_action_buttons_state(False)
        else:
            self.search_empty_frame.pack_forget()
            self.table_frame.pack(fill=tk.BOTH, expand=True)
            if search_query:
                self.stats_label.config(text=f"Showing {matching_count} of {total_docs}")
            else:
                doc_text = "1 Document" if total_docs == 1 else f"{total_docs} Documents"
                self.stats_label.config(text=doc_text)
            self._set_action_buttons_state(True)

    def _set_action_buttons_state(self, enabled: bool):
        """Enables or disables row-dependent action buttons."""
        state = tk.NORMAL if enabled else tk.DISABLED
        for btn in (self.open_btn, self.download_btn, self.delete_btn):
            btn.configure(state=state)

    def get_selected_document(self):
        """
        Validates the currently selected row in Treeview and returns
        the corresponding document record for the logged-in user.
        """
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Select Document", "Please select a document from the list first.")
            return None

        doc_id = selected[0]

        # Verify against SQLite for current user to enforce document isolation
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, filename, file_path, file_size, uploaded_at
            FROM documents
            WHERE id = ? AND user_id = ?
            """,
            (doc_id, self.current_user["id"])
        )
        doc = cursor.fetchone()
        conn.close()

        if not doc:
            messagebox.showerror("Error", "The selected document was not found or access is denied.")
            return None

        return doc

    def handle_upload(self):
        """
        Allows the user to select one or more documents, copies them to
        the local 'documents' folder with collision-free filenames,
        and saves their metadata to SQLite under the current user's ID.
        """
        file_paths = filedialog.askopenfilenames(
            title="Select Document(s) to Upload",
            filetypes=[
                ("All Supported Documents", "*.pdf;*.docx;*.doc;*.jpg;*.jpeg;*.png;*.txt;*.xlsx;*.xls;*.pptx;*.csv;*.zip"),
                ("PDF Documents (*.pdf)", "*.pdf"),
                ("Word Documents (*.docx, *.doc)", "*.docx;*.doc"),
                ("Images (*.jpg, *.png)", "*.jpg;*.jpeg;*.png"),
                ("Text & Data (*.txt, *.csv)", "*.txt;*.csv"),
                ("All Files (*.*)", "*.*")
            ]
        )

        if not file_paths:
            return  # User cancelled

        uploaded_count = 0
        last_filename = ""
        timestamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        cursor = conn.cursor()

        for source_path in file_paths:
            try:
                original_name = os.path.basename(source_path)
                safe_name = sanitize_filename(original_name)
                file_size_bytes = os.path.getsize(source_path)
                formatted_size = format_file_size(file_size_bytes)

                # Collision-free isolated storage filename: u{user_id}_{timestamp}_{safe_name}
                unique_prefix = f"u{self.current_user['id']}_{int(time.time() * 1000)}"
                dest_filename = f"{unique_prefix}_{safe_name}"
                destination_path = os.path.join(DOCS_DIR, dest_filename)

                # Copy file to storage
                shutil.copy2(source_path, destination_path)

                # Record in database under current user
                cursor.execute(
                    """
                    INSERT INTO documents (user_id, filename, file_path, file_size, uploaded_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self.current_user["id"],
                        original_name,
                        destination_path,
                        formatted_size,
                        timestamp_now
                    )
                )
                uploaded_count += 1
                last_filename = original_name

            except Exception as e:
                messagebox.showerror("Upload Error", f"Failed to upload '{os.path.basename(source_path)}':\n{e}")

        conn.commit()
        conn.close()

        if uploaded_count > 0:
            if uploaded_count > 1:
                msg = f"Successfully uploaded {uploaded_count} documents to your vault."
            else:
                msg = f"'{last_filename}' was uploaded successfully!"
            messagebox.showinfo("Upload Successful", msg)
            self.load_user_documents()

    def handle_open(self):
        """Opens the selected document with the operating system's default viewer."""
        doc = self.get_selected_document()
        if not doc:
            return

        file_path = doc["file_path"]
        if not os.path.exists(file_path):
            messagebox.showerror(
                "File Missing",
                f"The physical file '{doc['filename']}' could not be found.\n"
                "It may have been moved or removed from storage."
            )
            return

        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", file_path], check=True)
            else:
                import subprocess
                subprocess.run(["xdg-open", file_path], check=True)
        except Exception as e:
            messagebox.showerror("Open Failed", f"Could not launch viewer for document:\n{e}")

    def handle_download(self):
        """Prompts user to select destination and saves a copy of the document."""
        doc = self.get_selected_document()
        if not doc:
            return

        source_path = doc["file_path"]
        if not os.path.exists(source_path):
            messagebox.showerror(
                "File Missing",
                f"The document file '{doc['filename']}' is missing from local storage."
            )
            return

        original_ext = os.path.splitext(doc["filename"])[1]
        save_destination = filedialog.asksaveasfilename(
            title="Download Document",
            initialfile=doc["filename"],
            defaultextension=original_ext,
            filetypes=[("Original File Type", f"*{original_ext}"), ("All Files (*.*)", "*.*")]
        )

        if not save_destination:
            return  # User cancelled

        try:
            shutil.copy2(source_path, save_destination)
            messagebox.showinfo(
                "Download Complete",
                f"'{doc['filename']}' was saved successfully."
            )
        except Exception as e:
            messagebox.showerror("Download Failed", f"Could not save document:\n{e}")

    def handle_delete(self):
        """
        Confirms with the user, then removes the physical file from disk
        and permanently deletes its database record for the current user.
        """
        doc = self.get_selected_document()
        if not doc:
            return

        confirmed = ask_confirm_modern(
            self,
            title="Confirm Deletion",
            heading="Delete this document?",
            detail=f"Are you sure you want to permanently delete '{doc['filename']}'?\n\nThis will remove the file from your computer and database.",
            confirm_text="Delete Document",
            is_danger=True
        )

        if not confirmed:
            return

        # 1. Delete physical file from disk
        if os.path.exists(doc["file_path"]):
            try:
                os.remove(doc["file_path"])
            except Exception as e:
                messagebox.showwarning(
                    "Disk Removal Warning",
                    f"Could not remove physical file from disk:\n{e}\nProceeding with database removal."
                )

        # 2. Delete database entry
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM documents WHERE id = ? AND user_id = ?",
                (doc["id"], self.current_user["id"])
            )
            conn.commit()
            conn.close()

            messagebox.showinfo("Deleted", f"'{doc['filename']}' was successfully deleted.")
            self.load_user_documents()

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to delete document from database:\n{e}")

    def handle_logout(self):
        """Logs out the current user and returns to the login screen."""
        confirmed = ask_confirm_modern(
            self,
            title="Confirm Logout",
            heading="Log out of DocumentApp?",
            detail="You will need to enter your email and password to access your documents again.",
            confirm_text="Log Out",
            is_danger=False
        )
        if confirmed:
            self.current_user = None
            self.show_login_view()


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    # 1. Automatically initialize database & tables on first launch
    init_db()

    # 2. Launch the desktop GUI application
    app = DocumentApp()
    app.mainloop()
