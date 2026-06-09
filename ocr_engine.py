import cv2
import numpy as np
import os
import re

_rec_sess = None
_char_dict = None
SOLD_THRESHOLD = 0.82


def _get_rec():
    global _rec_sess, _char_dict
    if _rec_sess is None:
        import onnxruntime as ort
        models_dir = os.path.join(
            os.path.dirname(__import__("rapidocr").__file__), "models"
        )
        _rec_sess = ort.InferenceSession(
            os.path.join(models_dir, "ch_PP-OCRv4_rec_infer.onnx"),
            providers=["CPUExecutionProvider"],
        )
        with open(os.path.join(models_dir, "ppocr_keys_v1.txt"), "r", encoding="utf-8") as f:
            _char_dict = [""] + [l.strip() for l in f.readlines()]
    return _rec_sess, _char_dict


def _rec(img_bgr):
    sess, chardict = _get_rec()
    h, w = img_bgr.shape[:2]
    img_h = 48
    new_w = max(int(round(img_h * w / h)), 8)
    resized = cv2.resize(img_bgr, (new_w, img_h)).astype(np.float32)
    inp = resized.transpose((2, 0, 1)) / 255.0
    inp = (inp - 0.5) / 0.5
    inp = np.expand_dims(inp, axis=0)
    out = sess.run(None, {sess.get_inputs()[0].name: inp})[0]
    indices = np.argmax(out, axis=-1)[0]
    text = ""
    prev = -1
    for idx in indices:
        if idx != prev and idx != 0 and idx < len(chardict):
            text += chardict[idx]
        prev = idx
    return text


def _projection_rows(roi_bgr):
    """Split ROI into rows by y-projection only, keep full width."""
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if np.mean(binary) > 128:
        binary = 255 - binary
    h_proj = np.sum(binary, axis=1)
    th = np.max(h_proj) * 0.05
    rows = h_proj > th
    lines = []
    in_line = False
    start = 0
    for y, ok in enumerate(rows):
        if ok and not in_line:
            start = y
            in_line = True
        elif not ok and in_line:
            lines.append((start, y))
            in_line = False
    if in_line:
        lines.append((start, len(rows)))
    return [roi_bgr[y1 : y2 + 1, :, :] for y1, y2 in lines]


def recognize_card(card_bgr):
    from constants import ARMAMENT_NAMES
    from difflib import get_close_matches

    h, w = card_bgr.shape[:2]

    # Name: projection rows + rec
    name_roi = card_bgr[int(h * 0.62) : h, :, :]
    name = ""
    for row in _projection_rows(name_roi):
        text = _rec(row).strip()
        chinese = re.sub(r"[^\u4e00-\u9fff]", "", text)
        if chinese:
            candidates = get_close_matches(chinese, ARMAMENT_NAMES, n=1, cutoff=0.3)
            if candidates:
                name = candidates[0]
            elif not name and any(arm in chinese for arm in ARMAMENT_NAMES if len(arm) >= 3):
                name = chinese

    # Price: fixed ROI rec (taller, works better for digits)
    price_roi = card_bgr[int(h * 0.80) : int(h * 1.00), int(w * 0.12) : int(w * 0.48), :]
    price_text = _rec(price_roi).strip().replace(" ", "")
    price_text = re.sub(r"[\u4e00-\u9fff]", "", price_text)
    price = ""
    for p in ("1200", "400", "200", "100"):
        if p in price_text:
            price = p
            break

    return name, price


def is_sold_out(card_bgr):
    return False, False, False, 0


def _template_dirs():
    return []


def _imread(path):
    with open(path, "rb") as f:
        data = np.frombuffer(f.read(), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def get_sold_out_template():
    dirs = []
    import sys
    if getattr(sys, "frozen", False):
        dirs.append(os.path.join(sys._MEIPASS, "templates"))
        dirs.append(os.path.join(os.path.dirname(sys.executable), "templates"))
    else:
        dirs.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))
    for d in dirs:
        p = os.path.join(d, "已售.png")
        if os.path.exists(p):
            return p
    return None


def _match(image_bgr, tpl_path, threshold):
    if not os.path.exists(tpl_path):
        return False, 0
    templ = _imread(tpl_path)
    if templ is None or templ.size == 0:
        return False, 0
    ih, iw = image_bgr.shape[:2]
    th, tw = templ.shape[:2]
    if th > ih or tw > iw:
        s = min(ih / th, iw / tw)
        if s < 1:
            templ = cv2.resize(templ, (int(tw * s), int(th * s)))
    result = cv2.matchTemplate(image_bgr, templ, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val >= threshold, max_val


def is_sold_out_by_template(card_bgr):
    path = get_sold_out_template()
    if not path:
        return False
    ok, _ = _match(card_bgr, path, SOLD_THRESHOLD)
    return ok


def get_arm_templates():
    return {}


def matches_armament(card_bgr, selected_names, thresholds=None):
    name, _ = recognize_card(card_bgr)
    for sel in selected_names:
        if sel in name:
            return True, sel, 1.0
    return False, name, 0.0
