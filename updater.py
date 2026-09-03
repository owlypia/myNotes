import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass

from version import APP_VERSION, GITHUB_OWNER, GITHUB_REPO, SETUP_ASSET_NAME

API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


@dataclass
class ReleaseInfo:
    version: str
    tag: str
    notes: str
    download_url: str
    page_url: str


def parse_version(value):
    text = (value or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    parts = []
    for chunk in text.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(candidate, current=APP_VERSION):
    return parse_version(candidate) > parse_version(current)


def fetch_latest_release(timeout=12):
    request = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": f"MyNotes/{APP_VERSION}",
            "Accept": "application/vnd.github+json",
        },
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    tag = payload.get("tag_name") or ""
    version = tag[1:] if tag.lower().startswith("v") else tag
    download_url = ""
    for asset in payload.get("assets") or []:
        if asset.get("name") == SETUP_ASSET_NAME:
            download_url = asset.get("browser_download_url") or ""
            break
    return ReleaseInfo(
        version=version or "0.0.0",
        tag=tag,
        notes=(payload.get("body") or "").strip(),
        download_url=download_url,
        page_url=payload.get("html_url") or "",
    )


def download_installer(url, destination, timeout=120):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"MyNotes/{APP_VERSION}"},
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        data = response.read()
    with open(destination, "wb") as handle:
        handle.write(data)
    return destination
