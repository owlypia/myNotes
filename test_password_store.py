"""Unit tests for password_store.py"""
import os
import tempfile
import unittest
from password_store import (
    PasswordStore,
    generate_password,
    generate_recovery_key,
    validate_recovery_key,
)


class TestPasswordStore(unittest.TestCase):
    def setUp(self):
        """Create a temporary vault file for each test."""
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix=".vault")
        os.close(self.temp_fd)
        os.unlink(self.temp_path)
        self.store = PasswordStore(self.temp_path)

    def tearDown(self):
        """Clean up temporary files."""
        for path in [self.temp_path, self.temp_path + ".bak", self.temp_path + ".tmp"]:
            if os.path.exists(path):
                os.unlink(path)

    def test_create_vault_with_password(self):
        """Test creating a new vault with password."""
        recovery_key = self.store.create("testpassword123")
        self.assertTrue(self.store.unlocked)
        self.assertTrue(self.store.exists())
        self.assertIsNotNone(recovery_key)
        self.assertTrue(validate_recovery_key(recovery_key))

    def test_create_vault_with_custom_recovery_key(self):
        """Test creating a vault with a provided recovery key."""
        custom_key = generate_recovery_key()
        returned_key = self.store.create("testpassword123", recovery_key=custom_key)
        self.assertEqual(custom_key, returned_key)
        self.assertTrue(self.store.unlocked)

    def test_unlock_with_correct_password(self):
        """Test unlocking vault with correct password."""
        self.store.create("mypassword")
        self.store.lock()
        self.assertFalse(self.store.unlocked)
        
        self.store.unlock(password="mypassword")
        self.assertTrue(self.store.unlocked)

    def test_unlock_with_wrong_password(self):
        """Test that wrong password is rejected."""
        self.store.create("correctpassword")
        self.store.lock()
        
        with self.assertRaises(ValueError) as context:
            self.store.unlock(password="wrongpassword")
        self.assertIn("Wrong password", str(context.exception))
        self.assertFalse(self.store.unlocked)

    def test_unlock_with_recovery_key(self):
        """Test unlocking vault with recovery key."""
        recovery_key = self.store.create("password123")
        self.store.lock()
        
        new_store = PasswordStore(self.temp_path)
        new_store.unlock(recovery_key=recovery_key)
        self.assertTrue(new_store.unlocked)

    def test_unlock_with_wrong_recovery_key(self):
        """Test that wrong recovery key is rejected."""
        self.store.create("password123")
        self.store.lock()
        
        wrong_key = generate_recovery_key()
        with self.assertRaises(ValueError):
            self.store.unlock(recovery_key=wrong_key)
        self.assertFalse(self.store.unlocked)

    def test_change_password(self):
        """Test changing vault password."""
        recovery_key = self.store.create("oldpassword")
        self.store.change_password("newpassword")
        self.store.lock()
        
        self.store.unlock(password="newpassword")
        self.assertTrue(self.store.unlocked)
        
        self.store.lock()
        self.store.unlock(recovery_key=recovery_key)
        self.assertTrue(self.store.unlocked)

    def test_change_password_locks_old_password(self):
        """Test that old password no longer works after change."""
        self.store.create("oldpassword")
        self.store.change_password("newpassword")
        self.store.lock()
        
        with self.assertRaises(ValueError):
            self.store.unlock(password="oldpassword")

    def test_round_trip_data_persistence(self):
        """Test that data persists through lock/unlock cycle."""
        self.store.create("testpass")
        
        folder = self.store.create_folder("Work")
        entry = self.store.create_entry(
            folder_id=folder["id"],
            title="Email",
            username="user@example.com",
            password="secret123",
            url="https://example.com",
            notes="Important account",
        )
        
        self.store.lock()
        self.store.unlock(password="testpass")
        
        folders = self.store.get_folders()
        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0]["name"], "Work")
        
        entries = self.store.get_entries(folder["id"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Email")
        self.assertEqual(entries[0]["username"], "user@example.com")
        self.assertEqual(entries[0]["password"], "secret123")

    def test_tampered_file_detection(self):
        """Test that tampering with the vault file is detected."""
        self.store.create("password123")
        self.store.create_entry(title="Test", password="secret")
        self.store.lock()
        
        with open(self.temp_path, "r") as f:
            import json
            data = json.load(f)
        
        data["ciphertext"] = data["ciphertext"][:-10] + "TAMPERED!!"
        
        with open(self.temp_path, "w") as f:
            json.dump(data, f)
        
        new_store = PasswordStore(self.temp_path)
        with self.assertRaises(ValueError):
            new_store.unlock(password="password123")

    def test_create_and_retrieve_entries(self):
        """Test creating and retrieving password entries."""
        self.store.create("testpass")
        
        entry1 = self.store.create_entry(title="Gmail", username="user@gmail.com", password="pass1")
        entry2 = self.store.create_entry(title="GitHub", username="devuser", password="pass2")
        
        entries = self.store.get_entries()
        self.assertEqual(len(entries), 2)
        
        retrieved = self.store.get_entry(entry1["id"])
        self.assertEqual(retrieved["title"], "Gmail")
        self.assertEqual(retrieved["username"], "user@gmail.com")

    def test_update_entry(self):
        """Test updating an entry."""
        self.store.create("testpass")
        entry = self.store.create_entry(title="Old Title", username="olduser")
        
        self.store.update_entry(entry["id"], title="New Title", username="newuser", password="newpass")
        
        updated = self.store.get_entry(entry["id"])
        self.assertEqual(updated["title"], "New Title")
        self.assertEqual(updated["username"], "newuser")
        self.assertEqual(updated["password"], "newpass")

    def test_delete_entry(self):
        """Test soft-deleting an entry."""
        self.store.create("testpass")
        entry = self.store.create_entry(title="To Delete")
        
        self.store.delete_entry(entry["id"])
        
        entries = self.store.get_entries()
        self.assertEqual(len(entries), 0)
        
        retrieved = self.store.get_entry(entry["id"])
        self.assertIsNone(retrieved)

    def test_search_entries(self):
        """Test searching entries."""
        self.store.create("testpass")
        self.store.create_entry(title="Gmail", username="user@gmail.com")
        self.store.create_entry(title="GitHub", username="devuser")
        self.store.create_entry(title="Facebook", username="social@fb.com")
        
        results = self.store.search("gmail")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Gmail")
        
        results = self.store.search("user")
        self.assertEqual(len(results), 2)

    def test_folder_operations(self):
        """Test folder creation, renaming, and deletion."""
        self.store.create("testpass")
        
        folder = self.store.create_folder("Work")
        self.assertEqual(folder["name"], "Work")
        
        self.store.rename_folder(folder["id"], "Work Projects")
        updated = self.store.get_folder(folder["id"])
        self.assertEqual(updated["name"], "Work Projects")
        
        self.store.delete_folder(folder["id"])
        folders = self.store.get_folders()
        self.assertEqual(len(folders), 0)

    def test_folder_deletion_cascades_to_entries(self):
        """Test that deleting a folder soft-deletes its entries."""
        self.store.create("testpass")
        folder = self.store.create_folder("ToDelete")
        self.store.create_entry(folder_id=folder["id"], title="Entry1")
        self.store.create_entry(folder_id=folder["id"], title="Entry2")
        
        self.store.delete_folder(folder["id"])
        
        entries = self.store.get_entries(folder["id"])
        self.assertEqual(len(entries), 0)

    def test_backup_file_created(self):
        """Test that .bak file is created on updates."""
        self.store.create("testpass")
        self.store.create_entry(title="First")
        
        self.assertTrue(os.path.exists(self.temp_path + ".bak"))

    def test_atomic_write(self):
        """Test that writes are atomic (using temp file + rename)."""
        self.store.create("testpass")
        
        original_size = os.path.getsize(self.temp_path)
        self.store.create_entry(title="New Entry", password="secret")
        
        new_size = os.path.getsize(self.temp_path)
        self.assertGreater(new_size, original_size)
        
        self.assertFalse(os.path.exists(self.temp_path + ".tmp"))


class TestPasswordGeneration(unittest.TestCase):
    def test_generate_password_default(self):
        """Test generating password with default options."""
        password = generate_password()
        self.assertEqual(len(password), 16)
        # Test multiple generations to ensure randomness
        passwords = [generate_password(length=20) for _ in range(10)]
        # At least one should have each character type
        self.assertTrue(any(any(c.isupper() for c in p) for p in passwords))
        self.assertTrue(any(any(c.islower() for c in p) for p in passwords))
        self.assertTrue(any(any(c.isdigit() for c in p) for p in passwords))

    def test_generate_password_custom_length(self):
        """Test generating password with custom length."""
        password = generate_password(length=32)
        self.assertEqual(len(password), 32)

    def test_generate_password_lowercase_only(self):
        """Test generating lowercase-only password."""
        password = generate_password(use_upper=False, use_digits=False, use_symbols=False)
        self.assertTrue(all(c.islower() for c in password))

    def test_generate_password_no_symbols(self):
        """Test generating password without symbols."""
        password = generate_password(use_symbols=False, length=100)
        self.assertTrue(all(c.isalnum() for c in password))

    def test_recovery_key_generation(self):
        """Test recovery key generation."""
        key = generate_recovery_key()
        self.assertTrue(validate_recovery_key(key))
        self.assertGreater(len(key), 40)

    def test_recovery_key_validation(self):
        """Test recovery key validation."""
        valid_key = generate_recovery_key()
        self.assertTrue(validate_recovery_key(valid_key))
        self.assertTrue(validate_recovery_key(valid_key.lower()))
        
        self.assertFalse(validate_recovery_key(""))
        self.assertFalse(validate_recovery_key("invalid"))
        self.assertFalse(validate_recovery_key(None))
        self.assertFalse(validate_recovery_key("ABC123"))


if __name__ == "__main__":
    unittest.main()
