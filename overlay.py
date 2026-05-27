import tkinter as tk
from PIL import ImageGrab, Image, ImageTk


class RegionSelector:
    def __init__(self, title="选择区域"):
        self.result = None

        screenshot = ImageGrab.grab(all_screens=True)
        self.screenshot = screenshot

        self.root = tk.Toplevel()
        self.root.title(title)
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.config(cursor="cross")
        self.root.wait_visibility(self.root)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        self.canvas = tk.Canvas(self.root, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._tk_img = ImageTk.PhotoImage(screenshot)
        self._bg_id = self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

        self._overlay_ids = []

        self.prompt = self.canvas.create_text(
            screen_w // 2, 50,
            text=f"拖拽框选 {title}，松开确认，右键取消",
            fill="#FFD700", font=("Microsoft YaHei", 16, "bold"),
        )

        self.start_x = None
        self.start_y = None
        self.rect_id = None

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_cancel)

    def _update_dim_region(self, x1, y1, x2, y2):
        for oid in self._overlay_ids:
            self.canvas.delete(oid)
        self._overlay_ids.clear()

        left, right = min(x1, x2), max(x1, x2)
        top, bottom = min(y1, y2), max(y1, y2)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        black = self.canvas.create_rectangle
        tag = "dim"
        # top
        if top > 0:
            self._overlay_ids.append(black(0, 0, sw, top, fill="black", stipple="gray50", outline="", tags=tag))
        # bottom
        if bottom < sh:
            self._overlay_ids.append(black(0, bottom, sw, sh, fill="black", stipple="gray50", outline="", tags=tag))
        # left
        if left > 0:
            self._overlay_ids.append(black(0, top, left, bottom, fill="black", stipple="gray50", outline="", tags=tag))
        # right
        if right < sw:
            self._overlay_ids.append(black(right, top, sw, bottom, fill="black", stipple="gray50", outline="", tags=tag))

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#00BFFF", width=2,
        )

    def _on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)
            self._update_dim_region(self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event):
        if self.start_x is None:
            return
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        w, h = x2 - x1, y2 - y1
        if w < 5 or h < 5:
            self.root.destroy()
            return
        self.result = (x1, y1, w, h)
        self.root.destroy()

    def _on_cancel(self, event):
        self.result = None
        self.root.destroy()

    def wait(self):
        self.root.wait_window()
        return self.result
