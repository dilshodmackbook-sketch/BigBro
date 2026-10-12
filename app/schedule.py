from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import List, Optional

from . import config

WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
          "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]


def now() -> datetime:
    return datetime.now(config.TZ)


def now_key() -> str:
    """Hozirgi vaqt "YYYY-MM-DD HH:MM" ko'rinishida (bazadagi date||' '||time bilan solishtirish uchun)."""
    return now().strftime("%Y-%m-%d %H:%M")


def fmt_minutes(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def slot_times() -> List[str]:
    out = []
    step = config.SLOT_MINUTES
    t = config.WORK_START
    while t + step <= config.WORK_END:
        if not any(t < b and t + step > a for a, b in config.BREAKS):
            out.append(fmt_minutes(t))
        t += step
    return out


def upcoming_days() -> List[date]:
    today = now().date()
    return [today + timedelta(days=i) for i in range(config.DAYS_AHEAD)]


def is_open(d: date) -> bool:
    return d.weekday() not in config.DAYS_OFF


def slot_dt(d: str, t: str) -> datetime:
    return datetime.combine(date.fromisoformat(d), time.fromisoformat(t), tzinfo=config.TZ)


def _valid_day_and_time(d: str, t: str) -> bool:
    try:
        day = date.fromisoformat(d)
    except ValueError:
        return False
    return day in upcoming_days() and is_open(day) and t in slot_times()


def is_bookable(d: str, t: str) -> bool:
    """Mijoz uchun: slot boshlanishi hali kelmagan bo'lishi kerak."""
    return _valid_day_and_time(d, t) and slot_dt(d, t) > now()


def is_blockable(d: str, t: str) -> bool:
    """Xodim uchun: hozir davom etayotgan slotni ham band qilish mumkin."""
    return _valid_day_and_time(d, t) and slot_dt(d, t) + timedelta(minutes=config.SLOT_MINUTES) > now()


def open_status() -> dict:
    """Header uchun: hozir ochiqmi va qachongacha."""
    n = now()
    start, end = fmt_minutes(config.WORK_START), fmt_minutes(config.WORK_END)
    minute = n.hour * 60 + n.minute
    if is_open(n.date()) and config.WORK_START <= minute < config.WORK_END:
        return {"open": True, "text": f"Hozir ochiq · {end} gacha"}
    if is_open(n.date()) and minute < config.WORK_START:
        return {"open": False, "text": f"Bugun {start} da ochiladi"}
    for i in range(1, 8):
        d = n.date() + timedelta(days=i)
        if is_open(d):
            day = "Ertaga" if i == 1 else WEEKDAYS[d.weekday()]
            return {"open": False, "text": f"{day} {start} da ochiladi"}
    return {"open": False, "text": "Yopiq"}


def human_date(d: str) -> str:
    day = date.fromisoformat(d)
    today = now().date()
    if day == today:
        prefix = "Bugun"
    elif day == today + timedelta(days=1):
        prefix = "Ertaga"
    else:
        prefix = WEEKDAYS[day.weekday()]
    return f"{prefix}, {day.day}-{MONTHS[day.month - 1]}"


def normalize_phone(raw: object) -> Optional[str]:
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 9:
        digits = "998" + digits
    if digits.startswith("998") and len(digits) != 12:
        return None
    if not 10 <= len(digits) <= 15:
        return None
    return "+" + digits
