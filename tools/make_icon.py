from pathlib import Path

from PIL import Image, ImageDraw


def make_icon(dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [draw_note(size) for size in sizes]
    images[0].save(dest, format="ICO", sizes=[(size, size) for size in sizes])


def draw_note(size: int):
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad = max(1, size // 14)
    paper = (255, 252, 247, 255)
    ink = (62, 92, 69, 255)
    line = (212, 199, 176, 255)
    fold = (231, 225, 214, 255)

    draw.rounded_rectangle((pad, pad, size - pad - 1, size - pad - 1), radius=max(2, size // 8), fill=paper)
    fold_w = max(4, size // 3)
    x1, y0 = size - pad - 1, pad
    draw.polygon([(x1 - fold_w, y0), (x1, y0), (x1, y0 + fold_w)], fill=fold)
    draw.line([(x1 - fold_w, y0), (x1, y0 + fold_w)], fill=ink, width=max(1, size // 48))

    left = pad + size // 6
    right = size - pad - size // 6
    top = pad + size // 2
    gap = max(2, size // 8)
    for index in range(3):
        y = top + index * gap
        if y < size - pad - size // 8:
            draw.line([(left, y), (right, y)], fill=line, width=max(1, size // 32))
    return image


if __name__ == "__main__":
    make_icon(Path(__file__).resolve().parents[1] / "assets" / "icon.ico")
    print("icon created")
