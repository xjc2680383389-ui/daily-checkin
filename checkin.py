#!/usr/bin/env python3
"""每日打卡 — 桌面日历打卡应用
独立运行: python checkin.py
打包exe: pyinstaller --onefile --windowed --name 每日打卡 checkin.py
"""

import customtkinter as ctk
import json
import os
import sys
from datetime import date, timedelta
import calendar
from calendar import monthrange, monthcalendar

# 修复：Python calendar 默认周一起始，与表头「日 一 二 三 四 五 六」错位一天。
# 统一为周日起始后，monthcalendar 的行列与表头、周日红字判断全部对齐。
calendar.setfirstweekday(calendar.SUNDAY)

# ── 配置 ──────────────────────────────────────────────
APP_TITLE = "每日打卡"
WIN_W, WIN_H = 480, 1040  # 修复：620 太矮，内容所需 1007px，底部统计/按钮会被裁掉
DATA_DIR = os.path.join(os.path.expanduser("~"), ".daily-checkin")
DATA_FILE = os.path.join(DATA_DIR, "checkins.json")

# 配色（与 customtkinter blue 主题协调）
WIN_BG = "#f0f2f5"            # 窗口背景
CARD_BG = "#ffffff"           # 卡片/按钮背景
EMPTY_BG = "#e8eaef"          # 空白格背景
CHECKED_COLOR = "#2ecc71"      # 打卡绿
CHECKED_HOVER = "#27ae60"      # 打卡绿(hover)
TODAY_BORDER = "#3498db"       # 今日蓝框
WEEKEND_COLOR = "#e74c3c"      # 周日文字色

WEEKDAYS_CN = ["日", "一", "二", "三", "四", "五", "六"]


