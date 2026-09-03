import os
import subprocess
import tempfile
import threading
import tkinter as tk
import urllib.error
import webbrowser
from datetime import datetime
from tkinter import messagebox

from paths import resource_path
from storage import NoteStore, note_category, split_title_body
from updater import download_installer, fetch_latest_release, is_newer
from vault import PasswordVault
from version import APP_VERSION, GITHUB_RELEASES_URL, SETUP_ASSET_NAME

COLORS = {
    "bg": "#F4F1EA",
    "sidebar": "#E7E1D6",
    "sidebar_hover": "#DDD5C6",
    "sidebar_active": "#D4C7B0",
    "paper": "#FFFCF7",
    "line": "#D8D0C4",
    "text": "#2B2A28",
    "muted": "#7A7468",
    "accent": "#3E5C45",
    "accent_hover": "#314A37",
    "danger": "#A33B2B",
    "danger_hover": "#862F22",
    "search": "#FFFCF7",
}

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
SEARCH_PLACEHOLDER = "Search notes..."
APP_AUTHOR = "Kenan"
CATEGORY_LABELS = (("public", "Public"), ("private", "Private"), ("hidden", "Hidden"))
CATEGORY_NAMES = {key: label for key, label in CATEGORY_LABELS}
CATEGORY_KEYS = {label: key for key, label in CATEGORY_LABELS}


def format_when(iso_value):
    if not iso_value:
        return ""
    try:
        moment = datetime.fromisoformat(iso_value)
    except ValueError:
        return iso_value
    now = datetime.now()
    month = MONTHS[moment.month - 1]
    if moment.date() == now.date():
        return moment.strftime("%H:%M")
    if moment.year == now.year:
        return f"{month} {moment.day}"
    return f"{month} {moment.day}, {moment.year}"


def one_line(text, limit=40):
    cleaned = " ".join((text or "").replace("\n", " ").split())
    if len(cleaned) > limit:
        return cleaned[:limit].rstrip() + "…"
    return cleaned


def preview_text(note):
    title = one_line(note.get("title") or "")
    if title:
        return title
    content = one_line(note.get("content") or "")
    return content or "Empty note"


