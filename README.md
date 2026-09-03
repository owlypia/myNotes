# MyNotes

Windows desktop notes app by Kenan.

## Install

Download `MyNotesSetup.exe` from [Releases](https://github.com/owlypia/myNotes/releases) and run it.

Notes are stored in `%LOCALAPPDATA%\MyNotes` and are kept when you update.

## Updates

The app checks GitHub Releases on startup. You can also click **Check for updates** in the sidebar.

This repository must stay **public** so installed copies can see new releases.

## Publish a new version

1. Raise `APP_VERSION` in `version.py` (for example `1.0.0` → `1.0.1`).
2. Commit and push to `main`.
3. Create and push a tag:

```
git tag v1.0.1
git push origin v1.0.1
```

GitHub Actions builds `MyNotesSetup.exe` and attaches it to the release. Installed apps will offer that version.

## License

MIT. Copyright (c) 2026 Kenan (kenan@owlypia.org). See [LICENSE](LICENSE).
You may use, copy, modify, and share this software.
