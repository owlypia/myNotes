from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from version import APP_VERSION


def version_tuple():
    parts = APP_VERSION.split(".")
    numbers = []
    for part in parts:
        digits = "".join(ch for ch in part if ch.isdigit())
        numbers.append(int(digits) if digits else 0)
    while len(numbers) < 4:
        numbers.append(0)
    return tuple(numbers[:4])


def sync():
    major, minor, patch, build = version_tuple()
    iss = ROOT / "installer" / "MyNotes.iss"
    text = iss.read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines(keepends=True):
        if line.startswith("#define MyAppVersion"):
            line = f'#define MyAppVersion "{APP_VERSION}"\n'
        lines.append(line)
    iss.write_text("".join(lines), encoding="utf-8")

    info = ROOT / "file_version_info.txt"
    text = info.read_text(encoding="utf-8")

    text = re.sub(r"filevers=\(\d+, \d+, \d+, \d+\)", f"filevers=({major}, {minor}, {patch}, {build})", text)
    text = re.sub(r"prodvers=\(\d+, \d+, \d+, \d+\)", f"prodvers=({major}, {minor}, {patch}, {build})", text)
    text = re.sub(r'StringStruct\("FileVersion", "[^"]+"\)', f'StringStruct("FileVersion", "{APP_VERSION}")', text)
    text = re.sub(r'StringStruct\("ProductVersion", "[^"]+"\)', f'StringStruct("ProductVersion", "{APP_VERSION}")', text)
    info.write_text(text, encoding="utf-8")
    print(f"Synced version {APP_VERSION}")


if __name__ == "__main__":
    sync()
