#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
انتخاب تصادفی یک عکس بکر (بدون هیچ تغییری) از پوشه images، و ارسال آن به
همراه یک کپشن متنی گرم و متنوع (نه نوشته‌شده روی عکس) به کانال تلگرام.
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
CAPTION_STATE_PATH = "caption_state.json"

# آدرس API رایگان تقویم شمسی (بدون نیاز به کلید) برای دریافت مناسبت روز و تاریخ قمری
CALENDAR_API_URL = "https://pnldev.com/api/calender"

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "@saba_rasanehh")

HIJRI_MONTHS_FA = [
    "محرم", "صفر", "ربیع‌الاول", "ربیع‌الثانی", "جمادی‌الاول", "جمادی‌الثانی",
    "رجب", "شعبان", "رمضان", "شوال", "ذوالقعده", "ذوالحجه",
]

# ---------- استخر جمله‌های روزانه (برای اینکه پیام هر روز تکراری نباشد) ----------
# هر «حال‌وهوا» چند نسخه دارد؛ هر روز یک حال‌وهوا (متفاوت از دیروز) و یک نسخه‌ی
# تصادفیِ تازه از آن انتخاب می‌شود، تا وقتی همه‌ی نسخه‌ها یک‌بار استفاده شوند.

CAPTION_POOL = {
    # یک روز امیدبخش
    "hope": [
        {
            "opening": "صبح بخیر به مردمی که هنوز امید را، حتی لابه‌لای سختی‌های زندگی، زمین نگذاشته‌اند.",
            "wish_intro": "امروز را با یک آرزوی ساده شروع کنیم:",
            "wish_text": "دل‌ها آرام‌تر، سفره‌ها پُرتر و فرداها روشن‌تر از امروز باشد.",
        },
        {
            "opening": "صبح بخیر به همه‌ی کسانی که با وجود خستگی دیروز، امروز را دوباره از نو شروع می‌کنند.",
            "wish_intro": "بیایید امروز را با این نیت شروع کنیم:",
            "wish_text": "هر قدمی که برمی‌داریم، یک قدم به آرامش نزدیک‌تر باشد.",
        },
        {
            "opening": "صبح بخیر به شهری که هر روز صبح، دوباره بلند می‌شود و ادامه می‌دهد.",
            "wish_intro": "امروز آرزو می‌کنیم:",
            "wish_text": "اتفاقی کوچک، همین امروز، دل‌تان را گرم کند.",
        },
    ],
    # یک روز ادبی
    "literary": [
        {
            "opening": "صبح، مثل برگی سفید است که هنوز هیچ‌کس رویش چیزی ننوشته؛ بگذارید امروز خوب بنویسیمش.",
            "wish_intro": "با خودمان عهد کنیم:",
            "wish_text": "هر طلوع، دعوتی‌ست دوباره برای زیستن؛ امروز را با آرامش بپذیریم.",
        },
        {
            "opening": "در میان هیاهوی صبح، صدای آرام دل‌تان را گم نکنید.",
            "wish_intro": "امروز به یاد داشته باشیم:",
            "wish_text": "زندگی از همین لحظه‌های ساده‌ی صبحگاهی ساخته می‌شود.",
        },
        {
            "opening": "آفتاب که بالا می‌آید، انگار زمین دوباره نفس می‌کشد.",
            "wish_intro": "آرزوی امروزمان این باشد:",
            "wish_text": "دل‌مان به‌اندازه‌ی این آسمان، روشن و باز بماند.",
        },
    ],
    # یک روز طنز ظریف
    "humor": [
        {
            "opening": "صبح بخیر به همه‌ی کسانی که هنوز باور نکرده‌اند تعطیلات تمام شده.",
            "wish_intro": "امروز را این‌طور شروع کنیم:",
            "wish_text": "انگار چای‌مان هنوز داغ است، نه سرد؛ باقی‌اش را هم درست می‌کنیم!",
        },
        {
            "opening": "صبح بخیر به آن‌هایی که زنگ گوشی را ده بار قطع کردند و بالاخره بیدار شدند.",
            "wish_intro": "قول امروزمان این است:",
            "wish_text": "هرچه شد، حداقل قهوه‌مان درست باشد؛ بقیه‌اش را درست می‌کنیم.",
        },
        {
            "opening": "صبح بخیر به همه‌ی رفقایی که صبح‌ها با هزار بهانه از رختخواب جدا می‌شوند.",
            "wish_intro": "امروز کمی آسان‌تر بگیریم:",
            "wish_text": "دنیا قرار نیست همین امروز درست شود، ولی می‌تواند کمی بهتر شود.",
        },
    ],
    # یک روز مخصوص بازنشسته‌ها
    "retiree": [
        {
            "opening": "صبح بخیر به آن‌ها که یک عمر برای دیگران وقت گذاشتند و حالا وقت‌شان برای خودشان است.",
            "wish_intro": "امروز آرزو می‌کنیم:",
            "wish_text": "آرامش امروزتان را با خیال راحت زندگی کنید؛ به‌اندازه‌ی کافی زحمت کشیده‌اید.",
        },
        {
            "opening": "صبح بخیر به دستانی که سال‌ها زحمت کشیدند و حالا وقت آرام‌گرفتن‌شان است.",
            "wish_intro": "امیدواریم امروز داشته باشید:",
            "wish_text": "لحظه‌ای برای نشستن کنار پنجره و نگاه‌کردن به آفتاب.",
        },
        {
            "opening": "صبح بخیر به تجربه‌ها و خاطره‌هایی که هر بازنشسته، سرمایه‌ی بی‌ادعای این مملکت‌اند.",
            "wish_intro": "امروز به یاد داشته باشید:",
            "wish_text": "قدر آرامش امروزتان را بدانید؛ حق‌تان بود.",
        },
    ],
    # یک روز با یک جمله کوتاه تأمل‌برانگیز
    "reflective": [
        {
            "opening": "هیچ صبحی شبیه صبح دیگر نیست؛ امروز را با چشمی تازه ببینید.",
            "wish_intro": "کافی‌ست امروز:",
            "wish_text": "یک نفس عمیق بکشید و به خودتان یادآوری کنید که هنوز اینجایید.",
        },
        {
            "opening": "گاهی همین که از خواب بیدار شده‌ای، خودش یک پیروزی کوچک است.",
            "wish_intro": "بگذارید امروز:",
            "wish_text": "خودتان اولین کسی باشید که به خودتان لبخند می‌زنید.",
        },
        {
            "opening": "روزها از پی هم می‌آیند، اما هر کدام فرصتی تازه‌اند.",
            "wish_intro": "امروز را طوری زندگی کنیم:",
            "wish_text": "که فردا دل‌مان برایش تنگ شود.",
        },
    ],
}

