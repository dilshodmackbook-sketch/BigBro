from __future__ import annotations

import json
import time
from datetime import date, timedelta
from typing import Dict, Optional

from aiogram import Bot
from aiogram.utils.web_app import WebAppUser, safe_parse_webapp_init_data
from aiohttp import web

from . import config, db, notify, schedule

WEBAPP_DIR = config.BASE_DIR / "webapp"
INIT_DATA_MAX_AGE = 24 * 3600


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


@web.middleware
async def error_middleware(request: web.Request, handler):
    try:
        resp = await handler(request)
    except ApiError as e:
        return web.json_response({"error": e.message}, status=e.status)
    if request.path == "/" or request.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


def auth(request: web.Request) -> WebAppUser:
    """Telegram initData imzosini tekshiradi — soxta so'rovlarni o'tkazmaydi."""
    init_data = request.headers.get("X-Init-Data", "")
    if not init_data:
        raise ApiError("Ilovani Telegram orqali oching", 401)
    try:
        data = safe_parse_webapp_init_data(token=config.BOT_TOKEN, init_data=init_data)
    except ValueError:
        raise ApiError("Avtorizatsiya xatosi. Ilovani qayta oching", 401)
    if data.user is None:
        raise ApiError("Foydalanuvchi aniqlanmadi", 401)
    if time.time() - data.auth_date.timestamp() > INIT_DATA_MAX_AGE:
        raise ApiError("Sessiya eskirgan. Ilovani yopib, qayta oching", 401)
    u = data.user
    db.upsert_user(u.id, u.username, u.first_name, u.last_name)
    return u


def staff_only(u: WebAppUser) -> None:
    if not config.is_staff(u.id, u.username):
        raise ApiError("Faqat xodimlar uchun", 403)


async def body(request: web.Request) -> Dict:
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError("Noto'g'ri so'rov")
    if not isinstance(data, dict):
        raise ApiError("Noto'g'ri so'rov")
    return data


def booking_json(bk, staff: bool = False) -> Optional[Dict]:
    if bk is None:
        return None
    out = {
        "id": bk["id"],
        "barber_id": bk["barber_id"],
        "barber_name": notify.barber_name(bk["barber_id"]),
        "date": bk["date"],
        "time": bk["time"],
        "kind": bk["kind"],
        "name": bk["name"],
        "phone": bk["phone"],
        "username": bk["username"],
    }
    if staff:
        out["user_id"] = bk["user_id"]
    return out


# ---------- handlers ----------

