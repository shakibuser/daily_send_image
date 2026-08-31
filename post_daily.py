#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
انتخاب تصادفی یک عکس از پوشه images، افزودن کپشن ثابت + نام روز هفته
زیر عکس، و ارسال به کانال تلگرام.
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
from PIL import Image, ImageDraw, ImageFont, ImageSequence

# ---------- تنظیمات قابل ویرایش ----------

IMAGES_DIR = "images"
FONT_PATH = "fonts/Vazirmatn-Bold.ttf"
USED_LOG_PATH = "used_log.json"

# متن ثابتی که هر روز همراه نام روز هفته نوشته می‌شود
FIXED_CAPTION = "صبح بخیر ایران , صبح بخیر ایرانی"

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


def build_caption_band(width: int, caption_lines: list[str]) -> Image.Image:
    """ساخت نوار مستطیلی مشکی با متن فارسی رویش (ارتفاع بر اساس تعداد خطوط محاسبه می‌شود)."""
    font_size = max(int(width * 0.032), 26)
    font = ImageFont.truetype(FONT_PATH, font_size)
    spacing = int(font_size * 0.45)
    padding = int(font_size * 0.6)

    probe = Image.new("RGB", (width, 10))
    draw = ImageDraw.Draw(probe)

    line_heights = []
    for line in caption_lines:
        bbox = draw.textbbox((0, 0), line, font=font, direction="rtl")
        line_heights.append(bbox[3] - bbox[1])

    band_height = 2 * padding + sum(line_heights) + spacing * (len(caption_lines) - 1)

    band = Image.new("RGB", (width, band_height), (20, 20, 20))
    draw = ImageDraw.Draw(band)

    y = padding
    for line, line_h in zip(caption_lines, line_heights):
        draw.text(
            (width // 2, y),
            line,
            font=font,
            fill=(255, 255, 255),
            anchor="ma",
            direction="rtl",
        )
        y += line_h + spacing

    return band


def build_captioned_static(image_path: str, caption_lines: list[str]) -> str:
    """افزودن نوار کپشن زیر یک عکس ساده (jpg/png/webp) و ذخیره خروجی."""
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    band = build_caption_band(width, caption_lines)
    band_height = band.height

    new_img = Image.new("RGB", (width, height + band_height), (20, 20, 20))
    new_img.paste(img, (0, 0))
    new_img.paste(band, (0, height))

    out_path = "output.jpg"
    new_img.save(out_path, quality=92)
    return out_path


def build_captioned_gif(image_path: str, caption_lines: list[str]) -> str:
    """افزودن نوار کپشن زیر تمام فریم‌های یک گیف متحرک، با حفظ سرعت و تعداد تکرار."""
    src = Image.open(image_path)
    width, height = src.size
    band = build_caption_band(width, caption_lines).convert("RGBA")
    band_height = band.height

    out_frames = []
    durations = []
    for frame in ImageSequence.Iterator(src):
        rgba_frame = frame.convert("RGBA")
        canvas = Image.new("RGBA", (width, height + band_height), (20, 20, 20, 255))
        canvas.paste(rgba_frame, (0, 0))
        canvas.paste(band, (0, height))
        out_frames.append(canvas.convert("RGB"))
        durations.append(frame.info.get("duration", 100))

    out_path = "output.gif"
    out_frames[0].save(
        out_path,
        save_all=True,
        append_images=out_frames[1:],
        duration=durations,
        loop=src.info.get("loop", 0),
        disposal=2,
    )
    return out_path


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

    caption_text = "\n".join(caption_lines)

    image_path = pick_random_image()
    is_gif = image_path.lower().endswith(".gif") and getattr(
        Image.open(image_path), "is_animated", False
    )

    if is_gif:
        out_path = build_captioned_gif(image_path, caption_lines)
    else:
        out_path = build_captioned_static(image_path, caption_lines)

    send_to_telegram(out_path, caption_text)


if __name__ == "__main__":
    main()
