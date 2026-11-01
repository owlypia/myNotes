"""Encrypted password storage for MyNotes using AES-GCM with envelope encryption."""
import base64
import hashlib
import json
import os
import secrets
import shutil
from datetime import datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from paths import passwords_vault_path

SCRYPT_N = 2**17  # 131072
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_LENGTH = 32
VERSION = 1


def _generate_salt():
    return os.urandom(32)


def _derive_key(password, salt):
    """Derive a 32-byte key from password using scrypt."""
    kdf = Scrypt(
        salt=salt,
        length=SCRYPT_LENGTH,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
    )
    return kdf.derive(password.encode("utf-8"))


def _encrypt_data(plaintext_bytes, key):
    """Encrypt data with AES-GCM and return (nonce, ciphertext)."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
    return nonce, ciphertext


def _decrypt_data(nonce, ciphertext, key):
    """Decrypt AES-GCM ciphertext."""
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def generate_recovery_key():
    """Generate a high-entropy recovery key (32 bytes = 256 bits, base32-encoded)."""
    raw = secrets.token_bytes(32)
    return base64.b32encode(raw).decode("ascii")


def validate_recovery_key(key):
    """Check if a recovery key has the correct format."""
    if not key or not isinstance(key, str):
        return False
    try:
        decoded = base64.b32decode(key.upper())
        return len(decoded) == 32
    except Exception:
        return False


class PasswordStore:
    def __init__(self, path=None):
        self.path = path or passwords_vault_path()
        self.unlocked = False
        self._data_key = None
        self._vault_data = None

    def exists(self):
        """Check if the vault file exists."""
        return os.path.exists(self.path)

    def create(self, password, recovery_key=None):
        """Create a new vault with the given password and optional recovery key.
        
        Returns the generated recovery key if none was provided.
        """
        if self.exists():
            raise ValueError("Vault already exists")
        
        if not recovery_key:
            recovery_key = generate_recovery_key()
        elif not validate_recovery_key(recovery_key):
            raise ValueError("Invalid recovery key format")
        
        password_salt = _generate_salt()
        recovery_salt = _generate_salt()
        
        password_key = _derive_key(password, password_salt)
        recovery_derived = _derive_key(recovery_key, recovery_salt)
        
        data_key = AESGCM.generate_key(bit_length=256)
        
        pw_nonce, pw_wrapped = _encrypt_data(data_key, password_key)
        rec_nonce, rec_wrapped = _encrypt_data(data_key, recovery_derived)
        
        initial_data = {
            "folders": [],
            "entries": [],
        }
        payload = json.dumps(initial_data, ensure_ascii=False).encode("utf-8")
        data_nonce, ciphertext = _encrypt_data(payload, data_key)
        
        vault_structure = {
            "version": VERSION,
            "password_salt": base64.b64encode(password_salt).decode("ascii"),
            "password_nonce": base64.b64encode(pw_nonce).decode("ascii"),
            "password_wrapped_key": base64.b64encode(pw_wrapped).decode("ascii"),
            "recovery_salt": base64.b64encode(recovery_salt).decode("ascii"),
            "recovery_nonce": base64.b64encode(rec_nonce).decode("ascii"),
            "recovery_wrapped_key": base64.b64encode(rec_wrapped).decode("ascii"),
            "data_nonce": base64.b64encode(data_nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }
        
        self._write_vault(vault_structure)
        
        self._data_key = data_key
        self._vault_data = initial_data
        self.unlocked = True
        
        return recovery_key

    def unlock(self, password=None, recovery_key=None):
        """Unlock the vault with password or recovery key."""
        if not self.exists():
            raise ValueError("Vault does not exist")
        
        if not password and not recovery_key:
            raise ValueError("Password or recovery key required")
        
        vault = self._read_vault()
        
        if password:
            salt = base64.b64decode(vault["password_salt"])
            nonce = base64.b64decode(vault["password_nonce"])
            wrapped_key = base64.b64decode(vault["password_wrapped_key"])
            derived_key = _derive_key(password, salt)
        else:
            if not validate_recovery_key(recovery_key):
                raise ValueError("Invalid recovery key format")
            salt = base64.b64decode(vault["recovery_salt"])
            nonce = base64.b64decode(vault["recovery_nonce"])
            wrapped_key = base64.b64decode(vault["recovery_wrapped_key"])
            derived_key = _derive_key(recovery_key, salt)
        
        try:
            data_key = _decrypt_data(nonce, wrapped_key, derived_key)
        except Exception:
            raise ValueError("Wrong password or recovery key")
        
        data_nonce = base64.b64decode(vault["data_nonce"])
        ciphertext = base64.b64decode(vault["ciphertext"])
        
        try:
            plaintext = _decrypt_data(data_nonce, ciphertext, data_key)
            vault_data = json.loads(plaintext.decode("utf-8"))
        except Exception:
            raise ValueError("Vault data is corrupted or tampered")
        
        self._data_key = data_key
        self._vault_data = vault_data
        self.unlocked = True

    def change_password(self, new_password):
        """Change the vault password while keeping the recovery key."""
        if not self.unlocked:
            raise ValueError("Vault is locked")
        
        vault = self._read_vault()
        
        new_salt = _generate_salt()
        new_key = _derive_key(new_password, new_salt)
        
        pw_nonce, pw_wrapped = _encrypt_data(self._data_key, new_key)
        
        vault["password_salt"] = base64.b64encode(new_salt).decode("ascii")
        vault["password_nonce"] = base64.b64encode(pw_nonce).decode("ascii")
        vault["password_wrapped_key"] = base64.b64encode(pw_wrapped).decode("ascii")
        
        self._write_vault(vault)

    def lock(self):
        """Lock the vault and clear sensitive data from memory."""
        self.unlocked = False
        self._data_key = None
        self._vault_data = None

    def save(self):
        """Save the current vault data."""
        if not self.unlocked:
            raise ValueError("Vault is locked")
        
        vault = self._read_vault()
        
        payload = json.dumps(self._vault_data, ensure_ascii=False).encode("utf-8")
        data_nonce, ciphertext = _encrypt_data(payload, self._data_key)
        
        vault["data_nonce"] = base64.b64encode(data_nonce).decode("ascii")
        vault["ciphertext"] = base64.b64encode(ciphertext).decode("ascii")
        
        self._write_vault(vault)

    def _read_vault(self):
        """Read and parse the vault file."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or data.get("version") != VERSION:
                raise ValueError("Invalid vault format")
            return data
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"Cannot read vault file: {e}")

    def _write_vault(self, vault_structure):
        """Write vault to disk atomically with backup."""
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        
        temp_path = self.path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(vault_structure, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        if os.path.exists(self.path):
            try:
                shutil.copy2(self.path, self.path + ".bak")
            except OSError:
                pass
        
        os.replace(temp_path, self.path)

    def get_folders(self):
        """Get all folders (not soft-deleted)."""
        if not self.unlocked:
            return []
        return [f for f in self._vault_data.get("folders", []) if not f.get("deleted_at")]

    def get_folder(self, folder_id):
        """Get a folder by ID."""
        if not self.unlocked:
            return None
        for folder in self._vault_data.get("folders", []):
            if folder.get("id") == folder_id and not folder.get("deleted_at"):
                return folder
        return None

    def create_folder(self, name, parent_id=None):
        """Create a new folder."""
        if not self.unlocked:
            raise ValueError("Vault is locked")
        
        now = datetime.now().isoformat(timespec="seconds")
        folder = {
            "id": secrets.token_hex(16),
            "name": name,
            "parent_id": parent_id,
            "created_at": now,
            "updated_at": now,
        }
        self._vault_data.setdefault("folders", []).append(folder)
        self.save()
        return folder

    def rename_folder(self, folder_id, new_name):
        """Rename a folder."""
        if not self.unlocked:
            raise ValueError("Vault is locked")
        
        folder = self.get_folder(folder_id)
        if not folder:
            raise ValueError("Folder not found")
        
        folder["name"] = new_name
        folder["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.save()

    def delete_folder(self, folder_id):
        """Soft-delete a folder and all its entries."""
        if not self.unlocked:
            raise ValueError("Vault is locked")
        
        folder = self.get_folder(folder_id)
        if not folder:
            raise ValueError("Folder not found")
        
        now = datetime.now().isoformat(timespec="seconds")
        folder["deleted_at"] = now
        
        for entry in self._vault_data.get("entries", []):
            if entry.get("folder_id") == folder_id and not entry.get("deleted_at"):
                entry["deleted_at"] = now
        
        self.save()

    def get_entries(self, folder_id=None):
        """Get all entries (not soft-deleted), optionally filtered by folder."""
        if not self.unlocked:
            return []
        
        entries = [e for e in self._vault_data.get("entries", []) if not e.get("deleted_at")]
        
        if folder_id is not None:
            entries = [e for e in entries if e.get("folder_id") == folder_id]
        
        return entries

    def get_entry(self, entry_id):
        """Get an entry by ID."""
        if not self.unlocked:
            return None
        for entry in self._vault_data.get("entries", []):
            if entry.get("id") == entry_id and not entry.get("deleted_at"):
                return entry
        return None

    def create_entry(self, folder_id=None, title="", username="", password="", url="", notes="", tags=None):
        """Create a new password entry."""
        if not self.unlocked:
            raise ValueError("Vault is locked")
        
        now = datetime.now().isoformat(timespec="seconds")
        entry = {
            "id": secrets.token_hex(16),
            "folder_id": folder_id,
            "title": title,
            "username": username,
            "password": password,
            "url": url,
            "notes": notes,
            "tags": tags or [],
            "created_at": now,
            "updated_at": now,
        }
        self._vault_data.setdefault("entries", []).append(entry)
        self.save()
        return entry

    def update_entry(self, entry_id, **kwargs):
        """Update an entry's fields."""
        if not self.unlocked:
            raise ValueError("Vault is locked")
        
        entry = self.get_entry(entry_id)
        if not entry:
            raise ValueError("Entry not found")
        
        for key in ("title", "username", "password", "url", "notes", "tags", "folder_id"):
            if key in kwargs:
                entry[key] = kwargs[key]
        
        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.save()

    def delete_entry(self, entry_id):
        """Soft-delete an entry."""
        if not self.unlocked:
            raise ValueError("Vault is locked")
        
        entry = self.get_entry(entry_id)
        if not entry:
            raise ValueError("Entry not found")
        
        entry["deleted_at"] = datetime.now().isoformat(timespec="seconds")
        self.save()

    def search(self, query):
        """Search entries by title, username, or url."""
        if not self.unlocked:
            return []
        
        query_lower = query.lower().strip()
        if not query_lower:
            return self.get_entries()
        
        results = []
        for entry in self.get_entries():
            searchable = " ".join([
                entry.get("title", ""),
                entry.get("username", ""),
                entry.get("url", ""),
            ]).lower()
            if query_lower in searchable:
                results.append(entry)
        
        return results


def generate_password(length=16, use_upper=True, use_lower=True, use_digits=True, use_symbols=True):
    """Generate a random password using the secrets module."""
    chars = ""
    if use_lower:
        chars += "abcdefghijklmnopqrstuvwxyz"
    if use_upper:
        chars += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if use_digits:
        chars += "0123456789"
    if use_symbols:
        chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"
    
    if not chars:
        chars = "abcdefghijklmnopqrstuvwxyz"
    
    return "".join(secrets.choice(chars) for _ in range(length))