class NotesApp:
    def __init__(self, root):
        self.root = root
        self.store = NoteStore()
        self.vault = PasswordVault()
        self.section = "public"
        self.selected_id = None
        self.note_buttons = {}
        self.tab_buttons = {}
        self.save_job = None
        self._loading = False
        self._lock_visible = False

        self._setup_window()
        self._build_ui()
        self._bind_shortcuts()
        self.set_section("public")
        self.root.after(2500, self._start_silent_update_check)

    def _setup_window(self):
        self.root.title("MyNotes")
        self.root.configure(bg=COLORS["bg"])
        icon_file = resource_path("assets", "icon.ico")
        if os.path.exists(icon_file):
            try:
                self.root.iconbitmap(icon_file)
            except tk.TclError:
                pass
        self.root.minsize(860, 540)
        width, height = 1040, 660
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 3
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _build_ui(self):
        shell = tk.Frame(self.root, bg=COLORS["bg"])
        shell.pack(fill="both", expand=True, padx=16, pady=16)

        sidebar = tk.Frame(shell, bg=COLORS["sidebar"], width=320)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        header = tk.Frame(sidebar, bg=COLORS["sidebar"])
        header.pack(fill="x", padx=14, pady=(16, 10))

        title_row = tk.Frame(header, bg=COLORS["sidebar"])
        title_row.pack(fill="x")

        tk.Label(
            title_row,
            text="MyNotes",
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 16),
        ).pack(side="left")

        self.new_btn = tk.Button(
            title_row,
            text="+ New",
            command=self.create_note,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            padx=10,
            pady=4,
            bd=0,
        )
        self.new_btn.pack(side="right")

        self.lock_btn = tk.Button(
            title_row,
            text="Lock",
            command=self.lock_private,
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            cursor="hand2",
            font=("Segoe UI Semibold", 8),
            padx=8,
            pady=4,
            bd=0,
        )

        tk.Label(
            header,
            text=f"by {APP_AUTHOR}",
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(2, 8))

        tabs = tk.Frame(header, bg=COLORS["sidebar"])
        tabs.pack(fill="x")
        for key, label in CATEGORY_LABELS:
            button = tk.Button(
                tabs,
                text=label,
                command=lambda value=key: self.set_section(value),
                relief="flat",
                cursor="hand2",
                font=("Segoe UI Semibold", 8),
                padx=4,
                pady=5,
                bd=0,
            )
            button.pack(side="left", expand=True, fill="x", padx=2)
            self.tab_buttons[key] = button

        search_wrap = tk.Frame(sidebar, bg=COLORS["search"], highlightbackground=COLORS["line"], highlightthickness=1)
        search_wrap.pack(fill="x", padx=14, pady=(10, 12))

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_wrap,
            textvariable=self.search_var,
            bg=COLORS["search"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.search_entry.pack(fill="x", padx=8, pady=7)
        self._set_placeholder(self.search_entry, self.search_var, SEARCH_PLACEHOLDER)

        tk.Label(
            sidebar,
            text="2026",
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
        ).pack(side="bottom", fill="x", pady=(0, 12))

        tk.Label(
            sidebar,
            text=f"Written by {APP_AUTHOR}",
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
        ).pack(side="bottom", fill="x")

        self.update_label = tk.Label(
            sidebar,
            text=f"v{APP_VERSION}  ·  Check for updates",
            bg=COLORS["sidebar"],
            fg=COLORS["accent"],
            font=("Segoe UI", 8),
            cursor="hand2",
        )
        self.update_label.pack(side="bottom", fill="x", pady=(0, 2))
        self.update_label.bind("<Button-1>", lambda _event: self.check_for_updates(manual=True))

        self.list_canvas = tk.Canvas(sidebar, bg=COLORS["sidebar"], highlightthickness=0, bd=0)
        self.list_scroll = tk.Scrollbar(sidebar, orient="vertical", command=self.list_canvas.yview)
        self.list_frame = tk.Frame(self.list_canvas, bg=COLORS["sidebar"])
        self.list_window = self.list_canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_canvas.configure(yscrollcommand=self.list_scroll.set)
        self.list_canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 12))
        self.list_scroll.pack(side="right", fill="y", pady=(0, 12), padx=(0, 6))

        self.list_frame.bind("<Configure>", self._on_list_configure)
        self.list_canvas.bind("<Configure>", self._on_canvas_configure)
        self.list_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.search_var.trace_add("write", lambda *_: self.refresh_list())

        self.editor = tk.Frame(shell, bg=COLORS["paper"], highlightbackground=COLORS["line"], highlightthickness=1)
        self.editor.pack(side="left", fill="both", expand=True, padx=(14, 0))

        self.top = tk.Frame(self.editor, bg=COLORS["paper"])
        self.top.pack(fill="x", padx=22, pady=(16, 0))

        self.meta_label = tk.Label(
            self.top,
            text="",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
        )
        self.meta_label.pack(side="left")

        self.delete_btn = tk.Button(
            self.top,
            text="Delete",
            command=self.delete_note,
            bg=COLORS["paper"],
            fg=COLORS["danger"],
            activebackground="#F6E8E4",
            activeforeground=COLORS["danger_hover"],
            relief="flat",
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            padx=8,
            pady=2,
            bd=0,
        )
        self.delete_btn.pack(side="right")

        self.category_var = tk.StringVar(value="Public")
        self.category_menu = tk.OptionMenu(
            self.top,
            self.category_var,
            "Public",
            "Private",
            "Hidden",
            command=self.on_category_change,
        )
        self.category_menu.config(
            bg=COLORS["paper"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar"],
            activeforeground=COLORS["text"],
            highlightthickness=0,
            relief="flat",
            font=("Segoe UI", 9),
            bd=0,
            cursor="hand2",
        )
        self.category_menu.pack(side="right", padx=(0, 10))

        self.title_var = tk.StringVar()
        self.title_var.trace_add("write", lambda *_: self.schedule_save())
        self.title_entry = tk.Entry(
            self.editor,
            textvariable=self.title_var,
            bg=COLORS["paper"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            font=("Segoe UI Semibold", 20),
        )
        self.title_entry.pack(fill="x", padx=22, pady=(10, 6))
        self.title_entry.bind("<Return>", self._title_to_body)
        self.title_entry.bind("<<Paste>>", self._on_title_paste)
        self.title_entry.bind("<Control-v>", self._on_title_paste)
        self.title_entry.bind("<Control-V>", self._on_title_paste)

        self.editor_line = tk.Frame(self.editor, bg=COLORS["line"], height=1)
        self.editor_line.pack(fill="x", padx=22, pady=(0, 8))

        self.body = tk.Text(
            self.editor,
            bg=COLORS["paper"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            wrap="word",
            font=("Segoe UI", 12),
            padx=4,
            pady=4,
            spacing1=3,
            spacing3=6,
            bd=0,
            highlightthickness=0,
        )
        self.body.pack(fill="both", expand=True, padx=22, pady=(0, 18))
        self.body.bind("<KeyRelease>", lambda _event: self.schedule_save())

        self.empty_hint = tk.Label(
            self.editor,
            text="Select a note on the left, or click New to start.",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Segoe UI", 11),
        )

        self.lock_frame = tk.Frame(self.editor, bg=COLORS["paper"])

    def _set_placeholder(self, entry, variable, placeholder):
        def on_focus_in(_event):
            if entry.get() == placeholder:
                variable.set("")
                entry.config(fg=COLORS["text"])

        def on_focus_out(_event):
            if not entry.get().strip():
                variable.set(placeholder)
                entry.config(fg=COLORS["muted"])

        variable.set(placeholder)
        entry.config(fg=COLORS["muted"])
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def _search_query(self):
        value = self.search_var.get().strip()
        if value == SEARCH_PLACEHOLDER:
            return ""
        return value

    def _on_list_configure(self, _event):
        self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all"))
        self.list_canvas.xview_moveto(0)

    def _on_canvas_configure(self, event):
        self.list_canvas.itemconfig(self.list_window, width=max(1, event.width))
        self.list_canvas.xview_moveto(0)

    def _list_wrap(self):
        width = self.list_canvas.winfo_width()
        if width < 50:
            width = 220
        return max(80, width - 36)

    def _title_to_body(self, _event=None):
        self.body.focus_set()
        return "break"

    def _on_title_paste(self, _event=None):
        try:
            raw = self.root.clipboard_get()
        except tk.TclError:
            return None
        text = raw.replace("\r\n", "\n").replace("\r", "\n")
        if "\n" not in text:
            return None
        title, content = split_title_body(text, self.body.get("1.0", "end-1c"))
        self._loading = True
        self.title_var.set(title)
        if content.strip() and not self.body.get("1.0", "end-1c").strip():
            self.body.delete("1.0", "end")
            self.body.insert("1.0", content)
        elif content.strip() and content != self.body.get("1.0", "end-1c"):
            self.body.delete("1.0", "end")
            self.body.insert("1.0", content)
        self._loading = False
        self.schedule_save()
        self.body.focus_set()
        return "break"

    def _on_mousewheel(self, event):
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if widget is None:
            return
        if str(widget).startswith(str(self.list_canvas)) or str(widget).startswith(str(self.list_frame)):
            self.list_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _bind_shortcuts(self):
        self.root.bind("<Control-n>", lambda _event: self.create_note())
        self.root.bind("<Control-N>", lambda _event: self.create_note())
        self.root.bind("<Control-f>", lambda _event: self.focus_search())
        self.root.bind("<Control-F>", lambda _event: self.focus_search())
        self.root.bind("<Control-s>", lambda _event: self.save_now())
        self.root.bind("<Control-S>", lambda _event: self.save_now())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def focus_search(self):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")

    def private_locked(self):
        return self.section == "private" and not self.vault.unlocked

    def visible_notes(self):
        if self.private_locked():
            return []
        return self.store.search(self._search_query(), category=self.section)

    def _update_tabs(self):
        for key, button in self.tab_buttons.items():
            if key == self.section:
                button.config(bg=COLORS["accent"], fg="#FFFFFF", activebackground=COLORS["accent_hover"], activeforeground="#FFFFFF")
            else:
                button.config(bg=COLORS["sidebar_hover"], fg=COLORS["text"], activebackground=COLORS["sidebar_active"], activeforeground=COLORS["text"])
        if self.section == "private" and self.vault.unlocked:
            self.lock_btn.pack(side="right", padx=(0, 8))
        else:
            self.lock_btn.pack_forget()

    def set_section(self, section):
        if self.selected_id:
            self.save_now()
        self.section = section
        self._update_tabs()
        if self.private_locked():
            self.selected_id = None
            self.refresh_list()
            self.show_lock_screen()
            return
        self.hide_lock_screen()
        notes = self.visible_notes()
        self.refresh_list()
        if notes:
            self.select_note(notes[0]["id"])
        else:
            self.show_empty_editor()

    def lock_private(self):
        self.save_now()
        self.vault.lock()
        if self.section == "private":
            self.set_section("private")
        else:
            self._update_tabs()

    def show_lock_screen(self):
        self._lock_visible = True
        self._hide_note_widgets()
        self.empty_hint.pack_forget()
        for child in self.lock_frame.winfo_children():
            child.destroy()
        self.lock_frame.pack(fill="both", expand=True, padx=48, pady=48)

        creating = not self.vault.has_password()
        heading = "Create a Private password" if creating else "Private notes are locked"
        detail = (
            "Choose a password to protect Private notes. You will need it each time you open this section."
            if creating
            else "Enter your password to view and edit Private notes."
        )
        tk.Label(self.lock_frame, text=heading, bg=COLORS["paper"], fg=COLORS["text"], font=("Segoe UI Semibold", 16), wraplength=420, justify="left").pack(anchor="w")
        tk.Label(self.lock_frame, text=detail, bg=COLORS["paper"], fg=COLORS["muted"], font=("Segoe UI", 10), wraplength=420, justify="left").pack(anchor="w", pady=(8, 18))

        self.lock_password = tk.Entry(self.lock_frame, show="•", font=("Segoe UI", 12), relief="flat", bg=COLORS["search"], fg=COLORS["text"], insertbackground=COLORS["text"])
        self.lock_password.pack(fill="x", ipady=8)
        self.lock_password.bind("<Return>", lambda _event: self.submit_lock_form())

        self.lock_confirm = None
        if creating:
            tk.Label(self.lock_frame, text="Confirm password", bg=COLORS["paper"], fg=COLORS["muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(12, 4))
            self.lock_confirm = tk.Entry(self.lock_frame, show="•", font=("Segoe UI", 12), relief="flat", bg=COLORS["search"], fg=COLORS["text"], insertbackground=COLORS["text"])
            self.lock_confirm.pack(fill="x", ipady=8)
            self.lock_confirm.bind("<Return>", lambda _event: self.submit_lock_form())

        self.lock_error = tk.Label(self.lock_frame, text="", bg=COLORS["paper"], fg=COLORS["danger"], font=("Segoe UI", 9))
        self.lock_error.pack(anchor="w", pady=(10, 0))

        action = "Set password" if creating else "Unlock"
        tk.Button(
            self.lock_frame,
            text=action,
            command=self.submit_lock_form,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
            bd=0,
        ).pack(anchor="w", pady=(16, 0))
        self.lock_password.focus_set()

    def hide_lock_screen(self):
        self._lock_visible = False
        self.lock_frame.pack_forget()

    def submit_lock_form(self):
        password = self.lock_password.get() if hasattr(self, "lock_password") else ""
        if not self.vault.has_password():
            confirm = self.lock_confirm.get() if self.lock_confirm is not None else ""
            if len(password) < 4:
                self.lock_error.config(text="Use at least 4 characters.")
                return
            if password != confirm:
                self.lock_error.config(text="Passwords do not match.")
                return
            self.vault.set_password(password)
        elif not self.vault.verify(password):
            self.lock_error.config(text="Wrong password.")
            return
        self.hide_lock_screen()
        self._update_tabs()
        notes = self.visible_notes()
        self.refresh_list()
        if notes:
            self.select_note(notes[0]["id"])
        else:
            self.show_empty_editor()

    def _ensure_private_access(self):
        if self.vault.unlocked:
            return True
        return self._password_dialog(create=not self.vault.has_password())

    def _password_dialog(self, create=False):
        dialog = tk.Toplevel(self.root)
        dialog.title("Private notes")
        dialog.configure(bg=COLORS["paper"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        result = {"ok": False}

        tk.Label(
            dialog,
            text="Create a Private password" if create else "Enter Private password",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w", padx=20, pady=(18, 8))

        first = tk.Entry(dialog, show="•", font=("Segoe UI", 11), relief="flat", bg=COLORS["search"], width=28)
        first.pack(fill="x", padx=20, ipady=6)
        second = None
        if create:
            tk.Label(dialog, text="Confirm password", bg=COLORS["paper"], fg=COLORS["muted"], font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(10, 4))
            second = tk.Entry(dialog, show="•", font=("Segoe UI", 11), relief="flat", bg=COLORS["search"], width=28)
            second.pack(fill="x", padx=20, ipady=6)
        error = tk.Label(dialog, text="", bg=COLORS["paper"], fg=COLORS["danger"], font=("Segoe UI", 9))
        error.pack(anchor="w", padx=20, pady=(8, 0))

        def submit(_event=None):
            password = first.get()
            if create:
                if len(password) < 4:
                    error.config(text="Use at least 4 characters.")
                    return
                if password != second.get():
                    error.config(text="Passwords do not match.")
                    return
                self.vault.set_password(password)
            elif not self.vault.verify(password):
                error.config(text="Wrong password.")
                return
            result["ok"] = True
            dialog.destroy()

        tk.Button(
            dialog,
            text="Set password" if create else "Unlock",
            command=submit,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 9),
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
        ).pack(pady=(14, 18))
        first.bind("<Return>", submit)
        if second is not None:
            second.bind("<Return>", submit)
        first.focus_set()
        dialog.wait_window()
        return result["ok"]

    def on_category_change(self, selected_label):
        if self._loading or not self.selected_id:
            return
        target = CATEGORY_KEYS.get(selected_label, "public")
        note = self.store.get(self.selected_id)
        current = note_category(note)
        if target == current:
            return
        if target == "private" and not self._ensure_private_access():
            self._loading = True
            self.category_var.set(CATEGORY_NAMES.get(current, "Public"))
            self._loading = False
            return
        self.save_now()
        self.store.set_category(self.selected_id, target)
        note_id = self.selected_id
        self.set_section(target)
        if self.store.get(note_id):
            self.select_note(note_id)

    def refresh_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.note_buttons = {}

        if self.private_locked():
            empty = tk.Label(
                self.list_frame,
                text="Unlock Private to see these notes.",
                bg=COLORS["sidebar"],
                fg=COLORS["muted"],
                font=("Segoe UI", 10),
                wraplength=240,
                justify="left",
                pady=18,
            )
            empty.pack(fill="x", padx=10)
            return

        notes = self.visible_notes()
        if not notes:
            empty_text = "No notes found" if self._search_query() else f"No {CATEGORY_NAMES[self.section].lower()} notes yet"
            empty = tk.Label(
                self.list_frame,
                text=empty_text,
                bg=COLORS["sidebar"],
                fg=COLORS["muted"],
                font=("Segoe UI", 10),
                pady=18,
            )
            empty.pack(fill="x")
            return

        for note in notes:
            self._add_note_row(note)

    def _add_note_row(self, note):
        note_id = note["id"]
        active = note_id == self.selected_id
        bg = COLORS["sidebar_active"] if active else COLORS["sidebar"]

        row = tk.Frame(self.list_frame, bg=bg, cursor="hand2")
        row.pack(fill="x", padx=8, pady=3)

        wrap = self._list_wrap()
        title = tk.Label(
            row,
            text=preview_text(note),
            bg=bg,
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 10),
            anchor="w",
            justify="left",
            wraplength=wrap,
        )
        title.pack(fill="x", padx=10, pady=(8, 0))

        snippet = one_line(note.get("content") or "", 42)
        title_text = one_line(note.get("title") or "")
        snippet_label = None
        if snippet and title_text and snippet != title_text:
            snippet_label = tk.Label(
                row,
                text=snippet,
                bg=bg,
                fg=COLORS["muted"],
                font=("Segoe UI", 8),
                anchor="w",
                justify="left",
                wraplength=wrap,
            )
            snippet_label.pack(fill="x", padx=10)

        when = tk.Label(
            row,
            text=format_when(note.get("updated_at")),
            bg=bg,
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
            anchor="w",
        )
        when.pack(fill="x", padx=10, pady=(2, 8))

        widgets = [row, title, when]
        if snippet_label is not None:
            widgets.append(snippet_label)

        def select(_event=None, target=note_id):
            self.select_note(target)

        def hover_in(_event, target=row, labels=widgets[1:]):
            if note_id != self.selected_id:
                target.configure(bg=COLORS["sidebar_hover"])
                for label in labels:
                    label.configure(bg=COLORS["sidebar_hover"])

        def hover_out(_event, target=row, labels=widgets[1:]):
            if note_id != self.selected_id:
                target.configure(bg=COLORS["sidebar"])
                for label in labels:
                    label.configure(bg=COLORS["sidebar"])

        for widget in widgets:
            widget.bind("<Button-1>", select)
            widget.bind("<Enter>", hover_in)
            widget.bind("<Leave>", hover_out)

        self.note_buttons[note_id] = row

    def _hide_note_widgets(self):
        self.title_entry.pack_forget()
        self.editor_line.pack_forget()
        self.body.pack_forget()
        self.delete_btn.pack_forget()
        self.category_menu.pack_forget()
        self.top.pack_forget()

    def show_empty_editor(self):
        self.selected_id = None
        self._loading = True
        self.hide_lock_screen()
        self.title_var.set("")
        self.body.delete("1.0", "end")
        self.meta_label.config(text="")
        self._hide_note_widgets()
        self.empty_hint.pack(expand=True)
        self._loading = False

    def show_editor(self):
        self.hide_lock_screen()
        self.empty_hint.pack_forget()
        self.top.pack(fill="x", padx=22, pady=(16, 0))
        self.delete_btn.pack(side="right")
        self.category_menu.pack(side="right", padx=(0, 10))
        self.title_entry.pack(fill="x", padx=22, pady=(10, 6))
        self.editor_line.pack(fill="x", padx=22, pady=(0, 8))
        self.body.pack(fill="both", expand=True, padx=22, pady=(0, 18))

    def select_note(self, note_id):
        if self.private_locked():
            return
        if self.selected_id and self.selected_id != note_id:
            self.save_now()

        note = self.store.get(note_id)
        if note is None:
            return
        if note_category(note) == "private" and not self.vault.unlocked:
            self.set_section("private")
            return

        self.selected_id = note_id
        self._loading = True
        self.show_editor()
        self.title_var.set(note.get("title", ""))
        self.body.delete("1.0", "end")
        self.body.insert("1.0", note.get("content", ""))
        self.category_var.set(CATEGORY_NAMES.get(note_category(note), "Public"))
        created = format_when(note.get("created_at"))
        updated = format_when(note.get("updated_at"))
        self.meta_label.config(text=f"Created {created}  ·  Updated {updated}")
        self._loading = False
        self.refresh_list()
        if (note.get("title") or "") in ("", "New note") and not (note.get("content") or "").strip():
            self.title_entry.focus_set()
            self.title_entry.select_range(0, "end")
        else:
            self.body.focus_set()

    def create_note(self):
        if self.private_locked():
            self.lock_password.focus_set()
            return
        if self.section == "private" and not self._ensure_private_access():
            return
        self.save_now()
        note = self.store.create(category=self.section)
        if self._search_query():
            self.search_var.set("")
            self.search_entry.config(fg=COLORS["text"])
        self.select_note(note["id"])

    def delete_note(self):
        if not self.selected_id:
            return
        note = self.store.get(self.selected_id)
        label = preview_text(note) if note else "this note"
        if not messagebox.askyesno("Delete note", f'Delete "{label}"?'):
            return
        self.store.delete(self.selected_id)
        self.selected_id = None
        remaining = self.visible_notes()
        self.refresh_list()
        if remaining:
            self.select_note(remaining[0]["id"])
        else:
            self.show_empty_editor()

    def schedule_save(self):
        if self._loading or not self.selected_id:
            return
        if self.save_job is not None:
            self.root.after_cancel(self.save_job)
        self.save_job = self.root.after(400, self.save_now)

    def save_now(self):
        if self.save_job is not None:
            self.root.after_cancel(self.save_job)
            self.save_job = None
        if self._loading or not self.selected_id:
            return
        before = preview_text(self.store.get(self.selected_id) or {})
        title = self.title_var.get()
        content = self.body.get("1.0", "end-1c")
        self.store.update(self.selected_id, title, content)
        note = self.store.get(self.selected_id)
        if note:
            self.meta_label.config(
                text=f"Created {format_when(note.get('created_at'))}  ·  Updated {format_when(note.get('updated_at'))}"
            )
            if title != note.get("title", ""):
                self._loading = True
                self.title_var.set(note.get("title", ""))
                self.body.delete("1.0", "end")
                self.body.insert("1.0", note.get("content", ""))
                self._loading = False
        after = preview_text(note or {})
        if before != after:
            self.refresh_list()

    def on_close(self):
        self.save_now()
        self.vault.lock()
        self.root.destroy()

    def _start_silent_update_check(self):
        threading.Thread(target=self._silent_update_check, daemon=True).start()

    def _silent_update_check(self):
        try:
            release = fetch_latest_release()
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return
        if release and is_newer(release.version) and release.download_url:
            self.root.after(0, lambda: self._offer_update(release, silent=True))

    def check_for_updates(self, manual=False):
        self.update_label.config(text="Checking for updates...")
        threading.Thread(target=lambda: self._run_update_check(manual), daemon=True).start()

    def _run_update_check(self, manual):
        try:
            release = fetch_latest_release()
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            if manual:
                self.root.after(0, lambda: self._update_check_failed("Could not reach GitHub. Check your internet connection."))
            else:
                self.root.after(0, self._restore_update_label)
            return
        self.root.after(0, lambda: self._handle_update_result(release, manual))

    def _restore_update_label(self):
        self.update_label.config(text=f"v{APP_VERSION}  ·  Check for updates")

    def _update_check_failed(self, message):
        self._restore_update_label()
        messagebox.showinfo("Updates", message)

    def _handle_update_result(self, release, manual):
        self._restore_update_label()
        if release is None:
            if manual:
                messagebox.showinfo(
                    "Updates",
                    "No GitHub release was found yet.\n\n"
                    "Publish a release at:\n"
                    f"{GITHUB_RELEASES_URL}\n\n"
                    "The repository must be public for updates to work.",
                )
            return
        if is_newer(release.version) and release.download_url:
            self._offer_update(release, silent=not manual)
            return
        if manual:
            if is_newer(release.version) and not release.download_url:
                if messagebox.askyesno(
                    "Update available",
                    f"Version {release.version} is available, but {SETUP_ASSET_NAME} was not attached.\n\nOpen the release page?",
                ):
                    webbrowser.open(release.page_url or GITHUB_RELEASES_URL)
            else:
                messagebox.showinfo("Updates", f"MyNotes is up to date.\nCurrent version: {APP_VERSION}")

    def _offer_update(self, release, silent=False):
        notes = f"\n\n{release.notes[:400]}" if release.notes else ""
        if not messagebox.askyesno(
            "Update available",
            f"MyNotes {release.version} is available.\nYou have {APP_VERSION}.{notes}\n\nDownload and install now?",
        ):
            return
        self._install_update(release)

    def _install_update(self, release):
        self.update_label.config(text="Downloading update...")
        threading.Thread(target=lambda: self._download_and_run(release), daemon=True).start()

    def _download_and_run(self, release):
        try:
            destination = os.path.join(tempfile.gettempdir(), SETUP_ASSET_NAME)
            download_installer(release.download_url, destination)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            self.root.after(0, lambda: self._update_check_failed("The update could not be downloaded."))
            return
        self.root.after(0, lambda: self._launch_installer(destination))

    def _launch_installer(self, setup_path):
        self.save_now()
        try:
            subprocess.Popen([setup_path], close_fds=True)
        except OSError:
            self._restore_update_label()
            messagebox.showerror("Updates", "Could not start the installer.")
            return
        self.root.destroy()


def run():
    root = tk.Tk()
    NotesApp(root)
    root.mainloop()