MOODS = list(CAPTION_POOL.keys())

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
    """ساخت خطوط «امروز:» شامل تاریخ شمسی، تاریخ قمری، و مناسبت (در صورت وجود)."""
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


def load_caption_state() -> dict:
    if os.path.exists(CAPTION_STATE_PATH):
        with open(CAPTION_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_mood": None, "used": {}}


def save_caption_state(state: dict) -> None:
    with open(CAPTION_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def pick_caption_pair() -> dict:
    """
    انتخاب یک حال‌وهوای متفاوت از روز قبل (امیدبخش/ادبی/طنز/بازنشسته/تأمل‌برانگیز)
    و یک نسخه‌ی تصادفیِ استفاده‌نشده از آن، تا کپشن هر روز واقعاً تازه باشد.
    """
    state = load_caption_state()
    last_mood = state.get("last_mood")

    mood_candidates = [m for m in MOODS if m != last_mood] or MOODS
    mood = random.choice(mood_candidates)

    used = set(state.get("used", {}).get(mood, []))
    pool = CAPTION_POOL[mood]
    remaining = [i for i in range(len(pool)) if i not in used]
    if not remaining:
        used = set()
        remaining = list(range(len(pool)))

    idx = random.choice(remaining)
    used.add(idx)

    state.setdefault("used", {})[mood] = sorted(used)
    state["last_mood"] = mood
    save_caption_state(state)

    return pool[idx]


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
    pair = pick_caption_pair()

    lines = ["☀️ صبح بخیر ایران؛", pair["opening"]]
    lines += build_date_block(j_now, calendar_info)
    lines += [pair["wish_intro"], pair["wish_text"], CLOSING_LINE]
    lines += ["", CHANNEL_ID_LINE, CHANNEL_LINK_LINE]

    return "\n".join(lines)


def main():
    caption_text = build_caption_text()
    image_path = pick_random_image()
    # عکس کاملاً بکر و بدون تغییر ارسال می‌شود؛ کپشن فقط به‌صورت متن تلگرام درج می‌شود.
    send_to_telegram(image_path, caption_text)


if __name__ == "__main__":
    main()
