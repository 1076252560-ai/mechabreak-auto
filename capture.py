import mss
import numpy as np
import os
import sys
import tempfile
from PIL import Image, ImageDraw
from config import get_card_rects

TMPDIR = tempfile.gettempdir()
_debug_saved = False

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_DIR = os.path.join(BASE_DIR, "debug_screenshots")


def save_debug_grid(cards_rect, card_rects, full_rgb):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    img = Image.fromarray(full_rgb, "RGB")
    draw = ImageDraw.Draw(img)
    x0, y0, w0, h0 = cards_rect
    for i, r in enumerate(card_rects):
        lx = r["x"] - x0
        ly = r["y"] - y0
        draw.rectangle([lx, ly, lx + r["w"], ly + r["h"]],
                       outline="red", width=2)
        draw.text((lx + 4, ly + 4), str(i + 1), fill="yellow")
    img.save(os.path.join(DEBUG_DIR, "card_grid_debug.png"))
    return DEBUG_DIR


def capture_card_regions(cards_rect):
    global _debug_saved
    if cards_rect is None:
        return [], [], []
    rects = get_card_rects(cards_rect)
    if not rects:
        return [], [], []
    x0, y0, w0, h0 = cards_rect

    with mss.mss() as sct:
        screenshot = sct.grab({
            "top": y0, "left": x0, "width": w0, "height": h0,
        })
        full_arr = np.array(screenshot)

    if not _debug_saved:
        _debug_saved = True
        full_rgb = full_arr[..., [2, 1, 0]]
        save_debug_grid(cards_rect, rects, full_rgb)

    images = []
    paths = []
    arrays = []

    for i, r in enumerate(rects):
        local_x = r["x"] - x0
        local_y = r["y"] - y0
        card_bgra = full_arr[local_y:local_y + r["h"], local_x:local_x + r["w"]]
        card_rgb = card_bgra[..., [2, 1, 0]]

        img = Image.fromarray(card_rgb, "RGB")
        tmp = os.path.join(TMPDIR, f"mechabreak_card_{i}.png")
        img.save(tmp, "PNG")

        images.append(img)
        paths.append(tmp)
        arrays.append(card_bgra[..., :3])

    return images, paths, arrays


def reset_debug():
    global _debug_saved
    _debug_saved = False

def get_debug_dir():
    return DEBUG_DIR

