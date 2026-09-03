import hashlib
import hmac
import json
import os

from paths import settings_file_path

ITERATIONS = 180_000


class PasswordVault:
    def __init__(self, path=None):
        self.path = path or settings_file_path()
        self.data = {}
        self.unlocked = False
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            self.data = {}
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.data = data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            self.data = {}

    def save(self):
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(self.data, handle, ensure_ascii=False, indent=2)

    def has_password(self):
        return bool(self.data.get("salt") and self.data.get("hash"))

    def set_password(self, password):
        password = (password or "").strip()
        if not password:
            return False
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
        self.data["salt"] = salt.hex()
        self.data["hash"] = digest.hex()
        self.save()
        self.unlocked = True
        return True

    def verify(self, password):
        if not self.has_password():
            return False
        salt = bytes.fromhex(self.data["salt"])
        digest = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, ITERATIONS)
        ok = hmac.compare_digest(digest.hex(), self.data["hash"])
        self.unlocked = ok
        return ok

    def lock(self):
        self.unlocked = False
