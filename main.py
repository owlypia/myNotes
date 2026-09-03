import ctypes
import os
import sys
import traceback


def _log_path():
    appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(appdata, "MyNotes")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "error.log")


def _set_app_id():
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MyNotes.Desktop.1")
    except (AttributeError, OSError):
        pass


def main():
    _set_app_id()
    from notes_app import run

    run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            with open(_log_path(), "w", encoding="utf-8") as handle:
                handle.write(traceback.format_exc())
        except OSError:
            pass
        raise
