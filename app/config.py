from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Barber:
    id: int
    name: str
    username: Optional[str]


def _usernames(raw: str) -> Set[str]:
    return {x.strip().lstrip("@").lower() for x in raw.split(",") if x.strip()}


def _ids(raw: str) -> Set[int]:
    return {int(x) for x in raw.split(",") if x.strip().isdigit()}


def _barbers(raw: str) -> List[Barber]:
    out = []
    parts = [p for p in raw.split(";") if p.strip()]
    for i, part in enumerate(parts, start=1):
        name, _, user = part.partition(":")
        user = user.strip().lstrip("@").lower()
        out.append(Barber(i, name.strip() or f"Usta {i}", user or None))
    return out


def _minutes(hhmm: str) -> int:
    h, m = hhmm.strip().split(":")
    return int(h) * 60 + int(m)


def _breaks(raw: str) -> List[Tuple[int, int]]:
    out = []
    for part in raw.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            out.append((_minutes(a), _minutes(b)))
    return out


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

SHOP_NAME = os.getenv("SHOP_NAME", "BIG BRO")
ADMIN_USERNAMES = _usernames(os.getenv("ADMIN_USERNAMES", "bunyodovf"))
ADMIN_IDS = _ids(os.getenv("ADMIN_IDS", ""))
BARBERS = _barbers(os.getenv("BARBERS", "Usta 1;Usta 2"))
BARBER_BY_ID = {b.id: b for b in BARBERS}

TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))
WORK_START = _minutes(os.getenv("WORK_START", "09:00"))
WORK_END = _minutes(os.getenv("WORK_END", "21:00"))
SLOT_MINUTES = int(os.getenv("SLOT_MINUTES", "30"))
DAYS_AHEAD = int(os.getenv("DAYS_AHEAD", "7"))
DAYS_OFF = {int(x) for x in os.getenv("DAYS_OFF", "").split(",") if x.strip().isdigit()}
BREAKS = _breaks(os.getenv("BREAKS", ""))
REMIND_BEFORE_MIN = int(os.getenv("REMIND_BEFORE_MIN", "60"))

DB_PATH = BASE_DIR / os.getenv("DB_PATH", "data/bigbro.db")


def is_admin(user_id: int, username: Optional[str]) -> bool:
    return user_id in ADMIN_IDS or (username or "").lower() in ADMIN_USERNAMES


def is_staff(user_id: int, username: Optional[str]) -> bool:
    if is_admin(user_id, username):
        return True
    un = (username or "").lower()
    return bool(un) and any(b.username == un for b in BARBERS)
