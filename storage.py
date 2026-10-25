import json
import os
import shutil
import uuid
from datetime import datetime

from paths import app_dir, notes_file_path

CATEGORIES = ("public", "private", "hidden")


def fold(text):
    """Case-insensitive form that treats Turkish I/i/dotted I/dotless i alike."""
    text = (text or "").replace("\u0130", "i").replace("I", "i").replace("\u0131", "i")
    return text.lower()


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

    def _read_file(self, path):
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError("notes file is not a list")
        return [item for item in data if isinstance(item, dict)]

    def load(self):
        if not os.path.exists(self.path):
            self.notes = []
            return
        try:
            self.notes = self._read_file(self.path)
        except (OSError, ValueError):
            self.notes = self._recover()
        if self._normalize_notes():
            self.save()

    def _recover(self):
        """The notes file is unreadable: keep a copy of it and fall back to the last backup."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            shutil.copy2(self.path, f"{self.path}.corrupt-{stamp}")
        except OSError:
            pass
        try:
            return self._read_file(self.path + ".bak")
        except (OSError, ValueError):
            return []

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
        temp_path = self.path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(self.notes, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        if os.path.exists(self.path):
            try:
                shutil.copy2(self.path, self.path + ".bak")
            except OSError:
                pass
        os.replace(temp_path, self.path)

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

    @staticmethod
    def _norm_formats(value):
        out = []
        for item in value or []:
            if isinstance(item, (list, tuple)) and len(item) == 3:
                out.append([item[0], item[1], item[2]])
        try:
            return sorted(out)
        except TypeError:
            return out

    def update(self, note_id, title, content, formats=None, tags=None):
        note = self.get(note_id)
        if note is None:
            return None
        given_content = content
        title, content = split_title_body(title, content)
        if content != given_content:
            formats = []  # the text was rearranged, so old format offsets no longer apply
        changed = note.get("title") != title or note.get("content") != content
        if formats is not None:
            formats = self._norm_formats(formats)
            if self._norm_formats(note.get("format")) != formats:
                changed = True
        if tags is not None and (note.get("tags") or []) != tags:
            changed = True
        if not changed:
            return note
        note["title"] = title
        note["content"] = content
        if formats is not None:
            if formats:
                note["format"] = formats
            else:
                note.pop("format", None)
        if tags is not None:
            if tags:
                note["tags"] = tags
            else:
                note.pop("tags", None)
        note["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.notes.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        self.save()
        return note

    def trash(self, note_id):
        note = self.get(note_id)
        if note is None:
            return None
        note["deleted_at"] = datetime.now().isoformat(timespec="seconds")
        self.save()
        return note

    def restore(self, note_id):
        note = self.get(note_id)
        if note is None:
            return None
        note.pop("deleted_at", None)
        self.save()
        return note

    def merge(self, items):
        """Add notes from another export. Existing notes are only replaced by a newer copy."""
        now = datetime.now().isoformat(timespec="seconds")
        added = updated = 0
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            item = dict(item)
            item["id"] = str(item["id"])
            item["title"] = str(item.get("title") or "")
            item["content"] = str(item.get("content") or "")
            item.setdefault("created_at", now)
            item.setdefault("updated_at", item["created_at"])
            existing = self.get(item["id"])
            if existing is None:
                self.notes.append(item)
                added += 1
            elif (item.get("updated_at") or "") > (existing.get("updated_at") or ""):
                existing.clear()
                existing.update(item)
                updated += 1
        if added or updated:
            self._normalize_notes()
            self.notes.sort(key=lambda note: note.get("updated_at", ""), reverse=True)
            self.save()
        return added, updated

    def daily_backup(self, keep=14):
        if not self.notes or not os.path.exists(self.path):
            return
        folder = os.path.join(os.path.dirname(self.path), "backups")
        try:
            os.makedirs(folder, exist_ok=True)
            target = os.path.join(folder, f"notes-{datetime.now():%Y%m%d}.json")
            if not os.path.exists(target):
                shutil.copy2(self.path, target)
            names = sorted(n for n in os.listdir(folder) if n.startswith("notes-") and n.endswith(".json"))
            for old in names[:-keep]:
                os.remove(os.path.join(folder, old))
        except OSError:
            pass

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

    def search(self, query, category=None, categories=None, trashed=False):
        text = fold((query or "").strip())
        if categories:
            wanted = set(categories)
        elif category:
            wanted = {category}
        else:
            wanted = {"public"}
        notes = [
            note
            for note in self.notes
            if note_category(note) in wanted and bool(note.get("deleted_at")) == trashed
        ]
        if trashed:
            notes.sort(key=lambda note: note.get("deleted_at", ""), reverse=True)
        else:
            notes.sort(key=lambda note: not note.get("pinned"))
        if not text:
            return notes
        results = []
        for note in notes:
            tags = " ".join("#" + tag for tag in (note.get("tags") or []) if isinstance(tag, str))
            haystack = fold(f"{note.get('title', '')} {note.get('content', '')} {tags}")
            if text in haystack:
                results.append(note)
        return results
