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
from config import load_config, save_config, get_card_rects, save_settings
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
        self.var_iv = tk.StringVar(value="all")
        ttk.Label(f, text="IV 级选择:", font=("Microsoft YaHei", 9, "bold")).grid(row=r, column=0, columnspan=3, sticky="w", **p)
        ttk.Radiobutton(f, text="购买所有 4 级紫色武装", variable=self.var_iv, value="all").grid(row=r + 1, column=0, columnspan=3, sticky="w", padx=24, pady=4)
        ttk.Radiobutton(f, text="仅购买勾选的武装", variable=self.var_iv, value="filter").grid(row=r + 2, column=0, columnspan=3, sticky="w", padx=24, pady=4)
        ttk.Radiobutton(f, text="不购买 4 级紫色武装", variable=self.var_iv, value="none").grid(row=r + 3, column=0, columnspan=3, sticky="w", padx=24, pady=4)

        r = 11
        ttk.Label(f, text="武装选择:", font=("Microsoft YaHei", 9, "bold")).grid(row=r, column=0, columnspan=3, sticky="w", **p)

        self.var_all = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="全选", variable=self.var_all).grid(row=r + 1, column=0, sticky="w", **p)

        self.arm_vars = {}
        cols = 3
        for i, name in enumerate(ARMAMENT_NAMES):
            rr = r + 2 + i // cols
            cc = i % cols
            var = tk.BooleanVar(value=True)
            self.arm_vars[name] = var
            ttk.Checkbutton(f, text=name, variable=var).grid(row=rr, column=cc, sticky="w", padx=(24 if cc == 0 else 4, 4), pady=1)

        self.var_all.trace_add("write", self._on_all)
        for v in self.arm_vars.values():
            v.trace_add("write", self._on_arm)
        self.var_iv.trace_add("write", lambda *_: self._schedule_save())
        self.var_delay.trace_add("write", lambda *_: self._schedule_save())
        self.var_rounds.trace_add("write", lambda *_: self._schedule_save())
        self.var_act.trace_add("write", lambda *_: self._schedule_save())

        sep = r + 2 + (len(ARMAMENT_NAMES) + cols - 1) // cols
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

    _syncing = False

    def _on_all(self, *_):
        if self._syncing:
            return
        self._syncing = True
        try:
            v = self.var_all.get()
            for var in self.arm_vars.values():
                var.set(v)
        finally:
            self._syncing = False
        self._schedule_save()

    def _on_arm(self, *_):
        if self._syncing:
            return
        self._syncing = True
        try:
            self.var_all.set(all(v.get() for v in self.arm_vars.values()))
        finally:
            self._syncing = False
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

    def _selected_arms(self):
        return [n for n, v in self.arm_vars.items() if v.get()]

    def _restore_state(self):
        self._skip_save = True
        try:
            c = self.config_data
            m = c.get("iv_mode", "all")
            self.var_iv.set(m if m in ("all", "filter", "none") else "all")
            if c.get("arms"):
                for n, checked in c["arms"].items():
                    if n in self.arm_vars:
                        self.arm_vars[n].set(checked)
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
            "④ 选择 IV 模式 + 勾选武装\n\n"
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
            "iv_mode": self.var_iv.get(),
            "arms": {n: v.get() for n, v in self.arm_vars.items()},
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
            "iv": self.var_iv.get(),
            "arms": self._selected_arms(),
        }
        iv_label = {"all": "IV全买", "filter": "IV仅勾选", "none": "不买IV", "": "无IV模式"}.get(s["iv"], "?")
        mode = iv_label + (" + 全买" if len(s["arms"]) == len(ARMAMENT_NAMES) else (" + 指定" if s["arms"] else " + 无"))
        self._q(f"开始 | {mode} | 最大{s['rounds']}轮")
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
                    in_list = name in s["arms"] if s["arms"] else False
                    all_checked = len(s["arms"]) == len(ARMAMENT_NAMES)

                    purp = "purp" if level == 4 else ""
                    price_str = price if price else "?"
                    mode = {"all": "IV全", "filter": "IV仅勾", "none": "IV跳", "": "无"}.get(s["iv"], "?")

                    if s["iv"] == "all":
                        if level == 4 or all_checked or in_list:
                            buy_list.append(i)
                            act = "买"
                        else:
                            act = "未勾"
                    elif s["iv"] == "filter":
                        if all_checked or in_list:
                            buy_list.append(i)
                            act = "买"
                        else:
                            act = "未勾"
                    elif s["iv"] == "none":
                        if level == 4:
                            act = "跳IV"
                        elif all_checked or in_list:
                            buy_list.append(i)
                            act = "买"
                        else:
                            act = "未勾"
                    else:
                        if all_checked or in_list:
                            buy_list.append(i)
                            act = "买"
                        else:
                            act = "未勾"

                    self._q(f"  #{i + 1}: {name} {price_str} {purp} | {mode}->{act} @({cx},{cy})")

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
