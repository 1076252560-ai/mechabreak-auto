import ctypes
import time

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

VK_SPACE = 0x20
VK_ESC = 0x1B
SC_SPACE = 0x39
SC_ESC = 0x01

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

_log = None


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", INPUT_UNION)]


def set_log(fn):
    global _log
    _log = fn


def _show_dot(x, y, r=12):
    hdc = user32.GetDC(0)
    if not hdc:
        return
    brush = gdi32.CreateSolidBrush(0x0000FF)
    prev = gdi32.SelectObject(hdc, brush)
    gdi32.Ellipse(hdc, x - r, y - r, x + r, y + r)
    time.sleep(0.35)
    gdi32.SelectObject(hdc, prev)
    gdi32.DeleteObject(brush)
    user32.ReleaseDC(0, hdc)


def _mouse_click(x, y):
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    abs_x = int(x * 65536 / sw)
    abs_y = int(y * 65536 / sh)
    _show_dot(x, y)
    user32.SetCursorPos(x, y)
    time.sleep(0.05)
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN
    inp.union.mi.dx = abs_x
    inp.union.mi.dy = abs_y
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    time.sleep(0.05)
    inp.union.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _key_press(vk, scan):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki.wVk = vk
    inp.union.ki.wScan = scan
    inp.union.ki.dwFlags = KEYEVENTF_SCANCODE
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    time.sleep(0.1)
    inp.union.ki.dwFlags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def buy_card(cx, cy, delay_ms):
    d = delay_ms / 1000.0
    if _log:
        _log(f"  购买: 点击({cx},{cy})")
    _mouse_click(cx, cy)
    time.sleep(d)
    if _log:
        _log("  Space")
    _key_press(VK_SPACE, SC_SPACE)
    time.sleep(d)
    if _log:
        _log("  Space")
    _key_press(VK_SPACE, SC_SPACE)
    time.sleep(d)
    if _log:
        _log("  Esc")
    _key_press(VK_ESC, SC_ESC)
    time.sleep(0.2)
    user32.SetCursorPos(0, 0)


def refresh(cx, cy, delay_ms):
    d = delay_ms / 1000.0
    if _log:
        _log(f"  刷新: 点击({cx},{cy})")
    _mouse_click(cx, cy)
    time.sleep(d)
    if _log:
        _log("  Space")
    _key_press(VK_SPACE, SC_SPACE)
    time.sleep(0.2)
    user32.SetCursorPos(0, 0)
