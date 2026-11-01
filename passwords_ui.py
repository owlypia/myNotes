"""Password manager UI for MyNotes."""
import tkinter as tk
from tkinter import messagebox, font as tkfont

from password_store import PasswordStore, generate_password
from theme import COLORS


class PasswordsUIMixin:
    def _init_passwords(self):
        """Initialize password manager state."""
        self.password_store = PasswordStore()
        self.passwords_mode = False
        self.selected_folder_id = None
        self.selected_entry_id = None
        self._clipboard_clear_job = None
        self._auto_lock_job = None
        self._last_passwords_activity = None

    def _add_passwords_filter(self, filters):
        """Add the Passwords button to the filter row."""
        self.passwords_btn = tk.Button(
            filters,
            text="Passwords",
            command=self.toggle_passwords_mode,
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar"],
            activeforeground=COLORS["text"],
            highlightthickness=0,
            bd=0,
            font=("Segoe UI", 8),
            cursor="hand2",
            padx=4,
        )
        self.passwords_btn.pack(side="left", expand=True)

    def toggle_passwords_mode(self):
        """Toggle between notes and passwords mode."""
        if self.passwords_mode:
            self._exit_passwords_mode()
        else:
            self._enter_passwords_mode()

    def _enter_passwords_mode(self):
        """Enter passwords mode."""
        if not self._ensure_passwords_unlocked():
            return
        
        self.save_now()
        self.passwords_mode = True
        
        for var in self.filter_vars.values():
            var.set(False)
        
        self.passwords_btn.config(
            bg=COLORS["sidebar_active"],
            fg=COLORS["text"],
        )
        
        self.selected_id = None
        self.selected_entry_id = None
        self.selected_folder_id = None
        
        self._refresh_passwords_list()
        self._show_passwords_editor()
        self._schedule_auto_lock()

    def _exit_passwords_mode(self):
        """Exit passwords mode and return to notes."""
        self.passwords_mode = False
        self.password_store.lock()
        
        self.passwords_btn.config(
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
        )
        
        self.filter_vars["public"].set(True)
        self.apply_filters()
        self._cancel_auto_lock()

    def _ensure_passwords_unlocked(self):
        """Ensure the password vault is unlocked, prompting if necessary."""
        if self.password_store.unlocked:
            return True
        
        if not self.password_store.exists():
            return self._create_vault_dialog()
        else:
            return self._unlock_vault_dialog()

    def _create_vault_dialog(self):
        """Show dialog to create a new password vault."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Password Vault")
        dialog.configure(bg=COLORS["paper"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        result = {"ok": False}
        
        tk.Label(
            dialog,
            text="Create Password Vault",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 14),
        ).pack(anchor="w", padx=20, pady=(18, 8))
        
        tk.Label(
            dialog,
            text="Choose a password to protect your passwords.\nThis is separate from your Private notes password.",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))
        
        tk.Label(
            dialog,
            text="Vault Password",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(0, 4))
        
        password_entry = tk.Entry(
            dialog,
            show="•",
            font=("Segoe UI", 11),
            relief="flat",
            bg=COLORS["search"],
            width=35,
        )
        password_entry.pack(fill="x", padx=20, ipady=6)
        
        tk.Label(
            dialog,
            text="Confirm Password",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(10, 4))
        
        confirm_entry = tk.Entry(
            dialog,
            show="•",
            font=("Segoe UI", 11),
            relief="flat",
            bg=COLORS["search"],
            width=35,
        )
        confirm_entry.pack(fill="x", padx=20, ipady=6)
        
        error_label = tk.Label(
            dialog,
            text="",
            bg=COLORS["paper"],
            fg=COLORS["danger"],
            font=("Segoe UI", 9),
        )
        error_label.pack(anchor="w", padx=20, pady=(8, 0))
        
        recovery_key_var = {"key": None}
        
        def submit(_event=None):
            password = password_entry.get()
            confirm = confirm_entry.get()
            
            if len(password) < 8:
                error_label.config(text="Password must be at least 8 characters.")
                return
            
            if password != confirm:
                error_label.config(text="Passwords do not match.")
                return
            
            try:
                recovery_key = self.password_store.create(password)
                recovery_key_var["key"] = recovery_key
                result["ok"] = True
                dialog.destroy()
            except Exception as e:
                error_label.config(text=f"Error: {e}")
        
        button_frame = tk.Frame(dialog, bg=COLORS["paper"])
        button_frame.pack(pady=(14, 18))
        
        tk.Button(
            button_frame,
            text="Create Vault",
            command=submit,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        
        tk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left")
        
        password_entry.bind("<Return>", submit)
        confirm_entry.bind("<Return>", submit)
        password_entry.focus_set()
        
        dialog.wait_window()
        
        if result["ok"] and recovery_key_var["key"]:
            self._show_recovery_key(recovery_key_var["key"])
        
        return result["ok"]

    def _show_recovery_key(self, recovery_key):
        """Show the recovery key to the user once."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Your Recovery Key")
        dialog.configure(bg=COLORS["paper"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        tk.Label(
            dialog,
            text="⚠ Save Your Recovery Key",
            bg=COLORS["paper"],
            fg=COLORS["danger"],
            font=("Segoe UI Semibold", 14),
        ).pack(anchor="w", padx=20, pady=(18, 8))
        
        warning_text = (
            "This recovery key can unlock your password vault if you forget your password.\n\n"
            "Store it in a safe place. You will NOT see it again!\n\n"
            "Without your password OR this recovery key, your passwords are UNRECOVERABLE."
        )
        
        tk.Label(
            dialog,
            text=warning_text,
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))
        
        key_frame = tk.Frame(dialog, bg=COLORS["search"], relief="solid", bd=1)
        key_frame.pack(fill="x", padx=20, pady=(0, 12))
        
        key_text = tk.Text(
            key_frame,
            height=2,
            wrap="word",
            font=("Consolas", 10),
            bg=COLORS["search"],
            fg=COLORS["text"],
            relief="flat",
            padx=8,
            pady=8,
        )
        key_text.pack(fill="x")
        key_text.insert("1.0", recovery_key)
        key_text.config(state="disabled")
        
        def copy_key():
            self.root.clipboard_clear()
            self.root.clipboard_append(recovery_key)
            copy_btn.config(text="Copied!")
            self.root.after(2000, lambda: copy_btn.config(text="Copy to Clipboard"))
        
        button_frame = tk.Frame(dialog, bg=COLORS["paper"])
        button_frame.pack(pady=(0, 18))
        
        copy_btn = tk.Button(
            button_frame,
            text="Copy to Clipboard",
            command=copy_key,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        )
        copy_btn.pack(side="left", padx=(0, 8))
        
        tk.Button(
            button_frame,
            text="I Saved It",
            command=dialog.destroy,
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left")
        
        dialog.wait_window()

    def _unlock_vault_dialog(self):
        """Show dialog to unlock an existing vault."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Unlock Password Vault")
        dialog.configure(bg=COLORS["paper"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        result = {"ok": False}
        
        tk.Label(
            dialog,
            text="Unlock Password Vault",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 14),
        ).pack(anchor="w", padx=20, pady=(18, 8))
        
        tk.Label(
            dialog,
            text="Enter your vault password to access your passwords.",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=20, pady=(0, 12))
        
        tk.Label(
            dialog,
            text="Vault Password",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(0, 4))
        
        password_entry = tk.Entry(
            dialog,
            show="•",
            font=("Segoe UI", 11),
            relief="flat",
            bg=COLORS["search"],
            width=35,
        )
        password_entry.pack(fill="x", padx=20, ipady=6)
        
        error_label = tk.Label(
            dialog,
            text="",
            bg=COLORS["paper"],
            fg=COLORS["danger"],
            font=("Segoe UI", 9),
        )
        error_label.pack(anchor="w", padx=20, pady=(8, 0))
        
        def submit(_event=None):
            password = password_entry.get()
            try:
                self.password_store.unlock(password=password)
                result["ok"] = True
                dialog.destroy()
            except Exception:
                error_label.config(text="Wrong password.")
        
        def show_recovery():
            dialog.destroy()
            result["ok"] = self._recovery_dialog()
        
        button_frame = tk.Frame(dialog, bg=COLORS["paper"])
        button_frame.pack(pady=(14, 8))
        
        tk.Button(
            button_frame,
            text="Unlock",
            command=submit,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        
        tk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left")
        
        tk.Label(
            dialog,
            text="Forgot password? Use recovery key",
            bg=COLORS["paper"],
            fg=COLORS["accent"],
            font=("Segoe UI", 9),
            cursor="hand2",
        ).pack(pady=(0, 18))
        
        dialog.winfo_children()[-1].bind("<Button-1>", lambda _: show_recovery())
        
        password_entry.bind("<Return>", submit)
        password_entry.focus_set()
        
        dialog.wait_window()
        
        return result["ok"]

    def _recovery_dialog(self):
        """Show dialog to unlock with recovery key."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Recovery Key")
        dialog.configure(bg=COLORS["paper"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        result = {"ok": False}
        
        tk.Label(
            dialog,
            text="Use Recovery Key",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 14),
        ).pack(anchor="w", padx=20, pady=(18, 8))
        
        tk.Label(
            dialog,
            text="Enter your recovery key to unlock the vault.\nYou can then set a new password.",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))
        
        tk.Label(
            dialog,
            text="Recovery Key",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(0, 4))
        
        key_entry = tk.Entry(
            dialog,
            font=("Consolas", 10),
            relief="flat",
            bg=COLORS["search"],
            width=40,
        )
        key_entry.pack(fill="x", padx=20, ipady=6)
        
        error_label = tk.Label(
            dialog,
            text="",
            bg=COLORS["paper"],
            fg=COLORS["danger"],
            font=("Segoe UI", 9),
        )
        error_label.pack(anchor="w", padx=20, pady=(8, 0))
        
        def submit(_event=None):
            recovery_key = key_entry.get().strip().replace(" ", "").upper()
            try:
                self.password_store.unlock(recovery_key=recovery_key)
                result["ok"] = True
                dialog.destroy()
                self._change_password_dialog()
            except Exception:
                error_label.config(text="Invalid or wrong recovery key.")
        
        button_frame = tk.Frame(dialog, bg=COLORS["paper"])
        button_frame.pack(pady=(14, 18))
        
        tk.Button(
            button_frame,
            text="Unlock",
            command=submit,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        
        tk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left")
        
        key_entry.bind("<Return>", submit)
        key_entry.focus_set()
        
        dialog.wait_window()
        
        return result["ok"]

    def _change_password_dialog(self):
        """Show dialog to change vault password."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Vault Password")
        dialog.configure(bg=COLORS["paper"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        tk.Label(
            dialog,
            text="Set New Password",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 14),
        ).pack(anchor="w", padx=20, pady=(18, 8))
        
        tk.Label(
            dialog,
            text="Choose a new password for your vault.",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=20, pady=(0, 12))
        
        tk.Label(
            dialog,
            text="New Password",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(0, 4))
        
        password_entry = tk.Entry(
            dialog,
            show="•",
            font=("Segoe UI", 11),
            relief="flat",
            bg=COLORS["search"],
            width=35,
        )
        password_entry.pack(fill="x", padx=20, ipady=6)
        
        tk.Label(
            dialog,
            text="Confirm Password",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(10, 4))
        
        confirm_entry = tk.Entry(
            dialog,
            show="•",
            font=("Segoe UI", 11),
            relief="flat",
            bg=COLORS["search"],
            width=35,
        )
        confirm_entry.pack(fill="x", padx=20, ipady=6)
        
        error_label = tk.Label(
            dialog,
            text="",
            bg=COLORS["paper"],
            fg=COLORS["danger"],
            font=("Segoe UI", 9),
        )
        error_label.pack(anchor="w", padx=20, pady=(8, 0))
        
        def submit(_event=None):
            password = password_entry.get()
            confirm = confirm_entry.get()
            
            if len(password) < 8:
                error_label.config(text="Password must be at least 8 characters.")
                return
            
            if password != confirm:
                error_label.config(text="Passwords do not match.")
                return
            
            try:
                self.password_store.change_password(password)
                messagebox.showinfo("Success", "Password changed successfully.")
                dialog.destroy()
            except Exception as e:
                error_label.config(text=f"Error: {e}")
        
        button_frame = tk.Frame(dialog, bg=COLORS["paper"])
        button_frame.pack(pady=(14, 18))
        
        tk.Button(
            button_frame,
            text="Change Password",
            command=submit,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        
        tk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left")
        
        password_entry.bind("<Return>", submit)
        confirm_entry.bind("<Return>", submit)
        password_entry.focus_set()
        
        dialog.wait_window()

    def _refresh_passwords_list(self):
        """Refresh the sidebar to show folders and entries."""
        self._record_passwords_activity()
        
        for child in self.list_frame.winfo_children():
            child.destroy()
        
        if not self.password_store.unlocked:
            return
        
        search_query = self._search_query().lower()
        
        if search_query:
            entries = self.password_store.search(search_query)
            self._build_entries_list(entries, title="Search Results")
        else:
            folders = self.password_store.get_folders()
            root_folders = [f for f in folders if not f.get("parent_id")]
            
            for folder in root_folders:
                self._build_folder_tree(folder)
            
            root_entries = self.password_store.get_entries(folder_id=None)
            if root_entries:
                self._build_entries_list(root_entries, title="Passwords")

    def _build_folder_tree(self, folder, level=0):
        """Build a folder node in the tree."""
        folder_id = folder["id"]
        
        row = tk.Frame(self.list_frame, bg=COLORS["sidebar"], cursor="hand2")
        row.pack(fill="x", padx=(8 + level * 16, 8), pady=2)
        
        text_frame = tk.Frame(row, bg=COLORS["sidebar"], cursor="hand2")
        text_frame.pack(side="left", fill="x", expand=True)
        
        folder_icon = "\U0001F4C1"
        
        tk.Label(
            text_frame,
            text=f"{folder_icon} {folder['name']}",
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 10),
            anchor="w",
            cursor="hand2",
        ).pack(side="left", padx=(8, 4), pady=6)
        
        def select_folder():
            self.selected_folder_id = folder_id
            self.selected_entry_id = None
            self._show_folder_contents(folder_id)
        
        text_frame.bind("<Button-1>", lambda _: select_folder())
        row.bind("<Button-1>", lambda _: select_folder())
        
        child_folders = [f for f in self.password_store.get_folders() if f.get("parent_id") == folder_id]
        for child in child_folders:
            self._build_folder_tree(child, level + 1)
        
        entries = self.password_store.get_entries(folder_id)
        if entries:
            for entry in entries:
                self._build_entry_row(entry, level + 1)

    def _build_entries_list(self, entries, title=None):
        """Build a list of entries."""
        if title:
            tk.Label(
                self.list_frame,
                text=title,
                bg=COLORS["sidebar"],
                fg=COLORS["muted"],
                font=("Segoe UI Semibold", 9),
                anchor="w",
            ).pack(fill="x", padx=14, pady=(8, 4))
        
        for entry in entries:
            self._build_entry_row(entry, level=0)

    def _build_entry_row(self, entry, level=0):
        """Build an entry row."""
        entry_id = entry["id"]
        active = entry_id == self.selected_entry_id
        bg = COLORS["sidebar_active"] if active else COLORS["sidebar"]
        
        row = tk.Frame(self.list_frame, bg=bg, cursor="hand2")
        row.pack(fill="x", padx=(8 + level * 16, 8), pady=2)
        
        text_col = tk.Frame(row, bg=bg, cursor="hand2")
        text_col.pack(side="left", fill="both", expand=True)
        
        title_text = entry.get("title") or "Untitled"
        username_text = entry.get("username") or ""
        
        title_label = tk.Label(
            text_col,
            text=title_text,
            bg=bg,
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 10),
            anchor="w",
        )
        title_label.pack(fill="x", padx=(10, 4), pady=(6, 0))
        
        if username_text:
            username_label = tk.Label(
                text_col,
                text=username_text,
                bg=bg,
                fg=COLORS["muted"],
                font=("Segoe UI", 8),
                anchor="w",
            )
            username_label.pack(fill="x", padx=(10, 4), pady=(0, 6))
        else:
            title_label.pack_configure(pady=(6, 6))
        
        def select_entry():
            self.selected_entry_id = entry_id
            self.selected_folder_id = entry.get("folder_id")
            self._show_entry_editor(entry)
        
        row.bind("<Button-1>", lambda _: select_entry())
        text_col.bind("<Button-1>", lambda _: select_entry())
        title_label.bind("<Button-1>", lambda _: select_entry())
        if username_text:
            username_label.bind("<Button-1>", lambda _: select_entry())

    def _show_folder_contents(self, folder_id):
        """Show folder contents in the editor area."""
        self._record_passwords_activity()
        
        for child in self.editor.winfo_children():
            child.destroy()
        
        folder = self.password_store.get_folder(folder_id)
        if not folder:
            return
        
        header = tk.Frame(self.editor, bg=COLORS["paper"])
        header.pack(fill="x", padx=22, pady=(16, 12))
        
        tk.Label(
            header,
            text=f"\U0001F4C1 {folder['name']}",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 16),
        ).pack(side="left")
        
        tk.Button(
            header,
            text="New Entry",
            command=lambda: self._new_entry_dialog(folder_id),
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 9),
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
        ).pack(side="right")
        
        entries = self.password_store.get_entries(folder_id)
        
        if entries:
            tk.Label(
                self.editor,
                text=f"{len(entries)} password(s) in this folder",
                bg=COLORS["paper"],
                fg=COLORS["muted"],
                font=("Segoe UI", 10),
            ).pack(padx=22, pady=12)
        else:
            tk.Label(
                self.editor,
                text="This folder is empty. Click 'New Entry' to add a password.",
                bg=COLORS["paper"],
                fg=COLORS["muted"],
                font=("Segoe UI", 10),
            ).pack(padx=22, pady=40)

    def _show_passwords_editor(self):
        """Show the main passwords view."""
        self._record_passwords_activity()
        
        for child in self.editor.winfo_children():
            child.destroy()
        
        header = tk.Frame(self.editor, bg=COLORS["paper"])
        header.pack(fill="x", padx=22, pady=(16, 12))
        
        tk.Label(
            header,
            text="Password Manager",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 18),
        ).pack(side="left")
        
        tk.Button(
            header,
            text="Lock",
            command=self._lock_passwords,
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            font=("Segoe UI Semibold", 9),
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
        ).pack(side="right", padx=(8, 0))
        
        tk.Button(
            header,
            text="New Entry",
            command=lambda: self._new_entry_dialog(None),
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 9),
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
        ).pack(side="right")
        
        content = tk.Frame(self.editor, bg=COLORS["paper"])
        content.pack(fill="both", expand=True, padx=22, pady=(0, 18))
        
        tk.Label(
            content,
            text="Select a folder or entry from the left sidebar,\nor create a new password entry.",
            bg=COLORS["paper"],
            fg=COLORS["muted"],
            font=("Segoe UI", 11),
            justify="center",
        ).pack(expand=True)

    def _show_entry_editor(self, entry):
        """Show the entry editor."""
        self._record_passwords_activity()
        
        for child in self.editor.winfo_children():
            child.destroy()
        
        scrollable_frame = tk.Frame(self.editor, bg=COLORS["paper"])
        scrollbar = tk.Scrollbar(scrollable_frame, orient="vertical")
        canvas = tk.Canvas(
            scrollable_frame,
            bg=COLORS["paper"],
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=canvas.yview)
        
        inner_frame = tk.Frame(canvas, bg=COLORS["paper"])
        canvas_window = canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        
        def configure_scroll(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        
        inner_frame.bind("<Configure>", configure_scroll)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        scrollable_frame.pack(fill="both", expand=True)
        
        header = tk.Frame(inner_frame, bg=COLORS["paper"])
        header.pack(fill="x", padx=22, pady=(16, 12))
        
        tk.Label(
            header,
            text="Password Entry",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 16),
        ).pack(side="left")
        
        def delete_entry():
            if messagebox.askyesno("Delete", f"Delete password '{entry.get('title', 'Untitled')}'?"):
                self.password_store.delete_entry(entry["id"])
                self.selected_entry_id = None
                self._refresh_passwords_list()
                self._show_passwords_editor()
        
        tk.Button(
            header,
            text="Delete",
            command=delete_entry,
            bg=COLORS["danger"],
            fg="#FFFFFF",
            activebackground=COLORS["danger_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 9),
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
        ).pack(side="right")
        
        form = tk.Frame(inner_frame, bg=COLORS["paper"])
        form.pack(fill="x", padx=22, pady=(0, 18))
        
        fields = {}
        
        def add_field(label, key, show_copy=False, is_password=False):
            tk.Label(
                form,
                text=label,
                bg=COLORS["paper"],
                fg=COLORS["text"],
                font=("Segoe UI Semibold", 10),
            ).pack(anchor="w", pady=(12, 4))
            
            row = tk.Frame(form, bg=COLORS["paper"])
            row.pack(fill="x", pady=(0, 0))
            
            entry_widget = tk.Entry(
                row,
                font=("Segoe UI", 11),
                relief="flat",
                bg=COLORS["search"],
                fg=COLORS["text"],
                insertbackground=COLORS["text"],
                show="•" if is_password else "",
            )
            entry_widget.pack(side="left", fill="x", expand=True, ipady=6)
            entry_widget.insert(0, entry.get(key, ""))
            
            fields[key] = {"widget": entry_widget, "is_password": is_password}
            
            if is_password:
                def toggle_visibility():
                    current = entry_widget.cget("show")
                    if current:
                        entry_widget.config(show="")
                        show_btn.config(text="Hide")
                    else:
                        entry_widget.config(show="•")
                        show_btn.config(text="Show")
                
                show_btn = tk.Button(
                    row,
                    text="Show",
                    command=toggle_visibility,
                    bg=COLORS["sidebar"],
                    fg=COLORS["text"],
                    activebackground=COLORS["sidebar_hover"],
                    activeforeground=COLORS["text"],
                    relief="flat",
                    font=("Segoe UI", 9),
                    padx=8,
                    pady=6,
                    bd=0,
                    cursor="hand2",
                )
                show_btn.pack(side="left", padx=(4, 0))
            
            if show_copy:
                def copy_value(value_key=key):
                    value = fields[value_key]["widget"].get()
                    if value:
                        self.root.clipboard_clear()
                        self.root.clipboard_append(value)
                        if value_key == "password":
                            self._schedule_clipboard_clear(value)
                
                tk.Button(
                    row,
                    text="Copy",
                    command=copy_value,
                    bg=COLORS["accent"],
                    fg="#FFFFFF",
                    activebackground=COLORS["accent_hover"],
                    activeforeground="#FFFFFF",
                    relief="flat",
                    font=("Segoe UI", 9),
                    padx=8,
                    pady=6,
                    bd=0,
                    cursor="hand2",
                ).pack(side="left", padx=(4, 0))
        
        add_field("Title", "title")
        add_field("Username", "username", show_copy=True)
        add_field("Password", "password", show_copy=True, is_password=True)
        
        password_row = tk.Frame(form, bg=COLORS["paper"])
        password_row.pack(fill="x", pady=(4, 0))
        
        tk.Button(
            password_row,
            text="Generate Password",
            command=lambda: self._show_password_generator(fields["password"]["widget"]),
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            bd=0,
            cursor="hand2",
        ).pack(side="left")
        
        add_field("URL", "url")
        
        tk.Label(
            form,
            text="Notes",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w", pady=(12, 4))
        
        notes_widget = tk.Text(
            form,
            font=("Segoe UI", 11),
            relief="flat",
            bg=COLORS["search"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            height=4,
            wrap="word",
        )
        notes_widget.pack(fill="x", pady=(0, 0))
        notes_widget.insert("1.0", entry.get("notes", ""))
        
        fields["notes"] = {"widget": notes_widget}
        
        def save_entry():
            updates = {
                "title": fields["title"]["widget"].get(),
                "username": fields["username"]["widget"].get(),
                "password": fields["password"]["widget"].get(),
                "url": fields["url"]["widget"].get(),
                "notes": fields["notes"]["widget"].get("1.0", "end-1c"),
            }
            self.password_store.update_entry(entry["id"], **updates)
            self._refresh_passwords_list()
            messagebox.showinfo("Saved", "Password entry updated.")
        
        tk.Button(
            form,
            text="Save Changes",
            command=save_entry,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(pady=(16, 0))

    def _new_entry_dialog(self, folder_id=None):
        """Show dialog to create a new entry."""
        self._record_passwords_activity()
        
        dialog = tk.Toplevel(self.root)
        dialog.title("New Password Entry")
        dialog.configure(bg=COLORS["paper"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        tk.Label(
            dialog,
            text="New Password Entry",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 14),
        ).pack(anchor="w", padx=20, pady=(18, 12))
        
        tk.Label(
            dialog,
            text="Title",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(0, 4))
        
        title_entry = tk.Entry(
            dialog,
            font=("Segoe UI", 11),
            relief="flat",
            bg=COLORS["search"],
            width=35,
        )
        title_entry.pack(fill="x", padx=20, ipady=6)
        
        def submit():
            title = title_entry.get().strip()
            if not title:
                messagebox.showwarning("Required", "Please enter a title.")
                return
            
            entry = self.password_store.create_entry(folder_id=folder_id, title=title)
            self.selected_entry_id = entry["id"]
            self._refresh_passwords_list()
            self._show_entry_editor(entry)
            dialog.destroy()
        
        button_frame = tk.Frame(dialog, bg=COLORS["paper"])
        button_frame.pack(pady=(14, 18))
        
        tk.Button(
            button_frame,
            text="Create",
            command=submit,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        
        tk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left")
        
        title_entry.bind("<Return>", lambda _: submit())
        title_entry.focus_set()
        
        dialog.wait_window()

    def _show_password_generator(self, target_entry):
        """Show password generator dialog."""
        self._record_passwords_activity()
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Password Generator")
        dialog.configure(bg=COLORS["paper"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        tk.Label(
            dialog,
            text="Generate Password",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 14),
        ).pack(anchor="w", padx=20, pady=(18, 12))
        
        length_var = tk.IntVar(value=16)
        upper_var = tk.BooleanVar(value=True)
        lower_var = tk.BooleanVar(value=True)
        digits_var = tk.BooleanVar(value=True)
        symbols_var = tk.BooleanVar(value=True)
        
        tk.Label(
            dialog,
            text="Length",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(0, 4))
        
        length_frame = tk.Frame(dialog, bg=COLORS["paper"])
        length_frame.pack(fill="x", padx=20, pady=(0, 12))
        
        tk.Scale(
            length_frame,
            from_=8,
            to=64,
            orient="horizontal",
            variable=length_var,
            bg=COLORS["paper"],
            fg=COLORS["text"],
            highlightthickness=0,
        ).pack(side="left", fill="x", expand=True)
        
        tk.Label(
            length_frame,
            textvariable=length_var,
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 11),
            width=3,
        ).pack(side="left", padx=(8, 0))
        
        options_frame = tk.Frame(dialog, bg=COLORS["paper"])
        options_frame.pack(fill="x", padx=20, pady=(0, 12))
        
        for label, var in [("Uppercase", upper_var), ("Lowercase", lower_var), ("Digits", digits_var), ("Symbols", symbols_var)]:
            tk.Checkbutton(
                options_frame,
                text=label,
                variable=var,
                bg=COLORS["paper"],
                fg=COLORS["text"],
                activebackground=COLORS["paper"],
                activeforeground=COLORS["text"],
                selectcolor=COLORS["search"],
                font=("Segoe UI", 9),
            ).pack(anchor="w")
        
        password_var = tk.StringVar()
        
        tk.Label(
            dialog,
            text="Generated Password",
            bg=COLORS["paper"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=20, pady=(0, 4))
        
        password_display = tk.Entry(
            dialog,
            textvariable=password_var,
            font=("Consolas", 11),
            relief="flat",
            bg=COLORS["search"],
            fg=COLORS["text"],
            state="readonly",
        )
        password_display.pack(fill="x", padx=20, ipady=6, pady=(0, 12))
        
        def generate_new():
            password = generate_password(
                length_var.get(),
                upper_var.get(),
                lower_var.get(),
                digits_var.get(),
                symbols_var.get(),
            )
            password_var.set(password)
        
        def use_password():
            password = password_var.get()
            if password:
                target_entry.delete(0, "end")
                target_entry.insert(0, password)
                dialog.destroy()
        
        button_frame = tk.Frame(dialog, bg=COLORS["paper"])
        button_frame.pack(pady=(0, 18))
        
        tk.Button(
            button_frame,
            text="Generate",
            command=generate_new,
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        
        tk.Button(
            button_frame,
            text="Use This Password",
            command=use_password,
            bg=COLORS["accent"],
            fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        
        tk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            activebackground=COLORS["sidebar_hover"],
            activeforeground=COLORS["text"],
            relief="flat",
            font=("Segoe UI", 10),
            padx=16,
            pady=8,
            bd=0,
            cursor="hand2",
        ).pack(side="left")
        
        generate_new()
        
        dialog.wait_window()

    def _lock_passwords(self):
        """Lock the password vault."""
        self.password_store.lock()
        self._exit_passwords_mode()

    def _schedule_clipboard_clear(self, password):
        """Schedule clipboard to be cleared after 20 seconds."""
        if self._clipboard_clear_job is not None:
            self.root.after_cancel(self._clipboard_clear_job)
        
        def clear():
            try:
                if self.root.clipboard_get() == password:
                    self.root.clipboard_clear()
            except tk.TclError:
                pass
        
        self._clipboard_clear_job = self.root.after(20000, clear)

    def _record_passwords_activity(self):
        """Record user activity for auto-lock."""
        from datetime import datetime
        self._last_passwords_activity = datetime.now()

    def _schedule_auto_lock(self):
        """Schedule auto-lock check."""
        self._cancel_auto_lock()
        self._auto_lock_job = self.root.after(30000, self._check_auto_lock)

    def _cancel_auto_lock(self):
        """Cancel auto-lock timer."""
        if self._auto_lock_job is not None:
            self.root.after_cancel(self._auto_lock_job)
            self._auto_lock_job = None

    def _check_auto_lock(self):
        """Check if vault should auto-lock due to inactivity."""
        if not self.passwords_mode or not self.password_store.unlocked:
            return
        
        from datetime import datetime, timedelta
        
        if self._last_passwords_activity:
            idle_time = datetime.now() - self._last_passwords_activity
            if idle_time > timedelta(minutes=5):
                self._lock_passwords()
                return
        
        self._schedule_auto_lock()

    def _passwords_on_close(self):
        """Called when app closes to lock passwords."""
        if self.password_store.unlocked:
            self.password_store.lock()
