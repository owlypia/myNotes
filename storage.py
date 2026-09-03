import json
import os
import shutil
import uuid
from datetime import datetime

from paths import app_dir, notes_file_path

CATEGORIES = ("public", "private", "hidden")


def split_title_body(title, content=""):
    title = (title or "").replace("\r\n", "\n").replace("\r", "\n")
    content = content or ""
    if "\n" in title:
        first, rest = title.split("\n", 1)
        title = first.strip()
        rest = rest.lstrip("\n")
        if rest:
            content = rest + ("\n" + content if content.strip() else "")
    if not title.strip() and content.strip():
        first_line = content.strip().split("\n", 1)[0].strip()
        title = first_line[:80] or "New note"
    return title, content


def note_category(note):
    value = (note or {}).get("category")
    if value in CATEGORIES:
        return value
    if (note or {}).get("hidden"):
        return "hidden"
    return "public"


class NoteStore:
    def __init__(self, path=None):
        if path is None:
            path = notes_file_path()
            self._migrate_legacy(path)
        self.path = path
        self.notes = []
        self.load()

    def _migrate_legacy(self, path):
        if os.path.exists(path):
            return
        legacy = os.path.join(app_dir(), "data", "notes.json")
        if os.path.exists(legacy):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.copy2(legacy, path)

    def load(self):
        if not os.path.exists(self.path):
            self.notes = []
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.notes = data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            self.notes = []
        if self._normalize_notes():
            self.save()

    def _normalize_notes(self):
        changed = False
        for note in self.notes:
            title, content = split_title_body(note.get("title", ""), note.get("content", ""))
            if title != note.get("title", "") or content != note.get("content", ""):
                note["title"] = title
                note["content"] = content
                changed = True
            category = note_category(note)
            if note.get("category") != category:
                note["category"] = category
                changed = True
            if "hidden" in note:
                del note["hidden"]
                changed = True
        return changed

    def save(self):
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(self.notes, handle, ensure_ascii=False, indent=2)

    def create(self, title="New note", content="", category="public"):
        if category not in CATEGORIES:
            category = "public"
        now = datetime.now().isoformat(timespec="seconds")
        note = {
            "id": uuid.uuid4().hex,
            "title": title,
            "content": content,
            "created_at": now,
            "updated_at": now,
            "category": category,
        }
        self.notes.insert(0, note)
        self.save()
        return note

    def update(self, note_id, title, content):
        note = self.get(note_id)
        if note is None:
            return None
        title, content = split_title_body(title, content)
        if note.get("title") == title and note.get("content") == content:
            return note
        note["title"] = title
        note["content"] = content
        note["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.notes.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        self.save()
        return note

    def set_category(self, note_id, category):
        if category not in CATEGORIES:
            return None
        note = self.get(note_id)
        if note is None:
            return None
        note["category"] = category
        self.save()
        return note

    def delete(self, note_id):
        before = len(self.notes)
        self.notes = [note for note in self.notes if note.get("id") != note_id]
        if len(self.notes) != before:
            self.save()
            return True
        return False

    def get(self, note_id):
        for note in self.notes:
            if note.get("id") == note_id:
                return note
        return None

    def search(self, query, category=None, categories=None):
        text = (query or "").strip().lower()
        if categories:
            wanted = set(categories)
        elif category:
            wanted = {category}
        else:
            wanted = {"public"}
        notes = [note for note in self.notes if note_category(note) in wanted]
        if not text:
            return notes
        results = []
        for note in notes:
            haystack = f"{note.get('title', '')} {note.get('content', '')}".lower()
            if text in haystack:
                results.append(note)
        return results