async def index(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(WEBAPP_DIR / "index.html")


async def public_info(request: web.Request) -> web.Response:
    return web.json_response({"shop": config.SHOP_NAME, "bot_username": request.app["bot_username"]})


async def bootstrap(request: web.Request) -> web.Response:
    u = auth(request)
    row = db.get_user(u.id)
    active = db.user_active_booking(u.id, schedule.now_key())
    return web.json_response({
        "user": {
            "id": u.id,
            "username": u.username,
            "first_name": u.first_name,
            "phone": row["phone"] if row else None,
        },
        "shop": config.SHOP_NAME,
        "barbers": [{"id": b.id, "name": b.name} for b in config.BARBERS],
        "is_staff": config.is_staff(u.id, u.username),
        "active": booking_json(active),
        "slot_minutes": config.SLOT_MINUTES,
        "remind_minutes": config.REMIND_BEFORE_MIN,
        "status": schedule.open_status(),
    })


async def get_schedule(request: web.Request) -> web.Response:
    """Barcha ustalar uchun keyingi N kun slotlari. Status: f=bo'sh, b=band, p=o'tgan.
    "0" kaliti — "Farqi yo'q" (kamida bitta usta bo'sh bo'lsa, slot bo'sh)."""
    auth(request)
    days = schedule.upcoming_days()
    times = schedule.slot_times()
    busy = {(r["barber_id"], r["date"], r["time"]) for r in db.active_in_range(days[0].isoformat(), days[-1].isoformat())}
    n = schedule.now()

    slots: Dict[str, Dict[str, list]] = {str(b.id): {} for b in config.BARBERS}
    slots["0"] = {}
    out_days = []
    for d in days:
        iso = d.isoformat()
        closed = not schedule.is_open(d)
        out_days.append({"date": iso, "closed": closed})
        if closed:
            for k in slots:
                slots[k][iso] = []
            continue
        any_list = []
        for b in config.BARBERS:
            lst = []
            for t in times:
                if schedule.slot_dt(iso, t) <= n:
                    st = "p"
                elif (b.id, iso, t) in busy:
                    st = "b"
                else:
                    st = "f"
                lst.append([t, st])
            slots[str(b.id)][iso] = lst
        for i, t in enumerate(times):
            sts = [slots[str(b.id)][iso][i][1] for b in config.BARBERS]
            any_list.append([t, "f" if "f" in sts else ("p" if "p" in sts else "b")])
        slots["0"][iso] = any_list

    return web.json_response({"today": days[0].isoformat(), "days": out_days, "slots": slots})


async def book(request: web.Request) -> web.Response:
    u = auth(request)
    data = await body(request)
    try:
        barber_id = int(data.get("barber_id") or 0)
    except (TypeError, ValueError):
        raise ApiError("Usta noto'g'ri")
    d = str(data.get("date") or "")
    t = str(data.get("time") or "")
    name = " ".join(str(data.get("name") or u.first_name or "").split())[:40]
    phone = schedule.normalize_phone(data.get("phone"))

    if barber_id and barber_id not in config.BARBER_BY_ID:
        raise ApiError("Usta topilmadi")
    if not name:
        raise ApiError("Ismingizni kiriting")
    if not phone:
        raise ApiError("Telefon raqamini to'g'ri kiriting")
    if not schedule.is_bookable(d, t):
        raise ApiError("Bu vaqtga yozilib bo'lmaydi. Boshqa vaqt tanlang", 409)
    if db.user_active_booking(u.id, schedule.now_key()):
        raise ApiError("Sizda allaqachon faol navbat bor", 409)

    if barber_id:
        candidates = [barber_id]
    else:
        # "Farqi yo'q": shu kuni kamroq band bo'lgan ustadan boshlab
        load = {b.id: 0 for b in config.BARBERS}
        for r in db.active_in_range(d, d):
            load[r["barber_id"]] = load.get(r["barber_id"], 0) + 1
        candidates = sorted(load, key=lambda bid: (load[bid], bid))

    db.set_phone(u.id, phone)
    minutes_left = (schedule.slot_dt(d, t) - schedule.now()).total_seconds() / 60
    booking_id = None
    for bid in candidates:
        booking_id = db.create_booking(bid, d, t, "client", u.id, name, u.username, phone,
                                       reminded=minutes_left <= config.REMIND_BEFORE_MIN)
        if booking_id:
            break
    if not booking_id:
        raise ApiError("Afsus, bu vaqtni hozirgina boshqa mijoz oldi. Boshqa vaqt tanlang", 409)

    bk = db.get_booking(booking_id)
    notify.spawn(notify.new_booking(request.app["bot"], bk))
    return web.json_response({"booking": booking_json(bk)})


async def cancel(request: web.Request) -> web.Response:
    u = auth(request)
    data = await body(request)
    try:
        booking_id = int(data.get("id"))
    except (TypeError, ValueError):
        raise ApiError("Navbat topilmadi", 404)
    bk = db.get_booking(booking_id)
    if not bk:
        raise ApiError("Navbat topilmadi", 404)
    if bk["user_id"] != u.id and not config.is_staff(u.id, u.username):
        raise ApiError("Ruxsat yo'q", 403)
    if not db.cancel_booking(booking_id, u.id):
        raise ApiError("Navbat allaqachon bekor qilingan", 409)
    notify.spawn(notify.cancelled(request.app["bot"], bk, u.id))
    return web.json_response({"ok": True})


async def staff_day(request: web.Request) -> web.Response:
    u = auth(request)
    staff_only(u)
    days = [d.isoformat() for d in schedule.upcoming_days()]
    d = request.query.get("date") or days[0]
    if d not in days:
        d = days[0]
    rows = db.active_in_range(days[0], days[-1])
    counts = {day: 0 for day in days}
    for r in rows:
        if r["kind"] == "client":
            counts[r["date"]] += 1

    times = schedule.slot_times()
    n = schedule.now()
    open_day = schedule.is_open(date.fromisoformat(d))
    barbers = []
    for b in config.BARBERS:
        by_time = {r["time"]: r for r in rows if r["date"] == d and r["barber_id"] == b.id}
        all_times = sorted(set(times if open_day else []) | set(by_time))
        barbers.append({
            "id": b.id,
            "name": b.name,
            "slots": [{
                "time": t,
                "past": schedule.slot_dt(d, t) + timedelta(minutes=config.SLOT_MINUTES) <= n,
                "booking": booking_json(by_time.get(t), staff=True),
            } for t in all_times],
        })
    return web.json_response({
        "date": d,
        "days": [{"date": day, "closed": not schedule.is_open(date.fromisoformat(day))} for day in days],
        "counts": counts,
        "barbers": barbers,
    })


async def staff_block(request: web.Request) -> web.Response:
    """Joyida (navbatsiz) kelgan mijoz uchun slotni band qilish."""
    u = auth(request)
    staff_only(u)
    data = await body(request)
    try:
        barber_id = int(data.get("barber_id"))
    except (TypeError, ValueError):
        raise ApiError("Usta topilmadi")
    d, t = str(data.get("date") or ""), str(data.get("time") or "")
    if barber_id not in config.BARBER_BY_ID:
        raise ApiError("Usta topilmadi")
    if not schedule.is_blockable(d, t):
        raise ApiError("Bu vaqtni band qilib bo'lmaydi")
    if not db.create_booking(barber_id, d, t, "blocked", None, "Joyida mijoz", None, None, reminded=True):
        raise ApiError("Bu vaqt allaqachon band", 409)
    return web.json_response({"ok": True})


def create_app(bot: Bot, bot_username: str) -> web.Application:
    app = web.Application(middlewares=[error_middleware])
    app["bot"] = bot
    app["bot_username"] = bot_username
    app.router.add_get("/", index)
    app.router.add_static("/static/", WEBAPP_DIR)
    app.router.add_get("/api/public", public_info)
    app.router.add_get("/api/bootstrap", bootstrap)
    app.router.add_get("/api/schedule", get_schedule)
    app.router.add_post("/api/book", book)
    app.router.add_post("/api/cancel", cancel)
    app.router.add_get("/api/staff/day", staff_day)
    app.router.add_post("/api/staff/block", staff_block)
    return app
