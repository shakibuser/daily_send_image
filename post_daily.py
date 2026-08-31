#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
انتخاب تصادفی یک عکس بکر (بدون هیچ تغییری) از پوشه images، و ارسال آن به
همراه کپشن متنی (نه نوشته‌شده روی عکس) به کانال تلگرام.
اجرا هر روز ساعت ۶ صبح به وقت تهران توسط GitHub Actions.
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

# متن ثابتی که هر روز همراه نام روز هفته نوشته می‌شود
FIXED_CAPTION = "صبح بخیر ایران , صبح بخیر ایرانی"

# خط آدرس کانال که همیشه در انتهای کپشن، بعد از یک خط خالی، اضافه می‌شود
# با نویسه LRM (‎\u200e‎) شروع می‌شود تا کل خط از چپ به راست نمایش داده شود
# (اول آیدی انگلیسی، بعد بقیه متن) حتی در اپ‌هایی که پیش‌فرض راست‌به‌چپ هستند.
CHANNEL_LINE = "\u200esaba_rasanehh@ || کانال تلگرام صبا رسانه"

# نگاشت نام روزهای هفته به فرم محاوره‌ای خواسته‌شده
WEEKDAY_COLLOQUIAL = {
    "Saturday": "شنبه‌تون",
    "Sunday": "یکشنبه‌تون",
    "Monday": "دوشنبه‌تون",
    "Tuesday": "سه‌شنبه‌تون",
    "Wednesday": "چهارشنبه‌تون",
    "Thursday": "پنجشنبه‌تون",
    "Friday": "جمعه‌تون",
}

# آدرس API رایگان تقویم شمسی (بدون نیاز به کلید) برای دریافت مناسبت روز
CALENDAR_API_URL = "https://pnldev.com/api/calender"

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "@saba_rasanehh")

# ---------- توابع کمکی ----------

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_persian_digits(value) -> str:
    return str(value).translate(PERSIAN_DIGITS)


def get_jalali_date_line() -> tuple[str, jdatetime.date]:
    """ساخت خط «امروز : ...» با تاریخ شمسی و نام روز هفته به فارسی."""
    jdatetime.set_locale("fa_IR")
    j_now = jdatetime.datetime.now()
    weekday_fa = j_now.strftime("%A")
    month_fa = j_now.j_months_fa[j_now.month - 1] if hasattr(j_now, "j_months_fa") else jdatetime.date.j_months_fa[j_now.month - 1]

    day_fa = to_persian_digits(j_now.day)
    year_fa = to_persian_digits(j_now.year)

    line = f"امروز  : {weekday_fa} ، {day_fa} {month_fa} {year_fa}"
    return line, j_now.date()


def get_occasion_line(j_date: jdatetime.date) -> str | None:
    """دریافت مناسبت روز از API رایگان تقویم؛ اگر مناسبتی نبود یا API در دسترس نبود، None برمی‌گرداند."""
    try:
        resp = requests.get(
            CALENDAR_API_URL,
            params={"year": j_date.year, "month": j_date.month, "day": j_date.day},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        events = data.get("result", {}).get("event") or []
        events = [e.strip() for e in events if e and e.strip()]
        if not events:
            return None
        return "مناسبت امروز : " + "، ".join(events)
    except Exception as e:
        print(f"هشدار: دریافت مناسبت روز ناموفق بود ({e}). این بخش از کپشن نادیده گرفته می‌شود.", file=sys.stderr)
        return None


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


def main():
    tehran_now = datetime.now(ZoneInfo("Asia/Tehran"))
    weekday_en = tehran_now.strftime("%A")
    colloquial = WEEKDAY_COLLOQUIAL.get(weekday_en, weekday_en)

    date_line, j_date = get_jalali_date_line()
    occasion_line = get_occasion_line(j_date)

    caption_lines = [FIXED_CAPTION, f"صبح {colloquial} بخیر", date_line]
    if occasion_line:
        caption_lines.append(occasion_line)

    # یک خط خالی و سپس آدرس کانال در انتهای کپشن
    caption_lines.append("")
    caption_lines.append(CHANNEL_LINE)

    caption_text = "\n".join(caption_lines)

    image_path = pick_random_image()
    # عکس کاملاً بکر و بدون تغییر ارسال می‌شود؛ کپشن فقط به‌صورت متن تلگرام درج می‌شود.
    send_to_telegram(image_path, caption_text)


if __name__ == "__main__":
    main()
