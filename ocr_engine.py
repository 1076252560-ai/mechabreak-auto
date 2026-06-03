import cv2
import numpy as np
import os
import sys

ARM_THRESHOLD = 0.90
SOLD_THRESHOLD = 0.82


def _template_dirs():
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(os.path.join(sys._MEIPASS, "templates"))
        dirs.append(os.path.join(os.path.dirname(sys.executable), "templates"))
    else:
        dirs.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))
    return dirs


def _find_template(filename):
    for d in _template_dirs():
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return None


def _imread(path):
    with open(path, "rb") as f:
        data = np.frombuffer(f.read(), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def get_arm_templates():
    templates = {}
    for d in _template_dirs():
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".png") and f not in ("已售.png", "刷新.png"):
                name = f[:-4]
                if name not in templates:
                    templates[name] = os.path.join(d, f)
    return templates


def get_sold_out_template():
    return _find_template("已售.png")


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


def is_sold_out(card_bgr):
    gray = _gray_sold_out(card_bgr)
    path = get_sold_out_template()
    tmpl_ok, tmpl_conf = False, 0
    if path:
        tmpl_ok, tmpl_conf = _match(card_bgr, path, SOLD_THRESHOLD)
    return gray or tmpl_ok, gray, tmpl_ok, tmpl_conf


def _gray_sold_out(card_bgr):
    hsv = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2HSV)
    s = hsv[:, :, 1]
    return (np.sum(s < 30) / s.size) > 0.65


def matches_armament(card_bgr, selected_names, thresholds=None):
    if thresholds is None:
        thresholds = {}
    default_th = thresholds.get("_default", ARM_THRESHOLD)
    templates = get_arm_templates()
    best_name, best_conf = "?", 0
    for name in selected_names:
        if name not in templates:
            continue
        th = thresholds.get(name, default_th)
        ok, conf = _match(card_bgr, templates[name], th)
        if ok and conf > best_conf:
            best_name, best_conf = name, conf
    if best_conf > 0:
        return True, best_name, best_conf
    return False, "?", 0
