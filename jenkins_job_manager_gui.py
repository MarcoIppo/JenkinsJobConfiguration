#!/usr/bin/env python3
"""
Jenkins Job Configuration Tool — GUI
Tkinter-based Ericsson-themed interface for creating and maintaining Jenkins job
configurations aligned with a local Git repository.
Version: 1.7.1
"""

import os
import sys
import json
import threading
import logging
import traceback
import tkinter as tk
from datetime import datetime, timezone
from tkinter import ttk, filedialog, scrolledtext
from pathlib import Path
from typing import Optional

from jenkins_job_manager import (
    JenkinsClient, ConfigParser, TemplateGenerator,
    RepoWriter, RepoReader, ConfigGenerator,
    load_settings, save_settings, normalize_xml_declaration,
    parse_template_meta, format_meta_tooltip,
    DEFAULT_SETTINGS,
)

# --- Version ---
VERSION = "1.7.1"
CHANGELOG = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Jenkins Job Configuration Tool — Version History
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ver. 01.07.01 — TextParameter Support & ADD Mode for Empty Templates
───────────────────────────────────────────────────────────
  FIX  Added support for TextParameterDefinition (multiline
       text fields): parsing, generation, and repo read/write.
  FIX  Multiline Default Value in parameter headers is now
       correctly captured (previously only the first line was
       read).
  NEW  ADD mode: when the template has no <parameterDefinitions>
       section at all, the generator now creates the full section
       and injects all repo parameters into <properties>, instead
       of silently skipping them.

ver. 01.07.00 — Parameter Reordering, Template Fix & Connectivity Check
───────────────────────────────────────────────────────────
  NEW  Parameters in uploaded XML now follow the numeric
       prefix order from the repo (00, 01, 02...) regardless
       of their original position in the Jenkins template.
  NEW  "🔌 Test" button to verify connectivity and auth
       to the Jenkins FEM before any operation.
  NEW  Connection status indicator (●) next to credentials:
       green = OK, red = failed, gray = not tested.
  NEW  Pre-check before Read Job and Upload — blocks the
       operation with a clear error dialog if Jenkins is
       unreachable (DNS, timeout, auth failure).
  FIX  Template generation no longer misplaces PARAM_FALLBACK
       placeholder when fallback content is whitespace-only.
  NEW  Clear operation delimiters in log output — each major
       operation prints a visible START/COMPLETED/FAILED banner.

ver. 01.06.02 — Fix parameter parsing with hyphens in name
───────────────────────────────────────────────────────────
  FIX  RepoReader now correctly parses parameter filenames
       whose name contains hyphens (e.g. REMOTE_CONFIG_SERVER
       _AND_FILE). The previous regex NN-([^-]+)-suffix stopped
       at the first hyphen, silently dropping any parameter
       whose name included a '-' character.

ver. 01.06.01 — Status Indicators Redesign
───────────────────────────────────────────
  NEW  "📄 Template:" label and status dot now split into separate
       widgets with independent tooltips:
         - Hover on label  → color legend (🟢/🟡/🔴)
         - Hover on dot    → HYDRA:META provenance (job, URL,
                             extraction date, job version)
  NEW  "📋 Config:" label and status dot split the same way:
         - Hover on label  → color legend (🟢/⚫)
         - Hover on dot    → config provenance (from template
                             or merge, with timestamp)
  NEW  Template dot turns 🟡 when template exists but belongs
       to a different job than the one currently selected
  NEW  Template dot updates in real-time while typing in the
       Jenkins Job field
  FIX  Tooltip text refreshes even when the tooltip window is
       already open
  FIX  SSL warnings suppressed in the Read Job background thread
       (urllib3)
  FIX  Full traceback now logged at DEBUG level on Read Job error

ver. 01.05.00 — Template Provenance & Merge Metadata
──────────────────────────────────────────────────────
  NEW  Template file now includes a HYDRA:META comment header
       containing: source Jenkins URL, job name, extraction
       date/time, job version (when available)
  NEW  "📄 Template" dot tooltip displays the full provenance
       information read from the HYDRA:META header
  NEW  On XML generation (Upload / Save Generated), the
       HYDRA:META block is updated with the current merge
       timestamp while preserving the original extraction data
  NEW  HYDRA:META comment is retained in the final file written
       to Jenkins or saved locally

ver. 01.04.01 — Build Step Injection & Safety Guards
─────────────────────────────────────────────────────
  FIX  Upload now injects build steps into empty <builders>
       (template with 0 steps but repo has steps)
  FIX  Read Repo warns when launchers_dir is not found instead
       of silently returning 0 steps
  FIX  RepoReader detects directory name case mismatch at
       startup (e.g. ScriptLauncer vs ScriptLauncher)
  NEW  Upload blocked with confirmation popup if repo has 0
       launchers but Jenkins job currently has >0
  NEW  Read Repo logs exact paths searched (job, params,
       launchers dirs) for easier troubleshooting

ver. 01.04.00 — Read Repo Diagnostics & Config Summary
────────────────────────────────────────────────────────
  NEW  Config Summary printed to log after Read Job and Read
       Repo — lists all items found (params, launchers,
       description, inject, etc.)
  NEW  Read Repo logs exact paths searched at startup
  FIX  Launcher label in log extracted from first non-comment
       line of the shell script
  FIX  Inline script replacement for params without placeholders
       (self-closing <script/> tags)
  FIX  Parameter description and sandbox always updated from
       repo on upload
  FIX  Correct placeholder-to-param mapping (position-aware,
       not order-based)
  FIX  Duplicate header stripping on Save to Repo
  NEW  Separate "Repo Job" field for independent repo directory
       naming
  NEW  Overwrite confirmation when saving to existing repo dir
  NEW  Script approval warning popup after upload
       (sandbox=false detection)
  NEW  All parameter metadata written to description header
       (sandbox, filterable, visible items, choices)
  NEW  ChoiceParameterDefinition support (static choice lists)
  NEW  Type change detection — parameters re-generated when
       repo type differs from template
   UI  Jenkins Job and Repo Job fields side-by-side (50/50)

ver. 01.02.00 — Full Parameter Lifecycle & Descriptions
─────────────────────────────────────────────────────────
  NEW  Add new parameters from repo (XML block auto-generated)
  NEW  Parameter descriptions updated from repo on upload
  NEW  All param metadata in header (sandbox, filterable,
       visible items, default value, choices)
  NEW  XML escape for script content (fixes 500 error on
       HTML-containing scripts)
  NEW  XML validation before upload with debug file on failure
  NEW  Window geometry persistence (main + sub-windows)
  NEW  Reset window sizes button (⊞)
  NEW  Upload Manifest in log (lists all items being uploaded)
  NEW  Operation finished markers (■) in log
  FIX  Parameter type inference from script content
       (HTML → DynamicReferenceParameter)
  FIX  Description fallback replacement when placeholder is
       missing in template
  FIX  Jenkins error response body logged for debugging

ver. 01.01.00 — Smart Upload & Enhanced Logging
─────────────────────────────────────────────────
  NEW  Smart Upload: deleted repo items removed from Jenkins
       job XML automatically
  NEW  Smart Upload: deselected GUI items preserve original
       Jenkins content (no data loss)
  NEW  Name-based parameter matching (replaces fragile
       positional logic)
  NEW  Enhanced logging with DEBUG/INFO/WARN/ERROR levels
  FIX  Non-scripted params no longer consume script
       placeholders

ver. 01.00.00 — Initial Release
─────────────────────────────────
  •   Read job configurations from Jenkins
  •   Save sections to local repository files
  •   Read sections from local repository files
  •   Upload configurations to Jenkins
  •   Template-based config generation
  •   Ericsson-themed dark interface
  •   Settings persistence

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# --- Ericsson-inspired Dark Palette ---
# Based on Ericsson brand guidelines: dark navy base, Ericsson blue accent
C = {
    "base": "#1a1a2e",       # Dark navy (main background)
    "base2": "#222240",      # Slightly lighter for panels
    "surface": "#2d2d4a",    # Input fields, cards
    "surface2": "#3a3a5c",   # Hover, active states
    "border": "#4a4a6a",     # Subtle borders
    "text": "#e8e8f0",       # Primary text
    "dim": "#8888aa",        # Secondary/muted text
    "accent": "#0082f0",     # Ericsson Blue (primary brand)
    "accent_light": "#4da6ff",  # Lighter accent for highlights
    "green": "#4caf50",      # Success
    "red": "#ef5350",        # Error
    "yellow": "#ffc107",     # Warning/version
    "orange": "#f57c00",     # Read Job button
    "purple": "#7c4dff",     # Upload button
    "header_left": "#0082f0",   # Gradient start (Ericsson Blue)
    "header_right": "#1a1a2e",  # Gradient end
}

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
MEDIA_DIR = os.path.join(APP_DIR, "multimedia")
DEFAULT_GEOMETRY = "980x720"


# --- Logging Handler for GUI ---

class TextHandler(logging.Handler):
    def __init__(self, text_widget: tk.Text):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record) + "\n"
        self.text_widget.after(0, self._append, msg)

    def _append(self, msg: str):
        self.text_widget.configure(state="normal")
        self.text_widget.insert(tk.END, msg)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state="disabled")


