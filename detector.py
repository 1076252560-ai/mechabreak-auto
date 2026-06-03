import cv2
import numpy as np
from constants import PURPLE_LOWER, PURPLE_UPPER, LEVEL_CHECK_HEIGHT_RATIO
from ocr_engine import is_sold_out as _is_sold_out, matches_armament as _matches_armament


def is_sold_out(card_bgr):
    return _is_sold_out(card_bgr)


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


def matches_armament(card_bgr, selected_names, thresholds=None):
    return _matches_armament(card_bgr, selected_names, thresholds)
