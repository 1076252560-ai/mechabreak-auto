import json
import os
import sys
from constants import CARD_COLS, CARD_ROWS, CARD_COUNT, ARMAMENT_NAMES, DEFAULT_REFRESH_DELAY, DEFAULT_MAX_ROUNDS, DEFAULT_ACTION_DELAY

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CHECKED = {
    "六联导弹发射器", "轻型导弹发射器", "重型狙击炮", "蓄能爆破炮",
    "双联火箭发射器", "速射炮", "射束机炮", "转管机炮", "分束机炮",
    "重型榴弹炮", "干扰烟幕散布器",
}


def _default_settings():
    return {
        "cards_rect": None,
        "refresh_rect": None,
        "iv_mode": "all",
        "arms": {name: name in DEFAULT_CHECKED for name in ARMAMENT_NAMES},
        "refresh_delay": 1,
        "max_rounds": 100,
        "action_delay": 200,
        "arm_thresholds": {"_default": 0.90, "蓄能爆破炮": 0.92},
    }


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        defaults = _default_settings()
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
        return data
    return _default_settings()


def save_config(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_settings(settings):
    cfg = load_config()
    cfg.update(settings)
    save_config(cfg)


def has_config():
    return os.path.exists(CONFIG_PATH)


def get_card_rects(cards_rect):
    if cards_rect is None:
        return []
    x, y, w, h = cards_rect
    card_w = w // CARD_COLS
    card_h = h // CARD_ROWS
    rects = []
    for row in range(CARD_ROWS):
        for col in range(CARD_COLS):
            rects.append({
                "x": x + col * card_w,
                "y": y + row * card_h,
                "w": card_w,
                "h": card_h,
            })
    return rects


def get_refresh_center(refresh_rect):
    if refresh_rect is None or len(refresh_rect) < 4:
        return (0, 0)
    x, y, w, h = refresh_rect
    return (x + w // 2, y + h // 2)
