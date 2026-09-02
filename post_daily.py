#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
انتخاب تصادفی یک عکس بکر (بدون هیچ تغییری) از پوشه images، و ارسال آن به
همراه یک کپشن متنی گرم و متنوع (نه نوشته‌شده روی عکس) به کانال تلگرام.

کپشن از سه بخش تشکیل شده (با یک سطر خالی بین‌شان):
  ۱) پیام صبحگاهی
  ۲) تاریخ شمسی/قمری و مناسبت روز
  ۳) پیام دوم + امضای ثابت کانال

پیام‌های بخش ۱ و ۳ از فایل‌های متنی ساده در پوشه‌ی messages/ خوانده می‌شوند،
تا اضافه‌کردن جمله‌ی جدید فقط با اضافه‌کردن یک خط به یک فایل متنی ممکن باشد
(بدون نیاز به دست‌زدن به کد پایتون).
"""

import os
import json
import random
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import jdatetime

# ---------- تنظیمات قابل ویرایش ----------

IMAGES_DIR = "images"
USED_LOG_PATH = "used_log.json"
CAPTION_STATE_PATH = "caption_state.json"

OPENING_MESSAGES_DIR = "messages/opening"   # پیام اول (صبحگاهی)
CLOSING_MESSAGES_DIR = "messages/closing"   # پیام دوم (انگیزشی/مطالبه‌گری/سخن بزرگان/...)

# آدرس API رایگان تقویم شمسی (بدون نیاز به کلید) برای دریافت مناسبت روز و تاریخ قمری
CALENDAR_API_URL = "https://pnldev.com/api/calender"

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "@saba_rasanehh")

HIJRI_MONTHS_FA = [
    "محرم", "صفر", "ربیع‌الاول", "ربیع‌الثانی", "جمادی‌الاول", "جمادی‌الثانی",
    "رجب", "شعبان", "رمضان", "شوال", "ذوالقعده", "ذوالحجه",
]

# خط پایانی ثابت (همیشه یکسان، امضای روزانه کانال)
CLOSING_LINE = "صبح‌تان بخیر، تنتان سالم و دل‌تان گرم ❤️"

# خطوط آیدی و لینک کانال؛ با LRM (‎\u200e‎) شروع می‌شوند تا همیشه از چپ به راست
# نمایش داده شوند (چون با کاراکتر انگلیسی/لینک شروع می‌شوند).
CHANNEL_ID_LINE = "\u200e🆔👉 @saba_rasanehh || صبا رسانه"
CHANNEL_LINK_LINE = "\u200e🔗👉 https://t.me/saba_rasanehh"

# ---------- توابع کمکی ----------

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_persian_digits(value) -> str:
    return str(value).translate(PERSIAN_DIGITS)


def get_jalali_now() -> jdatetime.datetime:
    jdatetime.set_locale("fa_IR")
    return jdatetime.datetime.now()


def fetch_calendar_info(j_now: jdatetime.datetime) -> dict:
    """
    یک‌بار به API رایگان تقویم متصل می‌شود و هم مناسبت‌های روز و هم تاریخ
    قمری را برمی‌گرداند. اگر API در دسترس نبود، خروجی خالی (بدون خطا) می‌دهد
    تا ارسال پست هرگز متوقف نشود.
    """
    try:
        resp = requests.get(
            CALENDAR_API_URL,
            params={"year": j_now.year, "month": j_now.month, "day": j_now.day},
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json().get("result", {})
        events = [e.strip() for e in (result.get("event") or []) if e and e.strip()]
        moon = result.get("moon") or {}
        return {"events": events, "moon": moon}
    except Exception as e:
        print(f"هشدار: دریافت اطلاعات تقویم ناموفق بود ({e}). این بخش از کپشن نادیده گرفته می‌شود.", file=sys.stderr)
        return {"events": [], "moon": {}}


def build_date_block(j_now: jdatetime.datetime, calendar_info: dict) -> list[str]:
    """ساخت خطوط بخش دوم کپشن: تاریخ شمسی، تاریخ قمری، و مناسبت (در صورت وجود)."""
    weekday_fa = j_now.strftime("%A")
    month_fa = jdatetime.date.j_months_fa[j_now.month - 1]
    day_fa = to_persian_digits(j_now.day)
    year_fa = to_persian_digits(j_now.year)

    lines = [
        "امروز:",
        f"📅 {weekday_fa} {day_fa} {month_fa} {year_fa}",
    ]

    moon = calendar_info.get("moon") or {}
    if moon.get("day") and moon.get("month"):
        hijri_day_fa = to_persian_digits(moon["day"])
        hijri_month_fa = HIJRI_MONTHS_FA[moon["month"] - 1]
        lines.append(f"🌿 {hijri_day_fa} {hijri_month_fa}")

    events = calendar_info.get("events") or []
    if events:
        lines.append("🎉 " + "، ".join(events))

    return lines


# ---------- بارگذاری استخر پیام‌ها از فایل‌های متنی ساده ----------
#
# ساختار پوشه‌ها:
#   messages/opening/*.txt   -> هر فایل یک «حال‌وهوا»ی پیام اول (مثلاً hope.txt)
#   messages/closing/*.txt   -> هر فایل یک «دسته» از پیام دوم (مثلاً motivational.txt)
#
# داخل هر فایل: هر خط = یک پیام. خط‌های خالی و خط‌هایی که با # شروع می‌شوند
# (توضیح/کامنت) نادیده گرفته می‌شوند. برای اضافه‌کردن پیام جدید، کافی است یک
# خط جدید به فایل مربوطه اضافه شود.


def load_message_pool(directory: str) -> dict:
    """خواندن همه‌ی فایل‌های .txt یک پوشه؛ خروجی: {نام_دسته: [پیام‌ها]}."""
    pool = {}
    if not os.path.isdir(directory):
        return pool
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".txt"):
            continue
        category = filename[:-4]
        path = os.path.join(directory, filename)
        with open(path, "r", encoding="utf-8") as f:
            lines = [
                line.strip() for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
        if lines:
            pool[category] = lines
    return pool


def load_caption_state() -> dict:
    if os.path.exists(CAPTION_STATE_PATH):
        with open(CAPTION_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_caption_state(state: dict) -> None:
    with open(CAPTION_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def pick_message(pool: dict, state: dict, state_key: str) -> str:
    """
    از یک استخر دسته‌بندی‌شده (مثل پیام‌های صبحگاهی یا پیام‌های پایانی)، یک
    دسته‌ی متفاوت از دیروز و یک پیام تصادفیِ استفاده‌نشده از آن انتخاب می‌کند.
    state_key باعث می‌شود پیام اول و پیام دوم کاملاً مستقل از هم بچرخند.
    """
    section_state = state.setdefault(state_key, {"last_category": None, "used": {}})
    categories = list(pool.keys())
    if not categories:
        return ""

    last_category = section_state.get("last_category")
    candidates = [c for c in categories if c != last_category] or categories
    category = random.choice(candidates)

    used = set(section_state.get("used", {}).get(category, []))
    messages = pool[category]
    remaining = [i for i in range(len(messages)) if i not in used]
    if not remaining:
        used = set()
        remaining = list(range(len(messages)))

    idx = random.choice(remaining)
    used.add(idx)

    section_state.setdefault("used", {})[category] = sorted(used)
    section_state["last_category"] = category

    return messages[idx]


def pick_random_image() -> str:
    """انتخاب تصادفی یک عکس (یا گیف متحرک)، با تلاش برای عدم تکرار تا زمانی که همه استفاده شوند."""
    all_images = sorted(
        f for f in os.listdir(IMAGES_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
    )
    if not all_images:
        raise RuntimeError("هیچ عکسی در پوشه images پیدا نشد.")

    used = []
    if os.path.exists(USED_LOG_PATH):
        with open(USED_LOG_PATH, "r", encoding="utf-8") as f:
            used = json.load(f)

    remaining = [f for f in all_images if f not in used]
    if not remaining:
        # یک دور کامل استفاده شد، از نو شروع می‌کنیم
        used = []
        remaining = all_images

    chosen = random.choice(remaining)
    used.append(chosen)
    with open(USED_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(used, f, ensure_ascii=False, indent=2)

    return os.path.join(IMAGES_DIR, chosen)


def send_to_telegram(file_path: str, caption_text: str) -> None:
    is_gif = file_path.lower().endswith(".gif")
    method = "sendAnimation" if is_gif else "sendPhoto"
    field_name = "animation" if is_gif else "photo"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    with open(file_path, "rb") as f:
        resp = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption_text},
            files={field_name: f},
            timeout=120,
        )
    if not resp.ok or not resp.json().get("ok"):
        print("خطا در ارسال به تلگرام:", resp.text, file=sys.stderr)
        sys.exit(1)
    print("پست با موفقیت ارسال شد.")


def build_caption_text() -> str:
    j_now = get_jalali_now()
    calendar_info = fetch_calendar_info(j_now)

    opening_pool = load_message_pool(OPENING_MESSAGES_DIR)
    closing_pool = load_message_pool(CLOSING_MESSAGES_DIR)

    state = load_caption_state()
    opening_message = pick_message(opening_pool, state, "opening")
    closing_message = pick_message(closing_pool, state, "closing")
    save_caption_state(state)

    # بخش ۱: پیام صبحگاهی
    section1 = ["☀️ صبح بخیر ایران؛"]
    if opening_message:
        section1.append(opening_message)

    # بخش ۲: تاریخ و مناسبت
    section2 = build_date_block(j_now, calendar_info)

    # بخش ۳: پیام دوم + امضای کانال
    section3 = []
    if closing_message:
        section3.append(closing_message)
    section3.append(CLOSING_LINE)
    section3.append("")
    section3.append(CHANNEL_ID_LINE)
    section3.append(CHANNEL_LINK_LINE)

    full_text = "\n".join(section1) + "\n\n" + "\n".join(section2) + "\n\n" + "\n".join(section3)
    return full_text


def main():
    caption_text = build_caption_text()
    image_path = pick_random_image()
    # عکس کاملاً بکر و بدون تغییر ارسال می‌شود؛ کپشن فقط به‌صورت متن تلگرام درج می‌شود.
    send_to_telegram(image_path, caption_text)


if __name__ == "__main__":
    main()
