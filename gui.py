import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import time
import traceback
import ctypes

from constants import (
    ARMAMENT_NAMES, CARD_COUNT,
    DEFAULT_REFRESH_DELAY, DEFAULT_MAX_ROUNDS, DEFAULT_ACTION_DELAY,
)
from config import load_config, save_config, get_card_rects, save_settings
from capture import capture_card_regions, reset_debug
from detector import is_sold_out, is_iv_level, matches_armament
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

        self.log_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
        self.config_data = load_config()
        set_log(self._log)
        self._build_ui()
        self._restore_state()
        self._poll_log()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(0, self._poll_f8)

    def _build_ui(self):
        p = {"padx": 8, "pady": 4}
        f = ttk.Frame(self.root, padding=10)
        f.pack(fill=tk.BOTH, expand=True)

        r = 0
        ttk.Label(f, text="坐标配置:", font=("Microsoft YaHei", 9, "bold")).grid(row=r, column=0, sticky="w", **p)
        ttk.Button(f, text="配置区域", command=self._select_regions).grid(row=r, column=1, columnspan=2, sticky="ew", **p)
        ttk.Separator(f, orient="horizontal").grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=8)

        r = 3
        ttk.Label(f, text="刷新间隔(秒):").grid(row=r, column=0, sticky="w", **p)
        self.var_delay = tk.IntVar(value=DEFAULT_REFRESH_DELAY)
        ttk.Spinbox(f, from_=1, to=60, textvariable=self.var_delay, width=6).grid(row=r, column=1, sticky="w", **p)

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
        self.var_iv = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="IV级紫色全买 + 其他按勾选武装", variable=self.var_iv).grid(row=r, column=0, columnspan=3, sticky="w", **p)

        r = 8
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

    def _on_arm(self, *_):
        if self._syncing:
            return
        self._syncing = True
        try:
            self.var_all.set(all(v.get() for v in self.arm_vars.values()))
        finally:
            self._syncing = False

    def _selected_arms(self):
        return [n for n, v in self.arm_vars.items() if v.get()]

    def _restore_state(self):
        c = self.config_data
        if c.get("iv_only"):
            self.var_iv.set(True)
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

    def _save_state(self):
        save_settings({
            "iv_only": self.var_iv.get(),
            "arms": {n: v.get() for n, v in self.arm_vars.items()},
            "refresh_delay": self.var_delay.get(),
            "max_rounds": self.var_rounds.get(),
            "action_delay": self.var_act.get(),
        })

    def _select_regions(self):
        self._q("请拖拽框选 6个武装卡片的整体区域...")
        self.root.iconify()
        time.sleep(0.3)
        sel = RegionSelector("6个武装卡片区域")
        cards = sel.wait()
        if cards is None:
            self.root.deiconify()
            self._q("已取消")
            return
        self.root.iconify()
        time.sleep(0.3)
        sel2 = RegionSelector("刷新按钮区域")
        btn = sel2.wait()
        self.root.deiconify()
        self.config_data["cards_rect"] = list(cards)
        if btn:
            self.config_data["refresh_rect"] = list(btn)
        save_config(self.config_data)
        self.lbl_warn.config(text="")
        self._q(f"已保存: 卡片={cards}, 刷新={btn or '未选'}")

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
        mode = "仅IV级" if s["iv"] else ("全买" if len(s["arms"]) == len(ARMAMENT_NAMES) else f"指定:{s['arms']}")
        self._q(f"开始 | 模式={mode} | 最大{s['rounds']}轮")
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
        self._save_state()
        self.root.destroy()

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
                _, _, arrays = capture_card_regions(cr)
                if len(arrays) < CARD_COUNT:
                    self._q("截图异常，跳过本轮")
                    continue
                buy_list = []

                for i in range(CARD_COUNT):
                    arr = arrays[i]
                    rec = card_rects[i]
                    cx = rec["x"] + rec["w"] // 2
                    cy = rec["y"] + rec["h"] // 2

                    if arr is None or arr.size == 0:
                        self._q(f"  #{i + 1}: 空 @({cx},{cy})")
                        continue

                    sold, gray, ts, tc = is_sold_out(arr)
                    if sold:
                        self._q(f"  #{i + 1}: 已售(g={gray},t={ts}) @({cx},{cy})")
                        continue

                    if s["iv"]:
                        if is_iv_level(arr):
                            buy_list.append(i)
                            self._q(f"  #{i + 1}: IV级 ✓ @({cx},{cy})")
                        elif len(s["arms"]) == len(ARMAMENT_NAMES):
                            buy_list.append(i)
                            self._q(f"  #{i + 1}: 可购 @({cx},{cy})")
                        else:
                            ok, name, conf = matches_armament(arr, s["arms"])
                            if ok:
                                buy_list.append(i)
                                self._q(f"  #{i + 1}: {name} c={conf:.2f} @({cx},{cy})")
                            else:
                                self._q(f"  #{i + 1}: 未匹配 @({cx},{cy})")
                    elif len(s["arms"]) == len(ARMAMENT_NAMES):
                        buy_list.append(i)
                        self._q(f"  #{i + 1}: 可购 @({cx},{cy})")
                    else:
                        ok, name, conf = matches_armament(arr, s["arms"])
                        if ok:
                            buy_list.append(i)
                            self._q(f"  #{i + 1}: {name} c={conf:.2f} @({cx},{cy})")
                        else:
                            self._q(f"  #{i + 1}: 未匹配 @({cx},{cy})")

                if buy_list:
                    for idx in buy_list:
                        if not self.running:
                            break
                        rec = card_rects[idx]
                        self._q(f"▶ 买 #{idx + 1}")
                        buy_card(rec["x"] + rec["w"] // 2, rec["y"] + rec["h"] // 2, s["act"])
                else:
                    self._q("本轮无")

                if self.running:
                    self._q("刷新")
                    refresh(rr[0] + rr[2] // 2, rr[1] + rr[3] // 2, s["act"])

                for _ in range(s["delay"]):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                self._q(f"错误: {e}")
                self._q(traceback.format_exc()[-300:])

        self.running = False
        self._q("已停止")
        self._q("__STOP__")

    def run(self):
        self.root.mainloop()
