"""Editor features for MyNotes: rich text, lists, links, find, pin/tags/trash, backup, themes."""
import json
import os
import re
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import filedialog, messagebox
from tkinter import font as tkfont

from storage import fold
from theme import COLORS, THEMES

BULLET = "\u2022"
BOX_OPEN = "\u2610"
BOX_DONE = "\u2611"
LIST_RE = re.compile("^(\u2022|\u2610|\u2611|\\d+\\.) ")
LINK_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)

TEXT_COLORS = (
    ("Red", "#D32F2F"),
    ("Orange", "#E67E00"),
    ("Green", "#2E9E4F"),
    ("Blue", "#2F80ED"),
    ("Purple", "#9B51E0"),
    ("Gray", "#8A857B"),
)
COLOR_TAGS = {"fg_" + name.lower(): value for name, value in TEXT_COLORS}
STYLE_TAGS = ("bold", "italic", "underline")
SAVED_TAGS = STYLE_TAGS + tuple(COLOR_TAGS)


def list_kind(marker):
    if marker == BULLET:
        return "bullet"
    if marker in (BOX_OPEN, BOX_DONE):
        return "check"
    return "number"


class EditorMixin:
    # ------------------------------------------------------------------ setup
    def _init_features(self):
        self.find_bar = None
        self.find_matches = []
        self.find_index = -1
        self.find_len = 0
        self._auto_job = None

    def trash_mode(self):
        var = self.filter_vars.get("trash")
        return bool(var and var.get())

    def _flat_button(self, parent, text, command, font=("Segoe UI", 10), bg=None, fg=None):
        bg = bg or COLORS["paper"]
        fg = fg or COLORS["text"]
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            bd=0,
            padx=8,
            pady=2,
            font=font,
            cursor="hand2",
            takefocus=0,
            highlightthickness=0,
        )
        button.bind("<Enter>", lambda _e: button.configure(bg=COLORS["sidebar_hover"]))
        button.bind("<Leave>", lambda _e: button.configure(bg=bg))
        return button

    def _build_footer_tools(self, sidebar, author=""):
        row = tk.Frame(sidebar, bg=COLORS["sidebar"])
        row.pack(side="bottom", fill="x", padx=10, pady=(2, 8))
        icon_font = ("Segoe UI Symbol", 11)

        def icon(text, command):
            label = tk.Label(row, text=text, bg=COLORS["sidebar"], fg=COLORS["accent"], font=icon_font, cursor="hand2")
            label.pack(side="left", padx=(0, 6))
            label.bind("<Button-1>", command)
            label.bind("<Enter>", lambda _e: label.configure(fg=COLORS["text"]))
            label.bind("<Leave>", lambda _e: label.configure(fg=COLORS["accent"]))
            return label

        self.theme_label = icon("\u263e" if self.theme == "light" else "\u2600", lambda _e: self.toggle_theme())
        self.backup_label = icon("\u21e9", self._show_backup_menu)
        small = ("Segoe UI", 8)
        tk.Label(row, text=f"{author} \u00b7 2026", bg=COLORS["sidebar"], fg=COLORS["muted"], font=small).pack(side="right")
        self.update_label = tk.Label(row, text="", bg=COLORS["sidebar"], fg=COLORS["accent"], font=small, cursor="hand2")
        self.update_label.pack(side="right", padx=(0, 10))
        self.update_label.bind("<Button-1>", lambda _event: self.check_for_updates(manual=True))
        self._restore_update_label()

    def _build_top_buttons(self):
        self.category_menu["menu"].config(
            bg=COLORS["paper"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar_active"],
            activeforeground=COLORS["text"],
        )
        self.pin_btn = self._flat_button(self.top, "\u2606 Pin", self.toggle_pin, ("Segoe UI", 9))
        self.pin_btn.pack(side="right", padx=(0, 6))
        self.restore_btn = self._flat_button(
            self.top, "Restore", self.restore_selected, ("Segoe UI Semibold", 9), fg=COLORS["accent"]
        )

    def _build_tags_row(self):
        self.tags_row = tk.Frame(self.editor, bg=COLORS["paper"])
        tk.Label(self.tags_row, text="Tags", bg=COLORS["paper"], fg=COLORS["muted"], font=("Segoe UI", 9)).pack(side="left")
        self.tags_var = tk.StringVar()
        self.tags_var.trace_add("write", lambda *_: self.schedule_save())
        self.tags_entry = tk.Entry(
            self.tags_row,
            textvariable=self.tags_var,
            bg=COLORS["paper"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 9),
        )
        self.tags_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _build_toolbar(self):
        self.toolbar = tk.Frame(self.editor, bg=COLORS["paper"])
        bar = self.toolbar
        self._flat_button(bar, "B", lambda: self._toggle_style("bold"), ("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 2))
        self._flat_button(bar, "I", lambda: self._toggle_style("italic"), ("Segoe UI", 10, "italic")).pack(side="left", padx=(0, 2))
        self._flat_button(bar, "U", lambda: self._toggle_style("underline"), ("Segoe UI", 10, "underline")).pack(side="left", padx=(0, 2))
        self.color_btn = self._flat_button(bar, "A \u25BE", self._show_color_menu, ("Segoe UI Semibold", 10))
        self.color_btn.pack(side="left", padx=(0, 8))
        self._flat_button(bar, "\u2022", lambda: self._toggle_list("bullet")).pack(side="left", padx=(0, 2))
        self._flat_button(bar, "1.", lambda: self._toggle_list("number")).pack(side="left", padx=(0, 2))
        self._flat_button(bar, "\u2610", lambda: self._toggle_list("check")).pack(side="left", padx=(0, 8))
        self._flat_button(bar, "Clear", self._clear_format, ("Segoe UI", 9)).pack(side="left", padx=(0, 2))
        self._flat_button(bar, "Find", self.open_find, ("Segoe UI", 9)).pack(side="left", padx=(0, 2))
        tk.Label(
            bar,
            text="Ctrl+click opens links",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Segoe UI", 8),
        ).pack(side="right")

    def _setup_body_features(self):
        body = self.body
        base = tkfont.Font(root=self.root, family="Segoe UI", size=12)
        self.f_bold = base.copy()
        self.f_bold.configure(weight="bold")
        self.f_italic = base.copy()
        self.f_italic.configure(slant="italic")
        self.f_bi = base.copy()
        self.f_bi.configure(weight="bold", slant="italic")
        self._base_font = base

        for tag, color in COLOR_TAGS.items():
            body.tag_configure(tag, foreground=color)
        body.tag_configure("bold", font=self.f_bold)
        body.tag_configure("italic", font=self.f_italic)
        body.tag_configure("underline", underline=True)
        body.tag_configure("bi", font=self.f_bi)
        body.tag_configure("done", overstrike=True, foreground=COLORS["muted"])
        body.tag_configure("link", foreground=COLORS["link"], underline=True)
        body.tag_configure("found", background=COLORS["found"])
        body.tag_configure("found_current", background=COLORS["found_current"])
        body.tag_raise("sel")

        body.tag_bind("link", "<Control-Button-1>", self._open_link)
        body.tag_bind("link", "<Enter>", lambda _e: body.config(cursor="hand2"))
        body.tag_bind("link", "<Leave>", lambda _e: body.config(cursor="xterm"))

        body.bind("<Return>", self._on_body_return)
        body.bind("<KP_Enter>", self._on_body_return)
        body.bind("<space>", self._on_body_space)
        body.bind("<BackSpace>", self._on_body_backspace)
        body.bind("<Button-1>", self._on_body_click)
        for key, tag in (("b", "bold"), ("i", "italic"), ("u", "underline")):
            body.bind(f"<Control-{key}>", lambda _e, t=tag: self._toggle_style(t))
            body.bind(f"<Control-{key.upper()}>", lambda _e, t=tag: self._toggle_style(t))
        body.bind("<Control-f>", self._body_find)
        body.bind("<Control-F>", self._body_find)
        body.bind("<KeyRelease>", lambda _e: self._schedule_auto(), add="+")
        for sequence in ("<<Paste>>", "<<Cut>>"):
            body.bind(sequence, lambda _e: self._schedule_auto(), add="+")

    # ------------------------------------------------------- text <-> format
    def _off(self, index):
        return len(self.body.get("1.0", str(index)))

    def _ranges(self, tag):
        raw = self.body.tag_ranges(tag)
        return [(self._off(raw[i]), self._off(raw[i + 1])) for i in range(0, len(raw), 2)]

    def _collect_formats(self):
        size = len(self.body.get("1.0", "end-1c"))
        out = []
        for tag in SAVED_TAGS:
            for start, end in self._ranges(tag):
                start, end = min(start, size), min(end, size)
                if end > start:
                    out.append([tag, start, end])
        out.sort()
        return out

    def _collect_tags(self):
        seen = set()
        tags = []
        for part in re.split(r"[,;\n]+", self.tags_var.get()):
            part = part.strip().lstrip("#").strip()
            key = fold(part)
            if part and key not in seen:
                seen.add(key)
                tags.append(part)
        return tags

    def _load_body(self, note):
        body = self.body
        content = note.get("content", "") or ""
        body.delete("1.0", "end")
        body.insert("1.0", content)
        size = len(content)
        for item in note.get("format") or []:
            try:
                tag, start, end = item
                start, end = int(start), int(end)
            except (TypeError, ValueError):
                continue
            if tag in SAVED_TAGS and 0 <= start < end <= size:
                body.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")
        body.edit_reset()
        self._refresh_auto_tags()

    def _load_note_meta(self, note):
        self.tags_var.set(", ".join(t for t in (note.get("tags") or []) if isinstance(t, str)))
        self._update_pin_button(note)
        if self.trash_mode():
            self.restore_btn.pack(side="right", padx=(0, 6))
        else:
            self.restore_btn.pack_forget()

    def _update_pin_button(self, note):
        self.pin_btn.config(text="\u2605 Pinned" if note.get("pinned") else "\u2606 Pin")

    # --------------------------------------------------------- auto tagging
    def _schedule_auto(self):
        if self._auto_job is not None:
            try:
                self.root.after_cancel(self._auto_job)
            except tk.TclError:
                pass
        self._auto_job = self.root.after(150, self._run_auto)

    def _run_auto(self):
        self._auto_job = None
        try:
            if self.selected_id:
                self._refresh_auto_tags()
        except tk.TclError:
            pass

    def _refresh_auto_tags(self):
        body = self.body
        text = body.get("1.0", "end-1c")
        for tag in ("link", "done", "bi"):
            body.tag_remove(tag, "1.0", "end")
        for match in LINK_RE.finditer(text):
            url = match.group(0).rstrip(".,;:!?)]}'\"")
            if len(url) > 4:
                body.tag_add("link", f"1.0+{match.start()}c", f"1.0+{match.start() + len(url)}c")
        for number, line in enumerate(text.split("\n"), 1):
            if line.startswith(BOX_DONE + " ") and len(line) > 2:
                body.tag_add("done", f"{number}.2", f"{number}.end")
        italics = self._ranges("italic")
        for b_start, b_end in self._ranges("bold"):
            for i_start, i_end in italics:
                start, end = max(b_start, i_start), min(b_end, i_end)
                if end > start:
                    body.tag_add("bi", f"1.0+{start}c", f"1.0+{end}c")
        for tag in ("bi", "done", "link", "found", "found_current"):
            body.tag_raise(tag)
        body.tag_raise("sel")

    def _open_link(self, event):
        body = self.body
        index = body.index(f"@{event.x},{event.y}")
        found = body.tag_prevrange("link", f"{index}+1c")
        if found:
            url = body.get(found[0], found[1]).strip()
            if url.lower().startswith("www."):
                url = "https://" + url
            webbrowser.open(url)
        return "break"

    # ---------------------------------------------------------- formatting
    def _sel_range(self):
        raw = self.body.tag_ranges("sel")
        if not raw:
            return None
        return str(raw[0]), str(raw[1])

    def _covers(self, tag, first, last):
        start, end = self._off(first), self._off(last)
        covered = sum(max(0, min(e, end) - max(s, start)) for s, e in self._ranges(tag))
        return covered >= end - start

    def _after_format(self):
        self._refresh_auto_tags()
        self.schedule_save()

    def _toggle_style(self, tag):
        selection = self._sel_range()
        if selection:
            first, last = selection
            if self._covers(tag, first, last):
                self.body.tag_remove(tag, first, last)
            else:
                self.body.tag_add(tag, first, last)
            self._after_format()
        return "break"

    def _apply_color(self, tag):
        selection = self._sel_range()
        if not selection:
            return
        first, last = selection
        for name in COLOR_TAGS:
            self.body.tag_remove(name, first, last)
        if tag:
            self.body.tag_add(tag, first, last)
        self._after_format()

    def _clear_format(self):
        selection = self._sel_range()
        if not selection:
            return
        for tag in SAVED_TAGS:
            self.body.tag_remove(tag, *selection)
        self._after_format()

    def _show_color_menu(self):
        menu = tk.Menu(self.root, tearoff=0, bg=COLORS["paper"], fg=COLORS["text"], activebackground=COLORS["sidebar_active"], activeforeground=COLORS["text"])
        for name, color in TEXT_COLORS:
            menu.add_command(
                label="\u25CF  " + name,
                foreground=color,
                command=lambda tag="fg_" + name.lower(): self._apply_color(tag),
            )
        menu.add_separator()
        menu.add_command(label="Default color", command=lambda: self._apply_color(None))
        x = self.color_btn.winfo_rootx()
        y = self.color_btn.winfo_rooty() + self.color_btn.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    # --------------------------------------------------------------- lists
    def _toggle_list(self, kind):
        body = self.body
        selection = self._sel_range()
        if selection:
            first = int(body.index(selection[0]).split(".")[0])
            last_index = body.index(selection[1])
            last = int(last_index.split(".")[0])
            if last_index.endswith(".0") and last > first:
                last -= 1
        else:
            first = last = int(body.index("insert").split(".")[0])
        lines = range(first, last + 1)
        targets = []
        for number in lines:
            text = body.get(f"{number}.0", f"{number}.end")
            if text.strip() or len(lines) == 1:
                targets.append((number, text))
        if not targets:
            return
        remove = all(
            (match := LIST_RE.match(text)) and list_kind(match.group(1)) == kind for _n, text in targets
        )
        body.edit_separator()
        counter = 0
        for number, text in targets:
            match = LIST_RE.match(text)
            if match:
                body.delete(f"{number}.0", f"{number}.{len(match.group(0))}")
            if remove:
                continue
            counter += 1
            prefix = {"bullet": BULLET + " ", "check": BOX_OPEN + " ", "number": f"{counter}. "}[kind]
            body.insert(f"{number}.0", prefix)
        body.edit_separator()
        self._after_format()

    def _on_body_return(self, _event=None):
        body = self.body
        if body.tag_ranges("sel"):
            return None
        insert = body.index("insert")
        before = body.get(f"{insert} linestart", insert)
        match = LIST_RE.match(before)
        if not match:
            return None
        marker = match.group(0)
        whole = body.get(f"{insert} linestart", f"{insert} lineend")
        body.edit_separator()
        if before == marker and whole.rstrip() == marker.rstrip():
            body.delete(f"{insert} linestart", f"{insert} lineend")
        else:
            first = marker[0]
            if first.isdigit():
                nxt = f"{int(marker.split('.')[0]) + 1}. "
            elif first in (BOX_OPEN, BOX_DONE):
                nxt = BOX_OPEN + " "
            else:
                nxt = BULLET + " "
            body.insert("insert", "\n" + nxt)
            body.see("insert")
        body.edit_separator()
        self._after_format()
        return "break"

    def _on_body_space(self, _event=None):
        body = self.body
        if body.tag_ranges("sel"):
            return None
        insert = body.index("insert")
        before = body.get(f"{insert} linestart", insert)
        replacement = {"-": BULLET + " ", "*": BULLET + " ", "[]": BOX_OPEN + " ", "[ ]": BOX_OPEN + " "}.get(before)
        if replacement is None:
            return None
        body.edit_separator()
        body.delete(f"{insert} linestart", insert)
        body.insert("insert", replacement)
        body.edit_separator()
        self._after_format()
        return "break"

    def _on_body_backspace(self, _event=None):
        body = self.body
        if body.tag_ranges("sel"):
            return None
        insert = body.index("insert")
        before = body.get(f"{insert} linestart", insert)
        match = LIST_RE.match(before)
        if match and before == match.group(0):
            body.edit_separator()
            body.delete(f"{insert} linestart", insert)
            body.edit_separator()
            self._after_format()
            return "break"
        return None

    def _on_body_click(self, event):
        body = self.body
        index = body.index(f"@{event.x},{event.y}")
        char = body.get(index)
        if char in (BOX_OPEN, BOX_DONE):
            box = body.bbox(index)
            if box and box[0] <= event.x <= box[0] + box[2]:
                body.focus_set()
                body.edit_separator()
                body.delete(index, f"{index}+1c")
                body.insert(index, BOX_DONE if char == BOX_OPEN else BOX_OPEN)
                body.edit_separator()
                self._after_format()
                return "break"
        return None

    # ---------------------------------------------------------------- find
    def _body_find(self, _event=None):
        self.open_find()
        return "break"

    def _build_find_bar(self):
        bar = tk.Frame(self.editor, bg=COLORS["sidebar"])
        self.find_var = tk.StringVar()
        entry = tk.Entry(
            bar,
            textvariable=self.find_var,
            bg=COLORS["search"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10),
        )
        entry.pack(side="left", fill="x", expand=True, padx=(8, 6), pady=5)
        self.find_entry = entry
        self.find_count = tk.Label(bar, text="", bg=COLORS["sidebar"], fg=COLORS["muted"], font=("Segoe UI", 9), width=8)
        self.find_count.pack(side="left")
        self._flat_button(bar, "\u2191", lambda: self._find_step(-1), bg=COLORS["sidebar"]).pack(side="left")
        self._flat_button(bar, "\u2193", lambda: self._find_step(1), bg=COLORS["sidebar"]).pack(side="left")
        self._flat_button(bar, "\u2715", self._close_find, bg=COLORS["sidebar"]).pack(side="left", padx=(0, 4))
        entry.bind("<Return>", lambda _e: self._find_step(1))
        entry.bind("<Shift-Return>", lambda _e: self._find_step(-1))
        entry.bind("<Escape>", lambda _e: self._close_find())
        self.find_var.trace_add("write", lambda *_: self._find_update())
        self.find_bar = bar

    def open_find(self):
        if not self.selected_id:
            return
        if self.find_bar is None or not self.find_bar.winfo_exists():
            self._build_find_bar()
        self.find_bar.pack(fill="x", padx=22, pady=(0, 6), before=self.body_wrap)
        selection = self._sel_range()
        if selection:
            picked = self.body.get(*selection)
            if picked and "\n" not in picked:
                self.find_var.set(picked)
        self.find_entry.focus_set()
        self.find_entry.select_range(0, "end")
        self._find_update()

    def _close_find(self, focus=True):
        bar = self.find_bar
        if bar is None:
            return
        try:
            self.body.tag_remove("found", "1.0", "end")
            self.body.tag_remove("found_current", "1.0", "end")
            bar.pack_forget()
            if focus:
                self.body.focus_set()
        except tk.TclError:
            pass

    def _find_update(self):
        body = self.body
        body.tag_remove("found", "1.0", "end")
        body.tag_remove("found_current", "1.0", "end")
        query = fold(self.find_var.get())
        self.find_matches = []
        self.find_len = len(query)
        if query:
            hay = fold(body.get("1.0", "end-1c"))
            pos = 0
            while len(self.find_matches) < 2000:
                at = hay.find(query, pos)
                if at < 0:
                    break
                self.find_matches.append(at)
                pos = at + max(1, len(query))
            for at in self.find_matches:
                body.tag_add("found", f"1.0+{at}c", f"1.0+{at + len(query)}c")
        self.find_index = -1
        if self.find_matches:
            here = self._off("insert")
            self.find_index = next((i for i, at in enumerate(self.find_matches) if at >= here), 0)
        self._find_show(query)

    def _find_show(self, query=None):
        body = self.body
        body.tag_remove("found_current", "1.0", "end")
        total = len(self.find_matches)
        if self.find_index >= 0 and total:
            at = self.find_matches[self.find_index]
            body.tag_add("found_current", f"1.0+{at}c", f"1.0+{at + self.find_len}c")
            body.tag_raise("found_current")
            body.tag_raise("sel")
            body.see(f"1.0+{at}c")
            self.find_count.config(text=f"{self.find_index + 1}/{total}")
        else:
            self.find_count.config(text="0" if (query if query is not None else self.find_var.get()) else "")

    def _find_step(self, delta):
        if not self.find_matches:
            return "break"
        self.find_index = (self.find_index + delta) % len(self.find_matches)
        self._find_show()
        return "break"

    # ----------------------------------------------------- pin / tags / trash
    def toggle_pin(self):
        note = self.store.get(self.selected_id) if self.selected_id else None
        if note is None:
            return
        if note.get("pinned"):
            note.pop("pinned", None)
        else:
            note["pinned"] = True
        self.store.save()
        self._update_pin_button(note)
        self.refresh_list()

    def restore_selected(self):
        if not self.selected_id:
            return
        self.save_now()
        self.store.restore(self.selected_id)
        self.selected_id = None
        self.apply_filters()

    def _trash_notes(self):
        cats = ["public", "hidden"] + (["private"] if self.vault.unlocked else [])
        return self.store.search(self._search_query(), categories=cats, trashed=True)

    # -------------------------------------------------------- backup / theme
    def _show_backup_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0, bg=COLORS["paper"], fg=COLORS["text"], activebackground=COLORS["sidebar_active"], activeforeground=COLORS["text"])
        menu.add_command(label="Export notes...", command=self.export_notes)
        menu.add_command(label="Import notes...", command=self.import_notes)
        menu.add_command(label="Open backups folder", command=self.open_backups)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def export_notes(self):
        self.save_now()
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export notes",
            defaultextension=".json",
            initialfile=f"MyNotes-export-{datetime.now():%Y%m%d}.json",
            filetypes=[("JSON file", "*.json")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(self.store.notes, handle, ensure_ascii=False, indent=2)
        except OSError as error:
            messagebox.showerror("Export", f"Could not save the file.\n{error}")
            return
        messagebox.showinfo("Export", f"Exported {len(self.store.notes)} notes.")

    def import_notes(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Import notes",
            filetypes=[("JSON file", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, list):
                raise ValueError("not a notes file")
        except (OSError, ValueError):
            messagebox.showerror("Import", "This file is not a MyNotes export.")
            return
        self.save_now()
        added, updated = self.store.merge(data)
        previous = self.selected_id
        self.selected_id = None
        self.apply_filters()
        if previous and previous in {note["id"] for note in self.visible_notes()}:
            self.select_note(previous)
        messagebox.showinfo("Import", f"Added {added} notes, updated {updated}. Nothing was deleted.")

    def open_backups(self):
        folder = os.path.join(os.path.dirname(self.store.path), "backups")
        os.makedirs(folder, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(folder)

    def toggle_theme(self):
        self.save_now()
        flags = {key: var.get() for key, var in self.filter_vars.items()}
        query = self._search_query()
        selected = self.selected_id
        self.theme = "dark" if self.theme == "light" else "light"
        COLORS.update(THEMES[self.theme])
        self.vault.data["theme"] = self.theme
        try:
            self.vault.save()
        except OSError:
            pass
        for child in self.root.winfo_children():
            child.destroy()
        self.note_buttons = {}
        self.note_painters = {}
        self.filter_vars = {}
        self.find_bar = None
        self.selected_id = None
        self.save_job = None
        self.root.configure(bg=COLORS["bg"])
        self._build_ui()
        for key, value in flags.items():
            if key in self.filter_vars:
                self.filter_vars[key].set(value)
        if query:
            self.search_var.set(query)
            self.search_entry.config(fg=COLORS["text"])
        self.apply_filters()
        if selected and selected in {note["id"] for note in self.visible_notes()}:
            self.select_note(selected)