# --- Tooltip ---

class ToolTip:
    def __init__(self, widget, text: str, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tipwindow = None
        self._id = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)

    def _schedule(self, event=None):
        self._id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self.tipwindow:
            # Update text in already-visible tooltip
            for child in self.tipwindow.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(text=self.text)
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg=C["surface"])
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         bg=C["surface"], fg=C["text"],
                         font=("Helvetica", 9), wraplength=350, padx=8, pady=4)
        label.pack()

    def _hide(self, event=None):
        if self._id:
            self.widget.after_cancel(self._id)
            self._id = None
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


# --- Custom Dialog ---

def _dialog(parent, title, message, msg_color=None, buttons=None):
    """Dark-themed dialog. Returns the value of the clicked button."""
    if msg_color is None:
        msg_color = C["text"]
    if buttons is None:
        buttons = [("OK", C["accent"], True)]

    win = tk.Toplevel(parent)
    win.title(title)
    win.configure(bg=C["base"])
    win.transient(parent)
    win.resizable(False, False)

    result = [None]

    content = tk.Frame(win, bg=C["base"], padx=24, pady=16)
    content.pack(fill=tk.BOTH, expand=True)

    tk.Label(content, text=message, bg=C["base"], fg=msg_color, font=("Helvetica", 9),
             wraplength=450, justify=tk.LEFT).pack(pady=(0, 15))

    btn_frame = tk.Frame(content, bg=C["base"])
    btn_frame.pack(fill=tk.X)

    def close(val):
        result[0] = val
        win.destroy()

    for text, color, value in buttons:
        tk.Button(btn_frame, text=text, width=8, bg=color, fg="white",
                  font=("Helvetica", 9, "bold"), relief=tk.FLAT,
                  activebackground=color, activeforeground="white",
                  command=lambda v=value: close(v)).pack(side=tk.LEFT, padx=4)

    win.geometry(f"+{parent.winfo_rootx() + 100}+{parent.winfo_rooty() + 100}")
    win.update_idletasks()
    win.grab_set()
    parent.wait_window(win)
    return result[0]


def ask_confirm(parent, title, message):
    return _dialog(parent, title, message, msg_color=C["text"],
                   buttons=[("Yes", C["green"], True), ("No", C["red"], False)])


def show_info(parent, title, message):
    _dialog(parent, title, message, msg_color=C["green"],
            buttons=[("OK", C["accent"], True)])


def show_error(parent, title, message):
    _dialog(parent, title, message, msg_color=C["red"],
            buttons=[("OK", C["red"], True)])


def show_warning(parent, title, message):
    _dialog(parent, title, message, msg_color=C["yellow"],
            buttons=[("OK", C["orange"], True)])


# --- Main Application ---

class JenkinsJobManagerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Jenkins Job Configuration Tool")
        self.root.configure(bg=C["base"])
        self.root.minsize(850, 600)

        # State
        self.settings = load_settings(SETTINGS_FILE)

        # Restore window geometry from settings (or use default)
        saved_geometry = self.settings.get("window_geometry", DEFAULT_GEOMETRY)
        self.root.geometry(saved_geometry)
        self.config = None
        self.raw_xml = None
        self._config_source = None  # "job" or "repo"
        self.template_available = False
        self.section_vars = {}
        self._images = []
        self._config_meta = {}    # HYDRA:META dict from last merged/loaded config

        # Logging
        self.logger = logging.getLogger("JenkinsJobManager")
        self.logger.setLevel(logging.DEBUG)

        self._build_ui()
        self._setup_logging()
        self._log_init()
        self._load_settings_to_ui()
        self._update_status_indicators()

        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

    def run(self):
        self.root.mainloop()

    # --- UI ---

    def _build_ui(self):
        self._build_header()
        main = tk.Frame(self.root, bg=C["base"])
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 0))
        self._build_connection_frame(main)
        self._build_job_frame(main)
        self._build_sections_frame(main)
        self._build_log_area(main)
        self._build_bottom_bar()

    def _build_header(self):
        """Gradient header with logos and title."""
        hdr = tk.Canvas(self.root, height=65, highlightthickness=0, bg=C["base"])
        hdr.pack(fill=tk.X)
        hdr_width = 1000

        # Gradient: Ericsson Blue → dark navy
        for x in range(hdr_width):
            ratio = x / hdr_width
            r = int(0 + (26 - 0) * ratio)
            g = int(130 + (26 - 130) * ratio)
            b = int(240 + (46 - 240) * ratio)
            hdr.create_line(x, 0, x, 65, fill=f"#{r:02x}{g:02x}{b:02x}")

        # Hydra logo (left)
        try:
            from PIL import Image, ImageTk
            img = Image.open(os.path.join(MEDIA_DIR, "hydra_d.png")).convert("RGBA").resize((48, 48), Image.LANCZOS)
            self._hydra_logo = ImageTk.PhotoImage(img)
            hdr.create_image(14, 8, anchor="nw", image=self._hydra_logo)
            self._images.append(self._hydra_logo)
        except Exception:
            pass

        # Ericsson logo (right)
        try:
            from PIL import Image, ImageTk
            img_e = Image.open(os.path.join(MEDIA_DIR, "elogo.png")).convert("RGBA").resize((40, 40), Image.LANCZOS)
            self._ericsson_logo = ImageTk.PhotoImage(img_e)
            hdr.create_image(hdr_width - 65, 12, anchor="nw", image=self._ericsson_logo)
            self._images.append(self._ericsson_logo)
        except Exception:
            hdr.create_text(hdr_width - 50, 32, anchor="center", text="Ericsson",
                            font=("Helvetica", 9, "italic"), fill="#ccc")

        # Title (centered)
        cx = hdr_width // 2
        hdr.create_text(cx, 18, anchor="center",
                        text="🔧 Jenkins Job Configuration Tool",
                        font=("Helvetica", 15, "bold"), fill="white")
        hdr.create_text(cx, 38, anchor="center",
                        text="Create & Maintain Jenkins Jobs from Repository",
                        font=("Helvetica", 9), fill="#ddd")
        hdr.create_text(cx, 55, anchor="center",
                        text=f"ver. {VERSION.replace('.', '.')}", 
                        font=("Helvetica", 10, "bold"), fill=C["yellow"])

    def _build_connection_frame(self, parent):
        frame = tk.LabelFrame(parent, text="  🔐 Jenkins Connection  ",
                              bg=C["base2"], fg=C["accent_light"],
                              font=("Helvetica", 9, "bold"), padx=10, pady=6)
        frame.pack(fill=tk.X, pady=(0, 4))

        row0 = tk.Frame(frame, bg=C["base2"])
        row0.pack(fill=tk.X, pady=1)

        self._lbl(row0, "URL:").pack(side=tk.LEFT)
        self.url_entry = self._entry(row0, 35)
        self.url_entry.pack(side=tk.LEFT, padx=(2, 12))
        ToolTip(self.url_entry, "🌐 Jenkins server URL\n(e.g. https://fem1s11-eiffel216.eiffel.gic.ericsson.se:8443/jenkins)")

        self._lbl(row0, "User:").pack(side=tk.LEFT)
        self.user_entry = self._entry(row0, 14)
        self.user_entry.pack(side=tk.LEFT, padx=(2, 12))
        ToolTip(self.user_entry, "👤 Jenkins username (signum)")

        self._lbl(row0, "Token:").pack(side=tk.LEFT)
        self.token_entry = self._entry(row0, 20, show="●")
        self.token_entry.pack(side=tk.LEFT, padx=(2, 4))
        ToolTip(self.token_entry, "🔑 Jenkins API Token\n\n📌 How to generate:\n"
                "1. Log in to Jenkins\n2. Click your name → Configure\n"
                "3. API Token → Add new Token\n4. Name it and click Generate\n"
                "5. Copy (shown only once!)")

        # Connection test button and status indicator
        btn_test = tk.Button(row0, text="🔌 Test", command=self._action_test_connection,
                             bg=C["surface"], fg=C["text"], font=("Segoe UI", 8),
                             relief=tk.FLAT, cursor="hand2", padx=4, pady=0)
        btn_test.pack(side=tk.LEFT, padx=(4, 4))
        ToolTip(btn_test, "🔌 Test connectivity and authentication to Jenkins FEM")

        self._conn_status_label = tk.Label(row0, text="●", font=("Segoe UI", 12),
                                           fg=C["border"], bg=C["base2"])
        self._conn_status_label.pack(side=tk.LEFT, padx=(0, 4))
        ToolTip(self._conn_status_label, "⚫ Connection not tested yet")
        self._conn_ok = None  # None=not tested, True=OK, False=failed

        row1 = tk.Frame(frame, bg=C["base2"])
        row1.pack(fill=tk.X, pady=1)

        self._lbl(row1, "Agent:").pack(side=tk.LEFT)
        self.agent_entry = self._entry(row1, 14)
        self.agent_entry.pack(side=tk.LEFT, padx=(2, 12))
        ToolTip(self.agent_entry, "🖥️ Jenkins agent label (node restriction)")

        self._lbl(row1, "JDK:").pack(side=tk.LEFT)
        self.jdk_entry = self._entry(row1, 14)
        self.jdk_entry.pack(side=tk.LEFT, padx=(2, 0))
        ToolTip(self.jdk_entry, "☕ JDK installation name in Jenkins Global Tool Configuration")

    def _build_job_frame(self, parent):
        frame = tk.LabelFrame(parent, text="  🎯 Target  ",
                              bg=C["base2"], fg=C["accent_light"],
                              font=("Helvetica", 9, "bold"), padx=10, pady=6)
        frame.pack(fill=tk.X, pady=(0, 4))

        # Row 1: Jenkins Job + Repo Job (50/50)
        row1 = tk.Frame(frame, bg=C["base2"])
        row1.pack(fill=tk.X, pady=1)
        left = tk.Frame(row1, bg=C["base2"])
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._lbl(left, "Jenkins Job:").pack(side=tk.LEFT)
        self.job_entry = self._entry(left, 20)
        self.job_entry.pack(side=tk.LEFT, padx=(2, 0), fill=tk.X, expand=True)
        ToolTip(self.job_entry, "📋 Jenkins job name as it appears on the server\n"
                "(e.g. MyProject_Deploy, HYDRA_EnvironmentScript_Check)")
        # Update template indicator whenever the job name changes
        self._job_entry_var = tk.StringVar()
        self.job_entry.config(textvariable=self._job_entry_var)
        self._job_entry_var.trace_add("write", lambda *_: self._update_status_indicators())
        right = tk.Frame(row1, bg=C["base2"])
        right.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._lbl(right, "Repo Job:").pack(side=tk.LEFT, padx=(10, 0))
        self.repo_job_entry = self._entry(right, 20)
        self.repo_job_entry.pack(side=tk.LEFT, padx=(2, 0), fill=tk.X, expand=True)
        ToolTip(self.repo_job_entry,
                "📂 Directory name in the repo for this job's files\n"
                "(defaults to Jenkins Job name if left empty)\n\n"
                "This is the folder under <repo>/JenkinsJobConfiguration/\n"
                "where config files are read from and written to.")

        # Row 2: Local Repo
        row2 = tk.Frame(frame, bg=C["base2"])
        row2.pack(fill=tk.X, pady=1)
        self._lbl(row2, "Local Repo:").pack(side=tk.LEFT)
        btn_browse = tk.Button(row2, text="📁", bg=C["surface"], fg=C["accent_light"],
                               font=("Helvetica", 9), relief=tk.FLAT, padx=4,
                               command=self._browse_repo)
        btn_browse.pack(side=tk.LEFT, padx=(2, 2))
        ToolTip(btn_browse, "📁 Browse filesystem to select the repository root directory")
        self.repo_entry = self._entry(row2, 55)
        self.repo_entry.pack(side=tk.LEFT, padx=(0, 0), fill=tk.X, expand=True)
        ToolTip(self.repo_entry,
                "📂 Absolute path to the local Git repository root\n\n"
                "Job configs will be stored under:\n"
                "  <this path>/JenkinsJobConfiguration/<repo_job_name>/\n\n"
                "This should be the root of your Gerrit/Git clone\n"
                "where Jenkins job configurations are version-controlled.")

    def _build_sections_frame(self, parent):
        frame = tk.LabelFrame(parent, text="  ☑ Sections (select which to read/write)  ",
                              bg=C["base2"], fg=C["accent_light"],
                              font=("Helvetica", 9, "bold"), padx=10, pady=6)
        frame.pack(fill=tk.X, pady=(0, 4))

        # Item-level selection state
        self._item_selection = {}  # {"params": {name: bool}, "launchers": {idx_str: bool}}

        sec_grid = tk.Frame(frame, bg=C["base2"])
        sec_grid.pack(fill=tk.X)

        # Simple sections (no dropdown)
        simple_sections = [
            ("description", "📝 Description",
             "📝 Job description (HTML)\nThe main description shown at the top of the Jenkins job page"),
            ("inject", "💉 Inject Variables",
             "💉 EnvInject Groovy script\nSets environment variables at build start using Groovy code"),
            ("build_name", "🏷️ Build Name",
             "🏷️ Build Name Setter template\nDefines the display name pattern for each build (e.g. #${BUILD_NUMBER} - ${ENV})"),
            ("email", "📧 Email Template",
             "📧 Extended Email Publisher template\nHTML template for build notification emails"),
        ]

        col, row_idx = 0, 0
        for key, label, tip in simple_sections:
            var = tk.BooleanVar(value=self.settings["sections"].get(key, True))
            self.section_vars[key] = var
            cb = tk.Checkbutton(sec_grid, text=label, variable=var,
                                font=("Helvetica", 9), fg=C["text"], bg=C["base2"],
                                selectcolor=C["base2"], activebackground=C["base2"],
                                activeforeground=C["text"], bd=0, highlightthickness=0)
            cb.grid(row=row_idx, column=col, sticky="w", padx=15, pady=2)
            sec_grid.columnconfigure(col, weight=1, uniform="sec")
            ToolTip(cb, tip)
            col += 1
            if col >= 3:
                col = 0
                row_idx += 1

        # Expandable sections (with "⋯" dropdown for granular selection)
        expand_sections = [
            ("parameters", "⚙️ Parameters",
             "⚙️ Job parameters (Active Choices, Boolean, String)\n"
             "Groovy scripts that generate dynamic dropdowns and input fields\n"
             "Use ⋯ to select individual parameters"),
            ("build_steps", "🚀 Build Steps",
             "🚀 Shell script build steps (Script Launcher)\n"
             "The shell commands executed during the build phase\n"
             "Use ⋯ to select individual scripts"),
        ]
        for key, label, tip in expand_sections:
            var = tk.BooleanVar(value=self.settings["sections"].get(key, True))
            self.section_vars[key] = var
            f = tk.Frame(sec_grid, bg=C["base2"])
            f.grid(row=row_idx, column=col, sticky="w", padx=15, pady=2)
            sec_grid.columnconfigure(col, weight=1, uniform="sec")

            cb = tk.Checkbutton(f, text=label, variable=var,
                                font=("Helvetica", 9), fg=C["text"], bg=C["base2"],
                                selectcolor=C["base2"], activebackground=C["base2"],
                                activeforeground=C["text"], bd=0, highlightthickness=0)
            cb.pack(side=tk.LEFT)
            ToolTip(cb, tip)

            # Store ref for color changes on partial selection
            if key == "parameters":
                self._params_cb = cb
            else:
                self._launchers_cb = cb

            # "⋯" button to open item picker
            exp_btn = tk.Label(f, text="⋯", bg=C["base2"], fg=C["accent_light"],
                               font=("Helvetica", 10, "bold"), cursor="hand2")
            exp_btn.pack(side=tk.LEFT, padx=4)
            exp_btn.bind("<Button-1>", lambda e, k=key: self._show_item_dropdown(k))
            ToolTip(exp_btn, "⋯ Open item selector\nPick individual items to include/exclude.\n"
                    "Yellow checkbox = partial selection active")

            col += 1
            if col >= 3:
                col = 0
                row_idx += 1

        # All / None buttons
        btn_frame = tk.Frame(frame, bg=C["base2"])
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        btn_all = tk.Button(btn_frame, text="All", width=5, bg=C["surface"], fg=C["text"],
                  font=("Helvetica", 8), relief=tk.FLAT,
                  command=lambda: [v.set(True) for v in self.section_vars.values()])
        btn_all.pack(side=tk.LEFT, padx=3)
        ToolTip(btn_all, "Select all sections for read/write operations")
        btn_none = tk.Button(btn_frame, text="None", width=5, bg=C["surface"], fg=C["text"],
                  font=("Helvetica", 8), relief=tk.FLAT,
                  command=lambda: [v.set(False) for v in self.section_vars.values()])
        btn_none.pack(side=tk.LEFT, padx=3)
        ToolTip(btn_none, "Deselect all sections")

    def _build_log_area(self, parent):
        frame = tk.LabelFrame(parent, text="  📜 Log  ",
                              bg=C["base2"], fg=C["accent_light"],
                              font=("Helvetica", 9, "bold"), padx=5, pady=5)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        # Top bar with debug button
        top = tk.Frame(frame, bg=C["base2"])
        top.pack(fill=tk.X, pady=(0, 3))
        btn_raw = tk.Button(top, text="🐛 Save Raw XML", bg=C["surface"], fg=C["dim"],
                            font=("Helvetica", 8), relief=tk.FLAT, padx=6, pady=1,
                            activebackground=C["surface2"], command=self._action_save_raw_xml)
        btn_raw.pack(side=tk.RIGHT)
        ToolTip(btn_raw, "🐛 Debug: save the full raw config.xml\nto a file of your choice")

        self.log_text = scrolledtext.ScrolledText(
            frame, font=("Consolas", 9), bg=C["base"], fg=C["text"],
            insertbackground=C["text"], state="disabled", height=10,
            relief=tk.FLAT, borderwidth=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _build_bottom_bar(self):
        bottom = tk.Frame(self.root, bg=C["base2"], padx=10, pady=6)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)

        # Row 1: Action buttons (grouped by workflow)
        btn_row = tk.Frame(bottom, bg=C["base2"])
        btn_row.pack(fill=tk.X, pady=(0, 6))

        # Primary actions (colored) — grouped: Read | Write
        read_buttons = [
            ("📥 Read from Job", self._action_read_job, C["orange"],
             "📥 Read config from Jenkins job\n⚡ Downloads config + generates template"),
            ("📂 Read from Repo", self._action_read_repo, C["accent"],
             "📂 Read config from local repo files\n⚠️ Upload requires template"),
        ]
        for text, cmd, color, tip in read_buttons:
            btn = tk.Button(btn_row, text=text, command=cmd, bg=color, fg="white",
                            font=("Helvetica", 9, "bold"), relief=tk.FLAT,
                            activebackground=color, activeforeground="white",
                            padx=10, pady=4)
            btn.pack(side=tk.LEFT, padx=3)
            ToolTip(btn, tip)
            if "from Job" in text:
                self._btn_read_job = btn

        # Spacer between read and write groups
        tk.Frame(btn_row, bg=C["base2"], width=12).pack(side=tk.LEFT)

        write_buttons = [
            ("💾 Write to Repo", self._action_save_repo, C["green"],
             "💾 Write config sections to local repo\n📁 Creates dirs/files if needed"),
            ("🚀 Write to Job", self._action_upload, C["purple"],
             "🚀 Upload config to Jenkins (create/update)\n⚠️ Requires template + config loaded"),
        ]
        for text, cmd, color, tip in write_buttons:
            btn = tk.Button(btn_row, text=text, command=cmd, bg=color, fg="white",
                            font=("Helvetica", 9, "bold"), relief=tk.FLAT,
                            activebackground=color, activeforeground="white",
                            padx=10, pady=4)
            btn.pack(side=tk.LEFT, padx=3)
            ToolTip(btn, tip)
            if "to Job" in text:
                self._btn_write_job = btn

        # Secondary actions (right side)
        secondary = [
            ("Quit", self._on_quit, "#616161", "❌ Save settings and exit"),
            ("🔄 Reset", self._action_reset, C["surface2"], "🔄 Clear config (credentials preserved)"),
            ("💾 Log", self._action_save_log, C["surface2"], "💾 Save session log to file"),
            ("⊞", self._action_reset_geometry, C["surface2"], "⊞ Reset window to default size"),
            ("📜", self._show_history, C["surface2"], "📜 Version history and changelog"),
        ]
        for text, cmd, color, tip in secondary:
            btn = tk.Button(btn_row, text=text, command=cmd, bg=color, fg=C["text"],
                            font=("Helvetica", 9), relief=tk.FLAT,
                            activebackground=C["surface2"], activeforeground=C["text"],
                            padx=8, pady=4)
            btn.pack(side=tk.RIGHT, padx=2)
            ToolTip(btn, tip)

        # Row 2: Status indicators
        status_row = tk.Frame(bottom, bg=C["base2"])
        status_row.pack(fill=tk.X)

        # Job indicator (template): ○ not done, 🟡 reading, 🟢 loaded, 🔴 failed
        _JOB_LEGEND = (
            "📥 Job (Template) status:\n"
            "○  Not yet performed\n"
            "🟡 Reading — operation in progress\n"
            "🟢 Loaded — template read from Jenkins\n"
            "🔴 Failed"
        )
        self._tpl_text_lbl = tk.Label(status_row, text="📥 Job:",
                                      font=("Helvetica", 9), fg=C["text"], bg=C["base2"])
        self._tpl_text_lbl.pack(side=tk.LEFT, padx=(5, 0))
        ToolTip(self._tpl_text_lbl, _JOB_LEGEND)

        self._tpl_dot_lbl = tk.Label(status_row, text="○",
                                     font=("Segoe UI", 12), fg=C["dim"], bg=C["base2"])
        self._tpl_dot_lbl.pack(side=tk.LEFT, padx=(2, 8))
        self._tpl_dot_tooltip = ToolTip(self._tpl_dot_lbl, "Not yet performed")

        # Repo indicator (config): ○ not done, 🟡 reading/merging, 🟢 loaded, 🔴 failed
        _REPO_LEGEND = (
            "📂 Repo (Config) status:\n"
            "○  Not yet performed\n"
            "🟡 Reading/Merging — operation in progress\n"
            "🟢 Loaded — config read and merged from repo\n"
            "🔴 Failed"
        )
        self._cfg_text_lbl = tk.Label(status_row, text="📂 Repo:",
                                      font=("Helvetica", 9), fg=C["text"], bg=C["base2"])
        self._cfg_text_lbl.pack(side=tk.LEFT, padx=(5, 0))
        ToolTip(self._cfg_text_lbl, _REPO_LEGEND)

        self._cfg_dot_lbl = tk.Label(status_row, text="○",
                                     font=("Segoe UI", 12), fg=C["dim"], bg=C["base2"])
        self._cfg_dot_lbl.pack(side=tk.LEFT, padx=(2, 8))
        self._cfg_dot_tooltip = ToolTip(self._cfg_dot_lbl, "Not yet performed")

        self.status_label = tk.Label(status_row, text="Ready",
                                     font=("Helvetica", 9), fg=C["dim"], bg=C["base2"])
        self.status_label.pack(side=tk.RIGHT, padx=5)

    # --- Widget helpers ---

    def _lbl(self, parent, text: str) -> tk.Label:
        return tk.Label(parent, text=text, font=("Helvetica", 9),
                        fg=C["dim"], bg=C["base2"])

    def _entry(self, parent, width=20, **kwargs) -> tk.Entry:
        return tk.Entry(parent, width=width, font=("Helvetica", 9),
                        bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                        relief=tk.FLAT, borderwidth=3, **kwargs)

    # --- Logging ---

    def _setup_logging(self):
        handler = TextHandler(self.log_text)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
        self.logger.addHandler(handler)

    def _log_init(self):
        """Log application initialization steps."""
        self.logger.info(f"[INIT] ═══ Jenkins Job Configuration Tool ver. {VERSION} ═══")
        self.logger.info(f"[INIT] App directory: {APP_DIR}")
        if os.path.isfile(SETTINGS_FILE):
            self.logger.info(f"[INIT] ✓ Settings loaded from: {os.path.basename(SETTINGS_FILE)}")
        else:
            self.logger.info(f"[INIT] No settings file found — using defaults")
        tpl_path = os.path.join(APP_DIR, self.settings.get("template_filename", "job_template.xml"))
        if os.path.isfile(tpl_path):
            self.logger.info(f"[INIT] ✓ Template found: {os.path.basename(tpl_path)}")
        else:
            self.logger.info(f"[INIT] ⚠ No template file — use 'Read Job' to generate one")
        if self.settings.get("url"):
            self.logger.info(f"[INIT] Jenkins URL: {self.settings['url']}")
        if self.settings.get("job_name"):
            self.logger.info(f"[INIT] Job name: {self.settings['job_name']}")
        repo_root = self.settings.get("repo_root", "")
        if repo_root and os.path.isdir(repo_root):
            self.logger.info(f"[INIT] ✓ Repo root: {repo_root}")
        else:
            self.logger.info(f"[INIT] ⚠ Repo root not configured — will prompt on first Save/Read Repo")
        self.logger.info(f"[INIT] Repo subdir: {self.settings.get('repo_output_dir', 'JenkinsJobConfiguration')}/")
        self.logger.info(f"[INIT] ═══ Ready ═══")

    # --- Settings ---

    def _load_settings_to_ui(self):
        self.url_entry.insert(0, self.settings.get("url", ""))
        self.user_entry.insert(0, self.settings.get("user", ""))
        self.token_entry.insert(0, self.settings.get("token", ""))
        self.agent_entry.insert(0, self.settings.get("agent", ""))
        self.jdk_entry.insert(0, self.settings.get("jdk", ""))
        self._job_entry_var.set(self.settings.get("job_name", ""))
        self.repo_job_entry.insert(0, self.settings.get("repo_job_name", ""))
        self.repo_entry.insert(0, self.settings.get("repo_root", ""))

    def _save_settings_from_ui(self):
        self.settings["url"] = self.url_entry.get().strip()
        self.settings["user"] = self.user_entry.get().strip()
        self.settings["token"] = self.token_entry.get().strip()
        self.settings["agent"] = self.agent_entry.get().strip()
        self.settings["jdk"] = self.jdk_entry.get().strip()
        self.settings["job_name"] = self.job_entry.get().strip()
        self.settings["repo_job_name"] = self.repo_job_entry.get().strip()
        self.settings["repo_root"] = self.repo_entry.get().strip()
        self.settings["sections"] = {k: v.get() for k, v in self.section_vars.items()}
        self.settings["window_geometry"] = self.root.geometry()
        save_settings(SETTINGS_FILE, self.settings)

    def _populate_agent_jdk(self):
        """Populate Agent and JDK fields from parsed config if available."""
        if not self.config:
            return
        agent = self.config.get("agent_label", "")
        if agent:
            self.agent_entry.delete(0, tk.END)
            self.agent_entry.insert(0, agent)
            self.logger.info(f"[INFO] Agent field populated: '{agent}'")
        jdk = self.config.get("jdk", "")
        if jdk:
            self.jdk_entry.delete(0, tk.END)
            self.jdk_entry.insert(0, jdk)
            self.logger.info(f"[INFO] JDK field populated: '{jdk}'")

    def _get_sections(self) -> dict:
        return {k: v.get() for k, v in self.section_vars.items()}

    # --- Status ---

    def _update_status_indicators(self):
        tpl_path = os.path.join(APP_DIR, self.settings.get("template_filename", "job_template.xml"))
        tpl_exists = os.path.isfile(tpl_path)
        current_job = self.job_entry.get().strip() if hasattr(self, "job_entry") else ""

        # --- Read template meta ---
        tpl_meta = {}
        if tpl_exists:
            try:
                with open(tpl_path, "r", encoding="utf-8") as f:
                    tpl_text = f.read(2048)
                tpl_meta = parse_template_meta(tpl_text)
            except Exception:
                pass

        # --- Job (Template) dot ---
        if not tpl_exists:
            # Not yet performed
            self._tpl_dot_lbl.config(text="○", fg=C["dim"])
            self._tpl_dot_tooltip.text = "Not yet performed — use 'Read from Job'"
            self.template_available = False
        else:
            template_job = tpl_meta.get("job_name", "").strip()
            if not current_job or not template_job or template_job == current_job:
                self._tpl_dot_lbl.config(text="●", fg="#00e676")  # green
                self.template_available = True
                tpl_tip = "── Template provenance ──\n" + format_meta_tooltip(tpl_meta) if tpl_meta else "Template loaded."
            else:
                self._tpl_dot_lbl.config(text="●", fg="#ffaa00")  # yellow — mismatch
                self.template_available = False
                tpl_tip = (
                    f"⚠️ Template belongs to a different job!\n"
                    f"  Template job : {tpl_meta.get('job_name', '?')}\n"
                    f"  Current job  : {current_job}\n"
                    "Run 'Read from Job' to regenerate."
                )
            self._tpl_dot_tooltip.text = tpl_tip

        # --- Repo (Config) dot ---
        if self.config:
            self._cfg_dot_lbl.config(text="●", fg="#00e676")  # green
            m = self._config_meta
            src = m.get("_source", "")
            if src == "job":
                cfg_tip = (
                    "── Config from Jenkins ──\n"
                    f"🌐 URL      : {m.get('_jenkins_url', '?')}\n"
                    f"🔧 Job      : {m.get('_job_name', '?')}\n"
                    f"📅 Read at  : {m.get('_read_at', '?')}"
                )
            elif src == "repo":
                cfg_tip = (
                    "── Config from Repo ──\n"
                    f"🔧 Job      : {m.get('_job_name', '?')}\n"
                    f"📁 Dir      : {m.get('_repo_dir', '?')}\n"
                    f"📅 Read at  : {m.get('_read_at', '?')}"
                )
            else:
                cfg_tip = f"Config loaded from: {self._config_source or 'unknown'}"
            self._cfg_dot_tooltip.text = cfg_tip
        else:
            # Not yet performed
            self._cfg_dot_lbl.config(text="○", fg=C["dim"])
            self._cfg_dot_tooltip.text = "Not yet performed — use 'Read from Job' or 'Read from Repo'"

    def _set_status(self, text: str):
        self.status_label.config(text=text)

    # --- Actions ---

    def _show_item_dropdown(self, section_key):
        """Popup with individual item checkboxes for parameters or launchers."""
        if not self.config:
            self.logger.warning("[WARNING] Item selection attempted without loaded config")
            show_info(self.root, "ℹ️ No Configuration",
                      "📋 No items available.\n\n"
                      "Load a configuration first:\n"
                      "  • 📥 Read Job — from Jenkins\n"
                      "  • 📂 Read Repo — from local files")
            return

        is_params = section_key == "parameters"
        items = self.config.get("parameters" if is_params else "build_steps", [])
        if not items:
            section_label = "parameters" if is_params else "build steps"
            self.logger.warning(f"[WARNING] No {section_label} found in current config")
            show_info(self.root, "ℹ️ No Items",
                      f"📋 No {section_label} found in current configuration.\n\n"
                      "The job may not contain these elements yet.")
            return

        win = tk.Toplevel(self.root)
        win.title("⚙️ Select Parameters" if is_params else "🚀 Select Build Steps")
        geo_key = "win_params_geometry" if is_params else "win_steps_geometry"
        win.geometry(self.settings.get(geo_key, "450x320"))
        win.configure(bg=C["base"])
        win.transient(self.root)

        # Buttons at top
        btn_frame = tk.Frame(win, bg=C["base"])
        btn_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        import re
        item_vars = {}
        existing = self._item_selection.get("params" if is_params else "launchers", {})

        def apply_and_close():
            sel_key = "params" if is_params else "launchers"
            self._item_selection[sel_key] = {k: v.get() for k, v in item_vars.items()}
            all_sel = all(v.get() for v in item_vars.values())
            none_sel = not any(v.get() for v in item_vars.values())
            cb_widget = self._params_cb if is_params else self._launchers_cb
            if none_sel:
                self.section_vars[section_key].set(False)
                cb_widget.configure(fg=C["text"])
            elif all_sel:
                self.section_vars[section_key].set(True)
                cb_widget.configure(fg=C["text"])
            else:
                self.section_vars[section_key].set(True)
                cb_widget.configure(fg=C["yellow"])  # Partial selection → yellow
            n = sum(1 for v in item_vars.values() if v.get())
            self.logger.info(f"[INFO] {sel_key}: {n}/{len(items)} selected")
            self.settings[geo_key] = win.geometry()
            win.destroy()

        tk.Button(btn_frame, text="All", width=5, bg=C["surface"], fg=C["text"],
                  font=("Helvetica", 9), relief=tk.FLAT,
                  command=lambda: [v.set(True) for v in item_vars.values()]).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="None", width=5, bg=C["surface"], fg=C["text"],
                  font=("Helvetica", 9), relief=tk.FLAT,
                  command=lambda: [v.set(False) for v in item_vars.values()]).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="✓ Apply", width=8, bg=C["green"], fg="white",
                  font=("Helvetica", 9, "bold"), relief=tk.FLAT,
                  command=apply_and_close).pack(side=tk.RIGHT, padx=3)
        tk.Button(btn_frame, text="Cancel", width=7, bg="#616161", fg="white",
                  font=("Helvetica", 9), relief=tk.FLAT,
                  command=lambda: (self.settings.update({geo_key: win.geometry()}), win.destroy())).pack(side=tk.RIGHT, padx=3)

        # Scrollable list
        canvas = tk.Canvas(win, bg=C["base"], highlightthickness=0)
        scrollbar = tk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=C["base"])
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 8))

        for i, item in enumerate(items):
            if is_params:
                name = item.get("name", f"param_{i}")
                label = f"{i:02d} — {name}"
                key = name
            else:
                match = re.search(r"Script Name[:\s]+(.+)", item, re.IGNORECASE)
                label = f"{i:02d} — {match.group(1).strip() if match else 'Step ' + str(i)}"
                key = str(i)
            var = tk.BooleanVar(value=existing.get(key, True))
            item_vars[key] = var
            tk.Checkbutton(scroll_frame, text=f"  {label}", variable=var,
                           bg=C["base"], fg=C["text"], selectcolor=C["base"],
                           activebackground=C["base"], activeforeground=C["text"],
                           font=("Helvetica", 9), bd=0, highlightthickness=0).pack(anchor="w", pady=1)

        # Center popup
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")
        win.grab_set()

    def _get_filtered_config(self) -> dict:
        """Apply granular item selection to config before save/upload."""
        if not self.config:
            return {}
        config = dict(self.config)
        # Filter parameters
        param_sel = self._item_selection.get("params")
        if param_sel:
            config["parameters"] = [
                p for p in config.get("parameters", [])
                if param_sel.get(p.get("name", ""), True)
            ]
        # Filter build steps
        launcher_sel = self._item_selection.get("launchers")
        if launcher_sel:
            config["build_steps"] = [
                s for i, s in enumerate(config.get("build_steps", []))
                if launcher_sel.get(str(i), True)
            ]
        return config

    def _log_config_summary(self, config: dict):
        """Log a structured summary of all items in the loaded config."""
        self.logger.info("[INFO] ─── Config Summary ───")
        if config.get("description"):
            self.logger.info("[INFO]   • Description")
        if config.get("inject_variables"):
            self.logger.info("[INFO]   • Inject Variables")
        if config.get("build_name"):
            self.logger.info("[INFO]   • Build Name Setter")
        if config.get("email_template"):
            self.logger.info("[INFO]   • Email Template")
        for p in config.get("parameters", []):
            if isinstance(p, dict):
                self.logger.info(f"[INFO]   • Param [{p.get('type','?')}] {p.get('name','?')}")
        for i, s in enumerate(config.get("build_steps", []), 1):
            if isinstance(s, dict):
                label = s.get("script_name") or s.get("name") or f"Step #{i}"
            else:
                # s is raw shell script text — extract first non-empty, non-comment line
                first = next((ln.strip() for ln in str(s).splitlines()
                              if ln.strip() and not ln.strip().startswith("#")), f"Step #{i}")
                label = first[:60] + ("…" if len(first) > 60 else "")
            self.logger.info(f"[INFO]   • Launcher [{i}] {label}")
        self.logger.info("[INFO] ──────────────────────")

    def _action_read_job(self):
        url = self.url_entry.get().strip()
        user = self.user_entry.get().strip()
        token = self.token_entry.get().strip()
        job = self.job_entry.get().strip()

        if not all([url, user, token, job]):
            self.logger.warning("[WARNING] Read Job: required fields missing (URL/User/Token/Job)")
            show_warning(self.root, "Missing Fields", "Please fill URL, User, Token, and Job Name.")
            return

        # Pre-check connectivity
        if not self._check_jenkins_reachable():
            return

        self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.logger.info(f"[INFO] ▶ READ JOB — START — '{job}'")
        self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self._set_status("Reading from Jenkins...")

        # Set Job indicator to yellow (in progress)
        self._tpl_dot_lbl.config(text="●", fg="#ffaa00")
        self._tpl_dot_tooltip.text = "Reading from Jenkins..."

        def task():
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

                client = JenkinsClient(url, user, token)
                xml_text = client.read_config(job)
                self.raw_xml = xml_text
                self.logger.info(f"[INFO] ✓ Downloaded config.xml ({len(xml_text)} bytes)")

                parser = ConfigParser(xml_text)
                self.config = parser.parse_all()
                self._config_source = "job"
                self.logger.info(f"[INFO] ✓ Parsing complete — "
                                 f"{len(self.config.get('parameters',[]))} params, "
                                 f"{len(self.config.get('build_steps',[]))} steps")
                self._log_config_summary(self.config)

                tpl_gen = TemplateGenerator(xml_text, self.config,
                                            source_url=url, job_name=job,
                                            extracted_at=datetime.now(timezone.utc).strftime(
                                                "%Y-%m-%d %H:%M:%S UTC"))
                template = tpl_gen.generate()
                tpl_path = os.path.join(APP_DIR, self.settings.get("template_filename", "job_template.xml"))
                with open(tpl_path, "w", encoding="utf-8") as f:
                    f.write(template)
                self.logger.info(f"[INFO] ✓ Template generated: {os.path.basename(tpl_path)}")

                # Store config provenance: read directly from Jenkins
                tpl_meta = parse_template_meta(template)
                self._config_meta = {
                    "_source":       "job",
                    "_read_at":      datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "_jenkins_url":  url,
                    "_job_name":     job,
                    # template fields for reference
                    "extracted_from": tpl_meta.get("extracted_from", url),
                    "job_name":       tpl_meta.get("job_name", job),
                    "extracted_at":   tpl_meta.get("extracted_at", ""),
                    "job_version":    tpl_meta.get("job_version", ""),
                }

                # Populate agent/jdk from parsed config
                self.root.after(0, self._populate_agent_jdk)
                self.root.after(0, self._update_status_indicators)
                self.root.after(0, self._set_status, "Read Job complete ✓")
                self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                self.logger.info(f"[INFO] ■ READ JOB — COMPLETED — '{job}'")
                self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            except Exception as e:
                tb = traceback.format_exc()
                self.logger.error(f"[ERROR] ✗ Read Job failed: {e}")
                self.logger.debug(f"[DEBUG] Traceback:\n{tb}")
                self.root.after(0, self._set_status, f"Error: {e}")
                # Set Job indicator to red (failed)
                self.root.after(0, lambda: self._tpl_dot_lbl.config(text="●", fg="#ff1744"))
                self.root.after(0, lambda: setattr(self._tpl_dot_tooltip, 'text', f"Failed: {str(e)[:80]}"))
                # Disable Jenkins buttons if connection-related error
                err_str = str(e)
                if any(kw in err_str for kw in ("ConnectionError", "NameResolution",
                                                 "Timeout", "MaxRetry", "Connection refused")):
                    self.root.after(0, self._update_conn_status, False,
                                    f"Connection lost: {err_str[:80]}")
                self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                self.logger.info(f"[ERROR] ■ READ JOB — FAILED — '{job}'")
                self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        threading.Thread(target=task, daemon=True).start()

    def _action_read_repo(self):
        job = self._get_repo_job_name()
        if not job:
            self.logger.warning("[WARNING] Read Repo: job name missing")
            show_warning(self.root, "Missing Field", "Please enter a Job Name.")
            return

        base_dir = self._get_repo_base_dir()
        if not base_dir:
            return

        self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.logger.info(f"[INFO] ▶ READ REPO — START — '{job}'")
        self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self._set_status("Reading from repo...")

        # Set Repo indicator to yellow (in progress)
        self._cfg_dot_lbl.config(text="●", fg="#ffaa00")
        self._cfg_dot_tooltip.text = "Reading from repo..."

        try:
            reader = RepoReader(base_dir, job, self.settings)
            self.logger.info(f"[INFO]   Job dir: {reader.job_dir}")
            self.logger.info(f"[INFO]   Params dir: {reader.params_dir}")
            self.logger.info(f"[INFO]   Launchers dir: {reader.launchers_dir}")
            self.config = reader.read_all(self._get_sections())
            self._config_source = "repo"  # mark source so Upload uses template + repo sections
            self.logger.info(f"[INFO] ✓ Read Repo complete — "
                             f"{len(self.config.get('parameters',[]))} params, "
                             f"{len(self.config.get('build_steps',[]))} steps")
            self._log_config_summary(self.config)
            self.logger.debug(f"[DEBUG] Config source set to 'repo' — Upload will use smart generation")
            if self.raw_xml:
                self.logger.debug("[DEBUG] Original raw_xml available — deselected items will preserve Jenkins content")
            else:
                self.logger.warning("[WARN] No raw_xml in memory — run 'Read Job' first for full deselection support")

            # Store config provenance: read from local repo
            read_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            tpl_path = os.path.join(APP_DIR, self.settings.get("template_filename", "job_template.xml"))
            tpl_meta = {}
            if os.path.isfile(tpl_path):
                try:
                    with open(tpl_path, "r", encoding="utf-8") as f:
                        tpl_meta = parse_template_meta(f.read(2048))
                except Exception:
                    pass
            repo_dir = reader.job_dir  # absolute path to the job's repo dir
            self._config_meta = {
                "_source":       "repo",
                "_read_at":      read_at,
                "_repo_dir":     repo_dir,
                "_job_name":     job,
                # template of reference
                "extracted_from": tpl_meta.get("extracted_from", ""),
                "job_name":       tpl_meta.get("job_name", ""),
                "extracted_at":   tpl_meta.get("extracted_at", ""),
                "job_version":    tpl_meta.get("job_version", ""),
                "merged_at":      tpl_meta.get("merged_at", ""),
            }

            self._update_status_indicators()
            self._set_status("Read Repo complete ✓")
            self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.logger.info(f"[INFO] ■ READ REPO — COMPLETED — '{job}'")
            self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        except Exception as e:
            self.logger.error(f"[ERROR] ✗ Read Repo failed: {e}")
            self._set_status(f"Error: {e}")
            # Set Repo indicator to red (failed)
            self._cfg_dot_lbl.config(text="●", fg="#ff1744")
            self._cfg_dot_tooltip.text = f"Failed: {str(e)[:80]}"
            self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.logger.info(f"[ERROR] ■ READ REPO — FAILED — '{job}'")
            self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    def _browse_repo(self):
        """Open directory picker for repo root."""
        current = self.repo_entry.get().strip()
        initial = current if current and os.path.isdir(current) else os.path.expanduser("~")
        selected = filedialog.askdirectory(title="Select Repository Root Directory", initialdir=initial)
        if selected:
            self.repo_entry.delete(0, tk.END)
            self.repo_entry.insert(0, selected)
            self.settings["repo_root"] = selected
            self.logger.info(f"[INFO] ✓ Repository root set: {selected}")

    def _get_repo_job_name(self) -> str:
        """Get repo job directory name (falls back to Jenkins job name)."""
        return self.repo_job_entry.get().strip() or self.job_entry.get().strip()

    def _get_repo_base_dir(self) -> Optional[str]:
        """Get the repo base directory from entry field. Shows error if not set."""
        repo_root = self.repo_entry.get().strip()
        if not repo_root:
            self.logger.error("[ERROR] Repository root directory not configured")
            show_error(self.root, "⚠️ Repository Not Set",
                       "No repository directory is configured.\n\n"
                       "Please set the 'Local Repo' path in the Target section.\n"
                       "Use the 📁 button to browse, or type the absolute path.\n\n"
                       "Job files will be stored under:\n"
                       f"  <repo>/{self.settings.get('repo_output_dir', 'JenkinsJobConfiguration')}/<job>/")
            return None
        if not os.path.isdir(repo_root):
            self.logger.error(f"[ERROR] Repository directory does not exist: {repo_root}")
            show_error(self.root, "⚠️ Directory Not Found",
                       f"The configured repository path does not exist:\n\n  {repo_root}\n\n"
                       "Please check the path or use 📁 to select a valid directory.")
            return None
        return os.path.join(repo_root, self.settings.get("repo_output_dir", "JenkinsJobConfiguration"))

    def _action_save_repo(self):
        if not self.config:
            self.logger.warning("[WARNING] Save to Repo: no configuration in memory")
            show_warning(self.root, "No Config", "No configuration loaded. Read from Jenkins or Repo first.")
            return

        job = self._get_repo_job_name()
        if not job:
            self.logger.warning("[WARNING] Save to Repo: job name missing")
            show_warning(self.root, "Missing Field", "Please enter a Job Name.")
            return

        base_dir = self._get_repo_base_dir()
        if not base_dir:
            return

        job_dir = os.path.join(base_dir, job)
        if os.path.isdir(job_dir):
            if not ask_confirm(self.root, "Overwrite?",
                               f"Directory already exists:\n\n  {job_dir}\n\nOverwrite contents?"):
                self.logger.info("[INFO] Save to Repo cancelled by user (directory exists)")
                return

        self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.logger.info(f"[INFO] ▶ SAVE TO REPO — START — '{job}'")
        self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self._set_status("Saving to repo...")
        try:
            writer = RepoWriter(base_dir, job, self.settings)
            config_to_write = self._get_filtered_config()
            writer.write_all(config_to_write, self._get_sections())
            self.logger.info(f"[INFO] ✓ Files written to: {os.path.join(base_dir, job)}")
            self._set_status("Save to Repo complete ✓")
            self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.logger.info(f"[INFO] ■ SAVE TO REPO — COMPLETED — '{job}'")
            self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        except Exception as e:
            self.logger.error(f"[ERROR] ✗ Save to Repo failed: {e}")
            self._set_status(f"Error: {e}")
            self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.logger.info(f"[ERROR] ■ SAVE TO REPO — FAILED — '{job}'")
            self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    def _collect_approval_warnings(self, config: dict) -> list:
        """Return a list of human-readable strings for scripts that need Jenkins approval.

        A script needs approval when sandbox=false (Groovy runs outside sandbox)
        or when it is an EnvInject Groovy script (always unsandboxed by design).
        """
        items = []

        # Active Choice / CascadeChoice parameters with sandbox=false
        for p in config.get("parameters", []):
            ptype = p.get("type", "")
            sandbox = p.get("sandbox", "true")
            # Only Groovy-based params have a sandbox concept
            if ptype in ("ActiveChoiceParam", "ActiveChoiceCascadeParam",
                         "ActiveChoiceReactiveParam", "ActiveChoiceReactiveReferenceParam"):
                if sandbox == "false":
                    items.append(f"Parameter [{ptype}]: {p.get('name', '?')}  (sandbox=false)")

        # Inject Variables (EnvInject Groovy — always runs unsandboxed)
        if config.get("inject_variables"):
            items.append("Inject Variables  (EnvInject Groovy, always unsandboxed)")

        return items

    def _action_upload(self):
        url = self.url_entry.get().strip()
        user = self.user_entry.get().strip()
        token = self.token_entry.get().strip()
        job = self.job_entry.get().strip()

        if not all([url, user, token, job]):
            self.logger.warning("[WARN] Upload: required fields missing")
            show_warning(self.root, "Missing Fields", "Please fill URL, User, Token, and Job Name.")
            return

        # Pre-check connectivity
        if not self._check_jenkins_reachable():
            return

        xml_to_upload = None
        if self._config_source == "repo" and self.config:
            # Config comes from repo — use template + generate with removal of deleted items
            tpl_path = os.path.join(APP_DIR, self.settings.get("template_filename", "job_template.xml"))
            if not os.path.isfile(tpl_path):
                self.logger.error("[ERROR] Upload: template file not found — cannot generate config")
                show_error(self.root, "No Template",
                           "Template file not found. Read from Jenkins first to generate it.")
                return
            # full_config = all items from repo (before GUI deselection)
            # filtered_config = only selected items in GUI
            # original_config = parsed from raw_xml (original Jenkins content for deselected items)
            filtered_config = self._get_filtered_config()
            original_config = None
            if self.raw_xml:
                original_config = ConfigParser(normalize_xml_declaration(self.raw_xml)).parse_all()
                self.logger.debug(f"[DEBUG] Original config parsed from raw_xml: "
                                  f"{len(original_config.get('parameters',[]))} params, "
                                  f"{len(original_config.get('build_steps',[]))} steps")
            else:
                self.logger.warning("[WARN] No raw_xml available — deselected items will use empty content")

            n_repo_params = len(self.config.get("parameters", []))
            n_filtered_params = len(filtered_config.get("parameters", []))
            n_repo_steps = len(self.config.get("build_steps", []))
            n_filtered_steps = len(filtered_config.get("build_steps", []))
            self.logger.info(f"[INFO] Upload mode: smart generation (source: repo)")
            self.logger.debug(f"[DEBUG] Repo params: {n_repo_params}, selected: {n_filtered_params}, "
                              f"deselected: {n_repo_params - n_filtered_params}")
            self.logger.debug(f"[DEBUG] Repo steps: {n_repo_steps}, selected: {n_filtered_steps}, "
                              f"deselected: {n_repo_steps - n_filtered_steps}")
            self.logger.debug(f"[DEBUG] Template: {os.path.basename(tpl_path)}")

            # Safety check: warn if repo has 0 steps but original job had steps
            if n_repo_steps == 0 and original_config and len(original_config.get("build_steps", [])) > 0:
                n_orig = len(original_config.get("build_steps", []))
                self.logger.warning(f"[WARN] ⚠ Repo has 0 launchers but Jenkins job has {n_orig}!")
                self.logger.warning(f"[WARN]   Launchers dir: {os.path.join(self._get_repo_base_dir() or '', self._get_repo_job_name(), self.settings.get('launchers_dir','ScriptLauncher'))}")
                result = ask_confirm(self.root, "⚠️ No Launchers Found",
                                     f"The repo has 0 launcher scripts, but the Jenkins job has {n_orig}.\n\n"
                                     f"Uploading will DELETE ALL BUILD STEPS from Jenkins!\n\n"
                                     f"Check that 'launchers_dir' in settings matches the folder name on disk.\n\n"
                                     f"Proceed anyway?")
                if not result:
                    self.logger.info("[INFO] Upload cancelled — launcher mismatch")
                    return

            gen = ConfigGenerator(tpl_path)
            xml_to_upload = gen.generate(filtered_config,
                                         full_repo_config=self.config,
                                         original_config=original_config)
            self.logger.debug(f"[DEBUG] Generated XML size: {len(xml_to_upload)} bytes")
            # Log upload manifest
            self.logger.info("[INFO] ─── Upload Manifest ───")
            if filtered_config.get("description"):
                self.logger.info("[INFO]   ✓ Description")
            if filtered_config.get("inject_variables"):
                self.logger.info("[INFO]   ✓ Inject Variables")
            if filtered_config.get("build_name"):
                self.logger.info("[INFO]   ✓ Build Name")
            if filtered_config.get("email_template"):
                self.logger.info("[INFO]   ✓ Email Template")
            for p in filtered_config.get("parameters", []):
                ptype = p.get('type', 'unknown')
                self.logger.info(f"[INFO]   ✓ Param: {p['name']} ({ptype})")
            for i, s in enumerate(filtered_config.get("build_steps", [])):
                label = s.split('\n')[0][:60] if s else f"Step {i}"
                self.logger.info(f"[INFO]   ✓ Step #{i}: {label}")
            self.logger.info("[INFO] ────────────────────────")
            source = "template + repo sections"
        elif self.raw_xml and self._config_source == "job":
            xml_to_upload = normalize_xml_declaration(self.raw_xml)
            self.logger.info("[INFO] Upload mode: raw XML passthrough (source: Read Job)")
            source = "raw XML (from Read Job)"
            filtered_config = {}   # no section-level config available in raw passthrough
        elif self.config:
            tpl_path = os.path.join(APP_DIR, self.settings.get("template_filename", "job_template.xml"))
            if not os.path.isfile(tpl_path):
                self.logger.error("[ERROR] Upload: template file not found — cannot generate config")
                show_error(self.root, "No Template",
                           "Template file not found. Read from Jenkins first to generate it.")
                return
            filtered_config = self._get_filtered_config()
            gen = ConfigGenerator(tpl_path)
            xml_to_upload = gen.generate(filtered_config)
            self.logger.info("[INFO] Upload mode: legacy generation (no repo context)")
            source = "template + sections"
        else:
            self.logger.warning("[WARN] Upload: no configuration available — nothing to upload")
            show_warning(self.root, "No Config", "No configuration loaded.")
            return

        result = ask_confirm(self.root, "Confirm Upload",
                             f"Upload to job '{job}' using {source}?\n\nThis will overwrite the current configuration.")
        if not result:
            self.logger.info("[INFO] Upload cancelled by user")
            return

        # --- Pre-upload: check for scripts that will need approval ---
        approval_items = self._collect_approval_warnings(filtered_config)
        if approval_items:
            lines = "\n".join(f"  • {item}" for item in approval_items)
            msg = (
                f"The following scripts have Sandbox DISABLED and will require\n"
                f"manual approval in Jenkins after the upload:\n\n"
                f"{lines}\n\n"
                f"→ Manage Jenkins → In-process Script Approval\n\n"
                f"Proceed with upload anyway?"
            )
            self.logger.warning(f"[WARN] Pre-upload approval check: {len(approval_items)} script(s) need approval")
            for item in approval_items:
                self.logger.warning(f"[WARN]   ⚠ {item}")
            if not ask_confirm(self.root, "⚠️ Script Approval Required", msg):
                self.logger.info("[INFO] Upload cancelled — script approval warning")
                return

        # Validate XML before uploading
        from xml.etree import ElementTree as ET
        try:
            ET.fromstring(normalize_xml_declaration(xml_to_upload))
            self.logger.debug("[DEBUG] XML validation passed ✓")
        except ET.ParseError as e:
            self.logger.error(f"[ERROR] Generated XML is invalid: {e}")
            # Save problematic XML for inspection
            debug_path = os.path.join(APP_DIR, "_debug_upload.xml")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(xml_to_upload)
            self.logger.error(f"[ERROR] Problematic XML saved to: {debug_path}")
            show_error(self.root, "Invalid XML",
                       f"Generated XML is not well-formed:\n\n{e}\n\n"
                       f"Debug file saved: {debug_path}")
            return

        self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.logger.info(f"[INFO] ▶ UPLOAD TO JENKINS — START — '{job}'")
        self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.logger.info(f"[INFO]   Source: {source}")
        self._set_status("Uploading to Jenkins...")

        def task():
            try:
                client = JenkinsClient(url, user, token)
                exists = client.job_exists(job)
                action = "update" if exists else "create"
                client.upload_config(job, xml_to_upload, create=not exists)
                self.logger.info(f"[INFO] ✓ Upload complete ({action}) for '{job}'")
                self.root.after(0, self._set_status, "Upload complete ✓")
                # Reminder: scripts needing approval (already warned pre-upload, just log)
                if approval_items:
                    self.logger.info(f"[INFO] ⚠ Reminder: {len(approval_items)} script(s) need approval in Jenkins:")
                    for item in approval_items:
                        self.logger.info(f"[INFO]   → {item}")
                self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                self.logger.info(f"[INFO] ■ UPLOAD TO JENKINS — COMPLETED — '{job}'")
                self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            except Exception as e:
                self.logger.error(f"[ERROR] ✗ Upload failed: {e}")
                # Save generated XML for debugging
                debug_path = os.path.join(APP_DIR, "_debug_upload.xml")
                try:
                    with open(debug_path, "w", encoding="utf-8") as f:
                        f.write(xml_to_upload)
                    self.logger.info(f"[DEBUG] Generated XML saved for inspection: {debug_path}")
                except Exception:
                    pass
                self.root.after(0, self._set_status, f"Upload error: {e}")
                self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                self.logger.info(f"[ERROR] ■ UPLOAD TO JENKINS — FAILED — '{job}'")
                self.logger.info(f"[INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        threading.Thread(target=task, daemon=True).start()

    def _action_reset(self):
        self.config = None
        self.raw_xml = None
        self._config_source = None
        self._item_selection = {}
        self._update_status_indicators()
        self._set_status("Reset ✓")
        self.logger.info("[INFO] 🔄 State reset (credentials preserved)")

    def _action_test_connection(self):
        """Test connectivity to Jenkins FEM and update the status indicator."""
        url = self.url_entry.get().strip()
        user = self.user_entry.get().strip()
        token = self.token_entry.get().strip()

        if not all([url, user, token]):
            self._update_conn_status(False, "Missing fields (URL/User/Token)")
            self.logger.warning("[WARN] 🔌 Connection test: missing required fields")
            return

        self.logger.info(f"[INFO] 🔌 Testing connection to: {url}")
        self._conn_status_label.config(fg="#ffaa00")  # yellow = testing

        def task():
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            client = JenkinsClient(url, user, token)
            success, message = client.check_connection()
            self.root.after(0, self._update_conn_status, success, message)

        threading.Thread(target=task, daemon=True).start()

    def _update_conn_status(self, success: bool, message: str):
        """Update the connection status indicator, log, and enable/disable Jenkins buttons."""
        self._conn_ok = success
        if success:
            self._conn_status_label.config(fg="#00e676")  # green
            self.logger.info(f"[INFO] 🔌 ✅ {message}")
            # Re-enable Jenkins buttons
            if hasattr(self, '_btn_read_job'):
                self._btn_read_job.config(state=tk.NORMAL)
            if hasattr(self, '_btn_write_job'):
                self._btn_write_job.config(state=tk.NORMAL)
        else:
            self._conn_status_label.config(fg="#ff1744")  # red
            self.logger.error(f"[ERROR] 🔌 ❌ {message}")
            # Disable Jenkins buttons
            if hasattr(self, '_btn_read_job'):
                self._btn_read_job.config(state=tk.DISABLED)
            if hasattr(self, '_btn_write_job'):
                self._btn_write_job.config(state=tk.DISABLED)
        # Update tooltip text directly
        status_icon = "✅" if success else "❌"
        ToolTip(self._conn_status_label, f"{status_icon} {message}")

    def _check_jenkins_reachable(self) -> bool:
        """Pre-check Jenkins connectivity before Read Job or Upload.

        Returns True if connection is OK, False otherwise (shows error).
        """
        url = self.url_entry.get().strip()
        user = self.user_entry.get().strip()
        token = self.token_entry.get().strip()

        if not all([url, user, token]):
            return True  # let the caller handle missing fields

        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        client = JenkinsClient(url, user, token)
        success, message = client.check_connection()
        self._update_conn_status(success, message)

        if not success:
            show_error(self.root, "⚠️ Jenkins Unreachable",
                       f"Cannot connect to Jenkins FEM:\n\n"
                       f"  {url}\n\n"
                       f"Error: {message}\n\n"
                       f"Please check:\n"
                       f"  • VPN/WARP connection\n"
                       f"  • DNS resolution\n"
                       f"  • URL, user and token correctness")
            return False
        return True

    def _action_reset_geometry(self):
        self.root.geometry(DEFAULT_GEOMETRY)
        # Reset sub-window geometries
        for key in ("win_history_geometry", "win_params_geometry", "win_steps_geometry"):
            self.settings.pop(key, None)
        self.logger.info(f"[INFO] ⊞ All windows reset to default size")

    def _action_save_raw_xml(self):
        if not self.raw_xml:
            self.logger.warning("[WARNING] Save Raw XML: no XML in memory")
            show_info(self.root, "No XML", "No raw XML in memory. Read from Jenkins first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xml", filetypes=[("XML files", "*.xml")],
            initialfile=f"{self.job_entry.get().strip()}_config.xml"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.raw_xml)
            self.logger.info(f"[INFO] ✓ Raw XML saved: {path}")
        else:
            self.logger.info("[INFO] Save Raw XML cancelled by user")

    def _action_save_log(self):
        """Save current session log to file."""
        path = filedialog.asksaveasfilename(
            defaultextension=".log", filetypes=[("Log files", "*.log"), ("Text files", "*.txt")],
            initialfile=f"session_{self.job_entry.get().strip() or 'log'}.log"
        )
        if path:
            content = self.log_text.get("1.0", tk.END)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.logger.info(f"[INFO] ✓ Session log saved: {path}")
        else:
            self.logger.info("[INFO] Save Log cancelled by user")

    def _show_history(self):
        """Show version changelog in a scrollable window."""
        win = tk.Toplevel(self.root)
        win.title(f"📜 Version History — ver. {VERSION}")
        win.geometry(self.settings.get("win_history_geometry", "500x350"))
        win.configure(bg=C["base"])
        win.transient(self.root)
        win.resizable(True, True)

        tk.Label(win, text=f"Jenkins Job Configuration Tool — ver. {VERSION}",
                 font=("Helvetica", 11, "bold"), fg=C["accent_light"], bg=C["base"],
                 pady=10).pack(fill=tk.X)

        txt = scrolledtext.ScrolledText(win, font=("Consolas", 9), bg=C["base2"],
                                        fg=C["text"], relief=tk.FLAT, wrap=tk.WORD,
                                        borderwidth=0, highlightthickness=0)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        txt.insert(tk.END, CHANGELOG)
        txt.configure(state="disabled")

        def close():
            self.settings["win_history_geometry"] = win.geometry()
            win.destroy()

        tk.Button(win, text="Close", width=8, bg=C["surface2"], fg=C["text"],
                  font=("Helvetica", 9, "bold"), relief=tk.FLAT,
                  command=close).pack(pady=(0, 10))

        win.protocol("WM_DELETE_WINDOW", close)
        win.update_idletasks()
        win.grab_set()

    def _on_quit(self):
        self._save_settings_from_ui()
        self.root.destroy()


# --- Entry Point ---

def main():
    app = JenkinsJobManagerApp()
    app.run()


if __name__ == "__main__":
    main()
