import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import time
import os
import sys
import traceback
import ctypes

from constants import (
    ARMAMENT_NAMES, CARD_COUNT,
    DEFAULT_REFRESH_DELAY, DEFAULT_MAX_ROUNDS, DEFAULT_ACTION_DELAY,
)
from config import load_config, save_config, get_card_rects, save_settings, DEFAULT_CHECKED
from capture import capture_card_regions, reset_debug
from detector import is_sold_out, is_iv_level, ocr_card
from actions import buy_card, refresh, set_log
from overlay import RegionSelector


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("解限机 路网补给助手")
        self.root.resizable(False, False)
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass

        self.root.update_idletasks()
        self.root.after(100, self._center_window)

        self.log_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
        self._stop_cpu = False
        self.config_data = load_config()
        set_log(self._log)
        self._build_ui()
        self._restore_state()
        self._poll_log()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(0, self._poll_f8)
        self.root.after(500, self._show_guide)

    def _center_window(self):
        self.root.update_idletasks()
        ww = self.root.winfo_width()
        wh = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - ww) // 2
        y = (sh - wh) // 2
        self.root.geometry(f"+{x}+{y}")

    def _build_ui(self):
        p = {"padx": 8, "pady": 4}
        f = ttk.Frame(self.root, padding=10)
        f.pack(fill=tk.BOTH, expand=True)

        r = 0
        ttk.Label(f, text="坐标配置:", font=("Microsoft YaHei", 9, "bold")).grid(row=r, column=0, sticky="w", **p)
        ttk.Button(f, text="配置区域", command=self._select_regions).grid(row=r, column=1, sticky="ew", **p)
        ttk.Button(f, text="使用指南", command=self._show_guide).grid(row=r, column=2, sticky="e", **p)
        ttk.Separator(f, orient="horizontal").grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=8)

        r = 3
        ttk.Label(f, text="刷新间隔(秒):").grid(row=r, column=0, sticky="w", **p)
        self.var_delay = tk.DoubleVar(value=DEFAULT_REFRESH_DELAY)
        ttk.Spinbox(f, from_=0.5, to=60, increment=0.5, textvariable=self.var_delay, width=6).grid(row=r, column=1, sticky="w", **p)

        r += 1
        ttk.Label(f, text="最大轮数:").grid(row=r, column=0, sticky="w", **p)
        self.var_rounds = tk.IntVar(value=DEFAULT_MAX_ROUNDS)
        ttk.Spinbox(f, from_=0, to=999, textvariable=self.var_rounds, width=6).grid(row=r, column=1, sticky="w", **p)
        ttk.Label(f, text="(0=无限)").grid(row=r, column=2, sticky="w", **p)

        r += 1
        ttk.Label(f, text="操作延迟(ms):").grid(row=r, column=0, sticky="w", **p)
        self.var_act = tk.IntVar(value=DEFAULT_ACTION_DELAY)
        ttk.Spinbox(f, from_=100, to=2000, increment=50, textvariable=self.var_act, width=6).grid(row=r, column=1, sticky="w", **p)
        ttk.Separator(f, orient="horizontal").grid(row=6, column=0, columnspan=3, sticky="ew", padx=8, pady=8)

        r = 7
        nb = ttk.Notebook(f)
        nb.grid(row=r, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 0))

        iv_tab = ttk.Frame(nb, padding=5)
        nb.add(iv_tab, text="IV级武装")
        self.var_iv_mode = tk.StringVar(value="filter")
        ttk.Radiobutton(iv_tab, text="购买所有 4 级武装", variable=self.var_iv_mode, value="all").grid(row=0, column=0, columnspan=3, sticky="w", pady=2)
        ttk.Radiobutton(iv_tab, text="按勾选购买 4 级武装", variable=self.var_iv_mode, value="filter").grid(row=1, column=0, sticky="w", pady=2)
        self.iv_fold_btn = ttk.Button(iv_tab, text="▼ 折叠", width=7, command=self._toggle_iv_fold)
        self.iv_fold_btn.grid(row=1, column=1, sticky="e", padx=4, pady=2)
        ttk.Radiobutton(iv_tab, text="不购买 4 级武装", variable=self.var_iv_mode, value="none").grid(row=2, column=0, columnspan=3, sticky="w", pady=2)

        self.iv_cb_frame = ttk.Frame(iv_tab)
        self.iv_cb_frame.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.iv_arm_vars = {}
        for i, name in enumerate(ARMAMENT_NAMES):
            rr = i // 3
            cc = i % 3
            var = tk.BooleanVar(value=name in DEFAULT_CHECKED)
            self.iv_arm_vars[name] = var
            ttk.Checkbutton(self.iv_cb_frame, text=name, variable=var).grid(row=rr, column=cc, sticky="w", padx=(0, 8), pady=1)
            var.trace_add("write", lambda *_: self._schedule_save())

        iii_tab = ttk.Frame(nb, padding=5)
        nb.add(iii_tab, text="I~III级武装")
        self.var_i_iii_enabled = tk.BooleanVar(value=True)
        ttk.Radiobutton(iii_tab, text="购买勾选的 I~III 级武装", variable=self.var_i_iii_enabled, value=True).grid(row=0, column=0, sticky="w", pady=2)
        self.iii_fold_btn = ttk.Button(iii_tab, text="▼ 折叠", width=7, command=self._toggle_iii_fold)
        self.iii_fold_btn.grid(row=0, column=1, sticky="e", padx=4, pady=2)
        ttk.Radiobutton(iii_tab, text="不购买 I~III 级武装", variable=self.var_i_iii_enabled, value=False).grid(row=1, column=0, columnspan=3, sticky="w", pady=2)

        self.iii_cb_frame = ttk.Frame(iii_tab)
        self.iii_cb_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.i_iii_arm_vars = {}
        for i, name in enumerate(ARMAMENT_NAMES):
            rr = i // 3
            cc = i % 3
            var = tk.BooleanVar(value=name in DEFAULT_CHECKED)
            self.i_iii_arm_vars[name] = var
            ttk.Checkbutton(self.iii_cb_frame, text=name, variable=var).grid(row=rr, column=cc, sticky="w", padx=(0, 8), pady=1)
            var.trace_add("write", lambda *_: self._schedule_save())

        self._iv_folded = False
        self._iii_folded = False

        self.var_iv_mode.trace_add("write", self._on_iv_mode_changed)
        self.var_i_iii_enabled.trace_add("write", self._on_i_iii_enabled_changed)
        self.var_delay.trace_add("write", lambda *_: self._schedule_save())
        self.var_rounds.trace_add("write", lambda *_: self._schedule_save())
        self.var_act.trace_add("write", lambda *_: self._schedule_save())

        sep = r + 1
        self.lbl_warn = ttk.Label(f, text="", foreground="red")
        self.lbl_warn.grid(row=sep, column=0, columnspan=3, sticky="w", padx=8)
        ttk.Separator(f, orient="horizontal").grid(row=sep + 1, column=0, columnspan=3, sticky="ew", padx=8, pady=8)

        bf = ttk.Frame(f)
        bf.grid(row=sep + 2, column=0, columnspan=3, sticky="ew", **p)
        self.btn_start = ttk.Button(bf, text="▶ 开始", command=self._start, width=12)
        self.btn_start.pack(side=tk.LEFT, padx=4)
        self.btn_stop = ttk.Button(bf, text="■ 停止", command=self._stop, width=12, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=4)
        ttk.Label(bf, text="按 F8 停止", foreground="gray").pack(side=tk.LEFT, padx=8)

        self.log = scrolledtext.ScrolledText(f, width=55, height=16, font=("Consolas", 9), state="disabled", wrap=tk.WORD)
        self.log.grid(row=sep + 3, column=0, columnspan=3, sticky="nsew", **p)
        f.rowconfigure(sep + 3, weight=1)
        f.columnconfigure(1, weight=1)

    def _toggle_iv_fold(self):
        self._iv_folded = not self._iv_folded
        if self._iv_folded:
            self.iv_fold_btn.config(text="▶ 展开")
            self.iv_cb_frame.grid_forget()
        else:
            self.iv_fold_btn.config(text="▼ 折叠")
            self.iv_cb_frame.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def _toggle_iii_fold(self):
        self._iii_folded = not self._iii_folded
        if self._iii_folded:
            self.iii_fold_btn.config(text="▶ 展开")
            self.iii_cb_frame.grid_forget()
        else:
            self.iii_fold_btn.config(text="▼ 折叠")
            self.iii_cb_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def _on_iv_mode_changed(self, *_):
        mode = self.var_iv_mode.get()
        if mode == "filter":
            self.iv_fold_btn.grid(row=1, column=1, sticky="e", padx=4, pady=2)
            if not self._iv_folded:
                self.iv_cb_frame.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))
        else:
            self.iv_fold_btn.grid_forget()
            self.iv_cb_frame.grid_forget()
        self._schedule_save()

    def _on_i_iii_enabled_changed(self, *_):
        if self.var_i_iii_enabled.get():
            self.iii_fold_btn.grid(row=0, column=1, sticky="e", padx=4, pady=2)
            if not self._iii_folded:
                self.iii_cb_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        else:
            self.iii_fold_btn.grid_forget()
            self.iii_cb_frame.grid_forget()
        self._schedule_save()

    def _schedule_save(self):
        if getattr(self, "_skip_save", False):
            return
        if getattr(self, "_save_pending", False):
            return
        self._save_pending = True
        self.root.after(500, self._do_save)

    def _do_save(self):
        self._save_pending = False
        self._save_state()

    _save_pending = False

    def _restore_state(self):
        self._skip_save = True
        try:
            c = self.config_data
            m = c.get("iv_mode", "filter")
            self.var_iv_mode.set(m if m in ("all", "filter", "none") else "filter")
            if c.get("iv_arms"):
                for n, checked in c["iv_arms"].items():
                    if n in self.iv_arm_vars:
                        self.iv_arm_vars[n].set(checked)
            self.var_i_iii_enabled.set(c.get("i_iii_enabled", True))
            if c.get("i_iii_arms"):
                for n, checked in c["i_iii_arms"].items():
                    if n in self.i_iii_arm_vars:
                        self.i_iii_arm_vars[n].set(checked)
            self.var_delay.set(c.get("refresh_delay", DEFAULT_REFRESH_DELAY))
            self.var_rounds.set(c.get("max_rounds", DEFAULT_MAX_ROUNDS))
            self.var_act.set(c.get("action_delay", DEFAULT_ACTION_DELAY))
            has = c.get("cards_rect") is not None and c.get("refresh_rect") is not None
            self._q(f"配置: {'已就绪' if has else '请配置卡片+刷新按钮区域'}")
            if not has:
                self.lbl_warn.config(text="请先配置武装卡片区域和刷新按钮区域！")
        finally:
            self._skip_save = False

    def _show_guide(self):
        import os
        top = tk.Toplevel(self.root)
        top.title("使用指南")
        top.resizable(False, False)
        top.transient(self.root)
        try:
            top.attributes("-topmost", True)
        except:
            pass

        # Load GIF from templates/ (bundled in EXE)
        gif_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "guide.gif")
        if not os.path.exists(gif_path):
            import sys
            if getattr(sys, "frozen", False):
                gif_path = os.path.join(sys._MEIPASS, "templates", "guide.gif")
        frames = []
        delay = 100
        if os.path.exists(gif_path):
            try:
                from PIL import Image, ImageSequence, ImageTk
                img = Image.open(gif_path)
                for frame in ImageSequence.Iterator(img):
                    frames.append(ImageTk.PhotoImage(frame.copy().convert("RGBA")))
                delay = img.info.get("duration", 100)
                img.close()
            except Exception:
                pass

        if frames:
            lbl_img = tk.Label(top, image=frames[0])
            lbl_img.image = frames[0]
            lbl_img.pack(padx=10, pady=10)
            idx = [0]
            def animate():
                idx[0] = (idx[0] + 1) % len(frames)
                lbl_img.configure(image=frames[idx[0]])
                top.after(delay, animate)
            top.after(delay, animate)

        text_frame = ttk.Frame(top, padding=10)
        text_frame.pack(fill=tk.BOTH, expand=True)
        guide_text = (
            "① 右键管理员运行 EXE\n\n"
            "② 游戏设置 720p 分辨率 + 窗口模式\n\n"
            "③ 点「配置区域」→ 框选卡片+刷新按钮\n"
            "   游戏窗口移动后需重新配置\n\n"
            "④ 选择 IV级/I~III级 策略 + 勾选武装\n\n"
            "⑤ 点「▶ 开始」\n\n"
            "⑥ 按 F8 停止"
        )
        ttk.Label(text_frame, text=guide_text, font=("Microsoft YaHei", 10), justify=tk.LEFT).pack()
        ttk.Button(text_frame, text="关闭", command=top.destroy).pack(pady=(10, 0))

        top.update_idletasks()
        sw = top.winfo_screenwidth()
        sh = top.winfo_screenheight()
        ww = top.winfo_reqwidth()
        wh = top.winfo_reqheight()
        top.geometry(f"+{(sw-ww)//2}+{(sh-wh)//2}")

        top.wait_window()

    def _save_state(self):
        save_settings({
            "iv_mode": self.var_iv_mode.get(),
            "iv_arms": {n: v.get() for n, v in self.iv_arm_vars.items()},
            "i_iii_enabled": self.var_i_iii_enabled.get(),
            "i_iii_arms": {n: v.get() for n, v in self.i_iii_arm_vars.items()},
            "refresh_delay": self.var_delay.get(),
            "max_rounds": self.var_rounds.get(),
            "action_delay": self.var_act.get(),
        })

    def _show_reference_image(self, title, image_name, label_text):
        """Show a reference image popup before region selection. Returns True=proceed, None=cancel."""
        from PIL import Image, ImageTk

        top = tk.Toplevel(self.root)
        top.title(title)
        top.resizable(False, False)
        top.transient(self.root)
        try:
            top.attributes("-topmost", True)
        except:
            pass

        base = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, "frozen", False):
            img_path = os.path.join(sys._MEIPASS, "templates", image_name)
            if not os.path.exists(img_path):
                img_path = os.path.join(base, "templates", image_name)
        else:
            img_path = os.path.join(base, "templates", image_name)
        if os.path.exists(img_path):
            img = Image.open(img_path)
            w, h = img.size
            screen_w = self.root.winfo_screenwidth()
            if w > screen_w * 0.6:
                scale = screen_w * 0.6 / w
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
            lbl = tk.Label(top, image=tk_img)
            lbl.image = tk_img
            lbl.pack(padx=10, pady=10)

        ttk.Label(top, text=label_text, font=("Microsoft YaHei", 10)).pack(pady=(0, 10))

        result = [None]

        def proceed():
            result[0] = True
            top.destroy()

        def cancel():
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", cancel)

        bf = ttk.Frame(top, padding=5)
        bf.pack()
        ttk.Button(bf, text="开始框选", command=proceed).pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text="取消", command=cancel).pack(side=tk.LEFT, padx=5)

        top.update_idletasks()
        top.geometry(f"+{(top.winfo_screenwidth() - top.winfo_reqwidth()) // 2}+{(top.winfo_screenheight() - top.winfo_reqheight()) // 2}")
        top.wait_window()
        return result[0]

    def _show_area_preview(self, title, rect, show_grid=False):
        """Show a preview of the selected area with optional 3x2 grid overlay."""
        import mss, cv2, numpy as np
        x, y, w, h = rect

        with mss.mss() as sct:
            raw = sct.grab({"top": y, "left": x, "width": w, "height": h})
        frame = np.array(raw)[:, :, :3].copy()

        if show_grid:
            cw, ch = w // 3, h // 2
            for row in range(2):
                for col in range(3):
                    fx1, fy1 = col * cw, row * ch
                    fx2, fy2 = fx1 + cw, fy1 + ch
                    cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), (0, 0, 255), 2)
                    cv2.putText(frame, str(row * 3 + col + 1), (fx1 + 5, fy1 + 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # Resize for display if too large
        screen_h = self.root.winfo_screenheight()
        max_h = int(screen_h * 0.5)
        if h > max_h:
            scale = max_h / h
            frame = cv2.resize(frame, (int(w * scale), max_h))

        from PIL import Image, ImageTk
        img = Image.fromarray(frame[:, :, ::-1])
        tk_img = ImageTk.PhotoImage(img)

        top = tk.Toplevel(self.root)
        top.title(title)
        top.resizable(False, False)
        top.transient(self.root)
        top.focus_force()
        try:
            top.attributes("-topmost", True)
        except:
            pass

        lbl = tk.Label(top, image=tk_img)
        lbl.image = tk_img
        lbl.pack(padx=5, pady=5)

        result = [None]  # None=cancel, True=confirm, False=retry

        def confirm():
            result[0] = True
            top.destroy()

        def retry():
            result[0] = False
            top.destroy()

        def cancel():
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", cancel)

        bf = ttk.Frame(top, padding=5)
        bf.pack()
        ttk.Button(bf, text=u"✓ 确认", command=confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text=u"↺ 重选", command=retry).pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text=u"✕ 取消", command=cancel).pack(side=tk.LEFT, padx=5)

        top.update_idletasks()
        top.geometry(f"+{(top.winfo_screenwidth() - top.winfo_reqwidth()) // 2}+{(top.winfo_screenheight() - top.winfo_reqheight()) // 2}")
        top.wait_window()
        return result[0]

    def _select_regions(self):
        # Step 1: Reference + select cards
        self.root.deiconify()
        self.root.lift()
        if not self._show_reference_image("参考：6个武装卡片", "ref_cards.png",
                                          "⚠ 请只框选这 6 个武装卡片，不要框选其他区域"):
            self._q("已取消配置")
            return
        self.root.iconify()
        time.sleep(0.3)
        while True:
            sel = RegionSelector("6个武装卡片区域")
            cards = sel.wait()
            if cards is None:
                self._q("已取消卡片配置")
                self.root.deiconify()
                return
            self.root.deiconify()
            self.root.lift()
            r = self._show_area_preview("确认卡片区域", cards, show_grid=True)
            if r is True:
                break
            if r is None:
                self._q("已取消卡片配置")
                return
            # Retry: go back to selector
            self.root.iconify()
            time.sleep(0.3)

        # Step 2: Reference + select refresh button
        self.root.deiconify()
        self.root.lift()
        if not self._show_reference_image("参考：刷新按钮", "ref_refresh.png",
                                          "请框选右下角的刷新按钮"):
            self._q("已取消配置")
            return
        self.root.iconify()
        time.sleep(0.3)
        while True:
            sel2 = RegionSelector("刷新按钮区域")
            btn = sel2.wait()
            if btn is None:
                self._q("已取消刷新配置")
                self.root.deiconify()
                return
            self.root.deiconify()
            self.root.lift()
            r = self._show_area_preview("确认刷新按钮", btn)
            if r is True:
                break
            if r is None:
                self._q("已取消刷新配置")
                return
            # Retry

        self.root.deiconify()
        self.config_data["cards_rect"] = list(cards)
        self.config_data["refresh_rect"] = list(btn)
        save_config(self.config_data)
        self.lbl_warn.config(text="")
        self._q("配置已保存")

    def _start(self):
        if self.running:
            return
        cards = self.config_data.get("cards_rect")
        refresh_rect = self.config_data.get("refresh_rect")
        if not cards or not refresh_rect or len(refresh_rect) < 4 or refresh_rect[2] <= 0:
            self.lbl_warn.config(text="请先配置武装卡片区域和刷新按钮区域！")
            return
        self.lbl_warn.config(text="")
        self.running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._save_state()
        s = {
            "delay": self.var_delay.get(),
            "rounds": self.var_rounds.get(),
            "act": self.var_act.get(),
            "iv_mode": self.var_iv_mode.get(),
            "iv_arms": {n for n, v in self.iv_arm_vars.items() if v.get()},
            "i_iii_enabled": self.var_i_iii_enabled.get(),
            "i_iii_arms": {n for n, v in self.i_iii_arm_vars.items() if v.get()},
        }
        iv_label = {"all": "IV全买", "filter": "IV勾选", "none": "IV不买"}.get(s["iv_mode"], "?")
        iii_label = "I~III勾选" if s["i_iii_enabled"] else "I~III不买"
        self._q(f"开始 | {iv_label} + {iii_label} | 最大{s['rounds']}轮")
        reset_debug()
        self.worker_thread = threading.Thread(target=self._worker, args=(s,), daemon=True)
        self.worker_thread.start()

    def _stop(self):
        self.running = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self._q("停止中...")

    def _poll_f8(self):
        if ctypes.windll.user32.GetAsyncKeyState(0x77) & 0x8000:
            self._stop()
        self.root.after(50, self._poll_f8)

    def _on_close(self):
        self.running = False
        self._stop_cpu = True
        self._save_state()
        self.root.destroy()

    def _monitor_cpu(self):
        pass  # disabled

    def _q(self, msg):
        self.log_queue.put(msg)

    def _poll_log(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if msg == "__STOP__":
                    self.btn_start.config(state="normal")
                    self.btn_stop.config(state="disabled")
                    continue
                self.log.config(state="normal")
                ts = time.strftime("%H:%M:%S")
                self.log.insert(tk.END, f"[{ts}] {msg}\n")
                self.log.see(tk.END)
                self.log.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log)

    def _log(self, msg):
        self._q(msg)

    def _worker(self, s):
        rounds = 0
        cr = self.config_data["cards_rect"]
        rr = self.config_data["refresh_rect"]
        card_rects = get_card_rects(cr)

        if len(card_rects) < CARD_COUNT:
            self._q("卡片区域异常，请重新配置")
            self._q("__STOP__")
            return

        while self.running:
            if s["rounds"] > 0 and rounds >= s["rounds"]:
                self._q(f"已完成 {s['rounds']} 轮")
                break
            rounds += 1
            self._q(f"--- 第 {rounds} 轮 ---")

            try:
                import ctypes
                ctypes.windll.user32.SetCursorPos(0, 0)
                time.sleep(0.3)
                _, _, arrays = capture_card_regions(cr)
                # TEMP: save raw card area screenshot each round
                # import mss, cv2, os, numpy as np
                # ss_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local", "screenshots")
                # os.makedirs(ss_path, exist_ok=True)
                # with mss.mss() as sct:
                #     raw = sct.grab({"top": cr[1], "left": cr[0], "width": cr[2], "height": cr[3]})
                # frame = np.array(raw)[:, :, :3]
                # out = os.path.join(ss_path, f"{time.strftime('%H%M%S')}_{rounds}.png")
                # cv2.imwrite(out, frame)
                if len(arrays) < CARD_COUNT:
                    self._q("截图异常，跳过本轮")
                    continue
                buy_list = []

                t_ocr_start = time.time()
                for i in range(CARD_COUNT):
                    arr = arrays[i]
                    rec = card_rects[i]
                    cx = rec["x"] + rec["w"] // 2
                    cy = rec["y"] + rec["h"] // 2

                    if arr is None or arr.size == 0:
                        self._q(f"  #{i + 1}: 空 @({cx},{cy})")
                        continue

                    if is_sold_out(arr):
                        self._q(f"  #{i + 1}: 已售 @({cx},{cy})")
                        continue

                    # OCR: name + level (single call)
                    name, price, level = ocr_card(arr)

                    purp = "purp" if level == 4 else ""
                    price_str = price if price else "?"

                    if level == 4:
                        if s["iv_mode"] == "all":
                            buy_list.append(i)
                            act = "IV:全->买"
                        elif s["iv_mode"] == "filter":
                            if name in s["iv_arms"]:
                                buy_list.append(i)
                                act = "IV:勾->买"
                            else:
                                act = "IV:勾->跳"
                        else:
                            act = "IV:不买"
                    else:
                        if s["i_iii_enabled"]:
                            if name in s["i_iii_arms"]:
                                buy_list.append(i)
                                act = "I~III:勾->买"
                            else:
                                act = "I~III:勾->跳"
                        else:
                            act = "I~III:不买"

                    self._q(f"  #{i + 1}: {name} {price_str} {purp} | {act} @({cx},{cy})")

                t_ocr = (time.time() - t_ocr_start) * 1000
                t_act = 0

                if buy_list:
                    t0 = time.time()
                    for idx in buy_list:
                        if not self.running:
                            break
                        rec = card_rects[idx]
                        self._q(f"▶ 买 #{idx + 1}")
                        buy_card(rec["x"] + rec["w"] // 2, rec["y"] + rec["h"] // 2, s["act"])
                    t_act = (time.time() - t0) * 1000
                else:
                    self._q("本轮无")

                self._q(f"【耗时】OCR {t_ocr:.0f}ms | 购买 {t_act:.0f}ms | 总 {t_ocr+t_act:.0f}ms")

                if self.running:
                    self._q("刷新")
                    refresh(rr[0] + rr[2] // 2, rr[1] + rr[3] // 2, s["act"])

                if self.running:
                    time.sleep(s["delay"])

            except Exception as e:
                self._q(f"错误: {e}")
                self._q(traceback.format_exc()[-300:])

        self.running = False
        self._q("已停止")
        self._q("__STOP__")

    def run(self):
        self.root.mainloop()