# ── 数据持久化 ────────────────────────────────────────
def load_data() -> dict[str, bool]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_data(data: dict[str, bool]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 工具函数 ──────────────────────────────────────────
def date_key(d: date) -> str:
    return d.isoformat()


def calc_streak(data: dict[str, bool], today: date) -> int:
    """计算连续打卡天数（从今天往前数，中断即停）"""
    streak = 0
    d = today
    while True:
        if data.get(date_key(d)):
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak


# ── 主应用 ────────────────────────────────────────────
class CheckinApp:
    def __init__(self):
        # 窗口
        self.window = ctk.CTk()
        self.window.title(APP_TITLE)
        self.window.configure(fg_color=WIN_BG)
        self.window.resizable(False, False)

        # 居中
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - WIN_W) // 2
        y = (self.window.winfo_screenheight() - WIN_H) // 2
        self.window.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        # 图标（尝试设置）
        try:
            self.window.iconbitmap(default="")
        except Exception:
            pass

        # 状态
        self.data = load_data()
        self.today = date.today()
        self.current_year = self.today.year
        self.current_month = self.today.month

        # 构建 UI
        self._build_ui()
        self._render_calendar()
        self._update_stats()

    # ── UI 构建 ───────────────────────────────────
    def _build_ui(self):
        """一次性构建所有静态 UI 部件"""
        # 主容器
        self.main = ctk.CTkFrame(self.window, fg_color="transparent")
        self.main.pack(fill="both", expand=True, padx=16, pady=(16, 12))

        # ── 标题 ──
        title_frame = ctk.CTkFrame(self.main, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            title_frame,
            text="📅 每日打卡",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#2c3e50",
        ).pack(side="left")

        # ── 月份导航 ──
        nav = ctk.CTkFrame(self.main, fg_color="transparent")
        nav.pack(fill="x", pady=(0, 14))

        self.btn_year_prev = ctk.CTkButton(
            nav, text="◀◀", width=36, height=36,
            font=ctk.CTkFont(size=14),
            fg_color="transparent", text_color="#7f8c8d",
            hover_color="#ecf0f1",
            command=lambda: self._navigate(-12),
        )
        self.btn_year_prev.pack(side="left", padx=(0, 2))

        self.btn_month_prev = ctk.CTkButton(
            nav, text="◀", width=36, height=36,
            font=ctk.CTkFont(size=14),
            fg_color="transparent", text_color="#7f8c8d",
            hover_color="#ecf0f1",
            command=lambda: self._navigate(-1),
        )
        self.btn_month_prev.pack(side="left", padx=(0, 8))

        self.label_month = ctk.CTkLabel(
            nav,
            text="",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#2c3e50",
        )
        self.label_month.pack(side="left", expand=True)

        self.btn_month_next = ctk.CTkButton(
            nav, text="▶", width=36, height=36,
            font=ctk.CTkFont(size=14),
            fg_color="transparent", text_color="#7f8c8d",
            hover_color="#ecf0f1",
            command=lambda: self._navigate(1),
        )
        self.btn_month_next.pack(side="right", padx=(0, 2))

        self.btn_year_next = ctk.CTkButton(
            nav, text="▶▶", width=36, height=36,
            font=ctk.CTkFont(size=14),
            fg_color="transparent", text_color="#7f8c8d",
            hover_color="#ecf0f1",
            command=lambda: self._navigate(12),
        )
        self.btn_year_next.pack(side="right", padx=(8, 0))

        # ── 星期标题行 ──
        header_frame = ctk.CTkFrame(self.main, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 6))
        for i, name in enumerate(WEEKDAYS_CN):
            color = WEEKEND_COLOR if i == 0 else ("#e67e22" if i == 6 else "#7f8c8d")
            lbl = ctk.CTkLabel(
                header_frame,
                text=name,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=color,
                width=62,
            )
            lbl.pack(side="left")

        # ── 日历网格容器 ──
        self.cal_grid = ctk.CTkFrame(self.main, fg_color="transparent")
        self.cal_grid.pack(fill="x", pady=(0, 12))

        # 预创建 6×7 按钮矩阵
        self.day_btns: list[list[ctk.CTkButton | None]] = []
        for row in range(6):
            row_frame = ctk.CTkFrame(self.cal_grid, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            btn_row: list[ctk.CTkButton | None] = []
            for col in range(7):
                btn = ctk.CTkButton(
                    row_frame,
                    text="",
                    width=58, height=52,
                    font=ctk.CTkFont(size=16, weight="bold"),
                    corner_radius=8,
                    fg_color=CARD_BG,
                    text_color="#2c3e50",
                    hover_color="#e9ecef",
                    border_width=0,
                    border_color=CARD_BG,
                )
                btn.pack(side="left", padx=2)
                btn_row.append(btn)
            self.day_btns.append(btn_row)

        # ── 统计卡片 ──
        stats_card = ctk.CTkFrame(
            self.main,
            fg_color=CARD_BG,
            corner_radius=12,
            border_width=1,
            border_color="#e9ecef",
        )
        stats_card.pack(fill="x", pady=(0, 12))

        stats_inner = ctk.CTkFrame(stats_card, fg_color="transparent")
        stats_inner.pack(fill="x", padx=16, pady=14)

        # 三列统计
        stats_data = [
            ("🔥", "连续打卡", "streak"),
            ("📅", "本月打卡", "monthly"),
            ("🏆", "总计打卡", "total"),
        ]
        self.stat_labels: dict[str, ctk.CTkLabel] = {}
        self.stat_value_labels: dict[str, ctk.CTkLabel] = {}

        for icon, label, key in stats_data:
            col = ctk.CTkFrame(stats_inner, fg_color="transparent")
            col.pack(side="left", expand=True)

            inner = ctk.CTkFrame(col, fg_color="transparent")
            inner.pack(anchor="center")

            ctk.CTkLabel(
                inner,
                text=f"{icon} {label}",
                font=ctk.CTkFont(size=12),
                text_color="#95a5a6",
            ).pack()

            val_lbl = ctk.CTkLabel(
                inner,
                text="0 天",
                font=ctk.CTkFont(size=22, weight="bold"),
                text_color="#2c3e50",
            )
            val_lbl.pack()
            self.stat_value_labels[key] = val_lbl

        # ── 今天按钮 ──
        self.btn_today = ctk.CTkButton(
            self.main,
            text="📍 回到今天",
            font=ctk.CTkFont(size=14),
            fg_color="#3498db",
            hover_color="#2980b9",
            height=40,
            corner_radius=10,
            command=self._go_today,
        )
        self.btn_today.pack(fill="x")

        # ── 状态栏 ──
        self.status_label = ctk.CTkLabel(
            self.main,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#bdc3c7",
        )
        self.status_label.pack(pady=(6, 0))

    # ── 日历渲染 ─────────────────────────────────
    def _render_calendar(self):
        """根据 current_year/month 渲染日历按钮"""
        self.label_month.configure(text=f"{self.current_year}年 {self.current_month}月")

        cal = monthcalendar(self.current_year, self.current_month)
        # monthcalendar 返回的是 Sun-Sat，与我们的 header 一致

        for row_idx, week in enumerate(cal):
            for col_idx, day in enumerate(week):
                btn = self.day_btns[row_idx][col_idx]
                if day == 0:
                    # 空白天（不属于本月）
                    btn.configure(
                        text="",
                        state="disabled",
                        fg_color=EMPTY_BG,
                        text_color=EMPTY_BG,
                        hover_color=EMPTY_BG,
                        border_width=0,
                        border_color=EMPTY_BG,
                        command=None,
                    )
                else:
                    cell_date = date(self.current_year, self.current_month, day)
                    is_today = cell_date == self.today
                    is_checked = self.data.get(date_key(cell_date), False)
                    is_future = cell_date > self.today
                    is_weekend = col_idx == 0  # 周日

                    # 基础样式
                    if is_checked:
                        bg = CHECKED_COLOR
                        hover_bg = CHECKED_HOVER
                        text_color = "#ffffff"
                    else:
                        bg = CARD_BG
                        hover_bg = "#e9ecef"
                        text_color = WEEKEND_COLOR if is_weekend else "#2c3e50"

                    # 今日边框
                    border_w = 2 if is_today else 0

                    btn.configure(
                        text=str(day),
                        state="normal" if not is_future else "disabled",
                        fg_color=bg,
                        hover_color=hover_bg,
                        text_color=text_color,
                        border_width=border_w,
                        border_color=TODAY_BORDER if is_today else bg,
                        command=(lambda d=cell_date: self._toggle_day(d))
                        if not is_future else None,
                    )

        # 如果不在今天所在月份，显示回到今天按钮
        is_current = (
            self.current_year == self.today.year
            and self.current_month == self.today.month
        )
        self.btn_today.configure(
            text="📍 回到今天",
            state="normal" if not is_current else "disabled",
            fg_color="#3498db" if not is_current else "#bdc3c7",
        )

    # ── 打卡切换 ─────────────────────────────────
    def _toggle_day(self, d: date):
        """点击日期：切换打卡状态"""
        if d > self.today:
            return  # 未来日期不可打卡

        key = date_key(d)
        if self.data.get(key):
            del self.data[key]
            self.status_label.configure(text=f"⏎ 已取消 {d.month}月{d.day}日 打卡")
        else:
            self.data[key] = True
            if d == self.today:
                self.status_label.configure(text=f"✅ 今日打卡成功！继续坚持！")
            else:
                self.status_label.configure(text=f"✅ 已补卡 {d.month}月{d.day}日")

        save_data(self.data)
        self._render_calendar()
        self._update_stats()

    # ── 月份导航 ─────────────────────────────────
    def _navigate(self, delta: int):
        """delta: 月份增量（-1=上月, +1=下月, -12=去年, +12=明年）"""
        total_months = self.current_year * 12 + (self.current_month - 1) + delta
        self.current_year = total_months // 12
        self.current_month = (total_months % 12) + 1
        self._render_calendar()
        self._update_stats()

    # ── 回到今天 ─────────────────────────────────
    def _go_today(self):
        self.current_year = self.today.year
        self.current_month = self.today.month
        self._render_calendar()
        self._update_stats()

    # ── 统计更新 ─────────────────────────────────
    def _update_stats(self):
        # 连续天数
        streak = calc_streak(self.data, self.today)
        self.stat_value_labels["streak"].configure(text=f"{streak} 天")

        # 本月打卡
        monthly = sum(
            1 for k in self.data
            if k.startswith(f"{self.current_year}-{self.current_month:02d}")
        )
        self.stat_value_labels["monthly"].configure(text=f"{monthly} 天")

        # 总计
        total = len(self.data)
        self.stat_value_labels["total"].configure(text=f"{total} 天")

    # ── 启动 ────────────────────────────────────
    def run(self):
        self.window.mainloop()


# ── 入口 ──────────────────────────────────────────────
if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    app = CheckinApp()
    app.run()
