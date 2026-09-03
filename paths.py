import os
import sys


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def app_dir():
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts):
    if is_frozen():
        base = getattr(sys, "_MEIPASS", app_dir())
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def notes_file_path():
    return os.path.join(_data_folder(), "notes.json")


def settings_file_path():
    return os.path.join(_data_folder(), "settings.json")


def _data_folder():
    appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(appdata, "MyNotes")
    os.makedirs(folder, exist_ok=True)
    return folder
