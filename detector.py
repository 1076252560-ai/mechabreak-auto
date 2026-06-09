import cv2
import numpy as np
from constants import PURPLE_LOWER, PURPLE_UPPER, LEVEL_CHECK_HEIGHT_RATIO
from ocr_engine import recognize_card, is_sold_out_by_template


def is_sold_out(card_bgr):
    return is_sold_out_by_template(card_bgr)


def is_iv_level(image_bgr, threshold=0.02):
    if image_bgr is None or image_bgr.size == 0:
        return False
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    height = hsv.shape[0]
    check_height = int(height * LEVEL_CHECK_HEIGHT_RATIO)
    top_region = hsv[0:check_height, :]
    mask = cv2.inRange(top_region, np.array(PURPLE_LOWER), np.array(PURPLE_UPPER))
    ratio = np.count_nonzero(mask) / max(mask.size, 1)
    return ratio >= threshold


def ocr_card(card_bgr):
    name, price = recognize_card(card_bgr)

    # Purple check first (fast, <1ms)
    if is_iv_level(card_bgr):
        return name, price, 4

    # Price-based level
    if price == "400":
        level = 3
    elif price == "200":
        level = 2
    elif price == "100":
        level = 1
    else:
        level = 0

    return name, price, level
