# Password Manager Manual Testing Guide

## Prerequisites
- Install dependencies: `pip install cryptography`
- Run the app: `python main.py` (or use the built executable)

## Test Scenarios

### 1. First-Time Setup
**Steps:**
1. Launch MyNotes
2. Click the **Passwords** button in the sidebar filter row
3. You should see "Create Password Vault" dialog
4. Enter a password (min 8 characters recommended)
5. Confirm the password
6. Click "Create Vault"
7. **IMPORTANT**: A recovery key dialog appears - **copy and save this key!**
8. Click "I Saved It"

**Expected Result:**
- Vault created successfully
- You're now in password manager view
- Sidebar shows "Password Manager" heading with "New Entry" and "Lock" buttons

### 2. Create a Password Entry
**Steps:**
1. While in Passwords mode, click **New Entry**
2. Enter a title (e.g., "Gmail")
3. Click "Create"
4. Fill in the entry form:
   - Title: Gmail
   - Username: user@gmail.com
   - Password: (click "Generate Password" or type one)
   - URL: https://gmail.com
   - Notes: Personal email account
5. Click **Save Changes**

**Expected Result:**
- Entry appears in the left sidebar
- Shows title and username

### 3. Generate Password
**Steps:**
1. Create or edit an entry
2. Click **Generate Password** button
3. Adjust length slider (8-64 characters)
4. Toggle character options (Uppercase, Lowercase, Digits, Symbols)
5. Click **Generate** to create a new password
6. Click **Use This Password**

**Expected Result:**
- Generated password appears in the password field
- Password follows selected options

### 4. Copy Password with Auto-Clear
**Steps:**
1. Select an entry
2. Click the **Copy** button next to the password field
3. Paste into a text editor (Ctrl+V) - should work
4. Wait 20 seconds
5. Try pasting again

**Expected Result:**
- Password copies immediately
- After 20 seconds, clipboard is cleared (paste shows nothing or previous clipboard content)

### 5. Show/Hide Password
**Steps:**
1. Select an entry with a password
2. Password field shows dots (••••)
3. Click **Show** button
4. Click **Hide** button

**Expected Result:**
- Password revealed when "Show" clicked
- Password masked when "Hide" clicked

### 6. Search Entries
**Steps:**
1. Create multiple entries (Gmail, GitHub, Facebook)
2. Type "git" in the search box

**Expected Result:**
- Only GitHub entry shown
- Search filters by title, username, and URL

### 7. Manual Lock/Unlock
**Steps:**
1. While in Passwords mode, click **Lock** button
2. You return to notes view
3. Click **Passwords** button again
4. Enter your vault password
5. Click **Unlock**

**Expected Result:**
- Vault locks and returns to notes
- Re-unlock with correct password works
- Wrong password rejected with error message

### 8. Recovery Key Unlock
**Steps:**
1. Lock the vault or restart the app
2. Click **Passwords**
3. Click "Forgot password? Use recovery key" link
4. Enter your recovery key (from step 1)
5. Click **Unlock**
6. Set a new password when prompted
7. Click **Change Password**

**Expected Result:**
- Recovery key unlocks vault
- Prompted to set new password
- New password works for subsequent unlocks
- Old password no longer works

### 9. Auto-Lock on Inactivity
**Steps:**
1. Unlock password vault
2. Wait 5 minutes without any interaction with the passwords section
3. Try to access passwords

**Expected Result:**
- After 5 minutes of inactivity, vault auto-locks
- User must re-authenticate

### 10. Delete Entry
**Steps:**
1. Select an entry
2. Click **Delete** button
3. Confirm in the dialog

**Expected Result:**
- Entry removed from sidebar
- Entry soft-deleted (not permanently removed from vault file)

### 11. Data Persistence
**Steps:**
1. Create several password entries
2. Lock the vault (or close the app)
3. Reopen and unlock

**Expected Result:**
- All entries preserved
- Data intact after lock/unlock cycle

### 12. Notes Export Safety
**Steps:**
1. Create some password entries
2. Go back to notes mode (uncheck Passwords)
3. Click backup menu → Export notes
4. Save the export file
5. Open the exported JSON file

**Expected Result:**
- Export file contains only notes, NOT passwords
- Passwords remain encrypted in separate vault file

### 13. Switch Between Notes and Passwords
**Steps:**
1. Create a note
2. Click **Passwords** filter
3. Create a password entry
4. Click **Public** filter (or any note filter)

**Expected Result:**
- Switching to Passwords unselects all note filters
- Switching to notes unselects Passwords
- Both modes work independently

### 14. App Close Auto-Lock
**Steps:**
1. Unlock password vault
2. Close the app
3. Reopen the app
4. Click **Passwords**

**Expected Result:**
- Vault locked on app close
- Must re-enter password on next access

## Security Verification

### File Encryption Check
1. Navigate to `%LOCALAPPDATA%\MyNotes\`
2. Open `passwords.vault` in a text editor
3. Verify you see encrypted data (base64 strings, no plaintext passwords)
4. Check that `passwords.vault.bak` also exists (encrypted backup)

### Tamper Detection
1. Close MyNotes
2. Open `passwords.vault` in a text editor
3. Modify a few characters in the "ciphertext" field
4. Save and close
5. Open MyNotes and try to unlock passwords

**Expected Result:**
- Unlock fails with error (corrupted/tampered data detected)

## Performance Testing

### Large Entry Count
1. Create 50-100 password entries
2. Test search responsiveness
3. Test lock/unlock speed

**Expected Result:**
- No significant slowdown
- Search remains fast
- Lock/unlock takes ~1-2 seconds (due to Scrypt KDF)

## Common Issues

**Issue**: "Vault is locked" error when trying to save
- **Cause**: Auto-lock triggered
- **Solution**: Unlock vault again

**Issue**: Recovery key doesn't work
- **Cause**: Key entered incorrectly (case/spaces matter for base32)
- **Solution**: Remove spaces, try both uppercase and lowercase

**Issue**: Password manager button doesn't appear
- **Cause**: Not running latest version
- **Solution**: Pull latest code and reinstall dependencies

## Test Results Template

```
Test Date: [DATE]
Tester: [NAME]
Version: 1.2.0

| Scenario | Status | Notes |
|----------|--------|-------|
| 1. First-Time Setup | ☐ Pass ☐ Fail | |
| 2. Create Entry | ☐ Pass ☐ Fail | |
| 3. Generate Password | ☐ Pass ☐ Fail | |
| 4. Copy with Auto-Clear | ☐ Pass ☐ Fail | |
| 5. Show/Hide Password | ☐ Pass ☐ Fail | |
| 6. Search | ☐ Pass ☐ Fail | |
| 7. Lock/Unlock | ☐ Pass ☐ Fail | |
| 8. Recovery Key | ☐ Pass ☐ Fail | |
| 9. Auto-Lock | ☐ Pass ☐ Fail | |
| 10. Delete Entry | ☐ Pass ☐ Fail | |
| 11. Data Persistence | ☐ Pass ☐ Fail | |
| 12. Export Safety | ☐ Pass ☐ Fail | |
| 13. Switch Modes | ☐ Pass ☐ Fail | |
| 14. App Close Lock | ☐ Pass ☐ Fail | |
```
