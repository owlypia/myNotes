LIGHT = {
    "bg": "#F4F1EA",
    "sidebar": "#E7E1D6",
    "sidebar_hover": "#DDD5C6",
    "sidebar_active": "#D4C7B0",
    "paper": "#FFFCF7",
    "line": "#D8D0C4",
    "text": "#2B2A28",
    "muted": "#7A7468",
    "accent": "#3E5C45",
    "accent_hover": "#314A37",
    "danger": "#A33B2B",
    "danger_hover": "#862F22",
    "search": "#FFFCF7",
    "brand_my": "#6B2FA0",
    "brand_notes": "#C62828",
    "link": "#1565C0",
    "found": "#FFE58A",
    "found_current": "#FFB74D",
}

DARK = {
    "bg": "#171716",
    "sidebar": "#232321",
    "sidebar_hover": "#2D2D2A",
    "sidebar_active": "#3A3A35",
    "paper": "#2A2A28",
    "line": "#40403B",
    "text": "#ECE8E1",
    "muted": "#A29C90",
    "accent": "#5E8F69",
    "accent_hover": "#74A880",
    "danger": "#E57363",
    "danger_hover": "#F08A7A",
    "search": "#323230",
    "brand_my": "#B67BE8",
    "brand_notes": "#FF6B6B",
    "link": "#7FB2FF",
    "found": "#6B5A00",
    "found_current": "#A06A00",
}

THEMES = {"light": LIGHT, "dark": DARK}

# Shared, mutable colour table. Widgets read from it when they are built.
COLORS = dict(LIGHT)