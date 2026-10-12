from __future__ import annotations

import asyncio
import logging
from html import escape
from typing import Optional, Set

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from . import config, db, schedule

log = logging.getLogger(__name__)
_tasks: Set[asyncio.Task] = set()


def spawn(coro) -> None:
    """Xabarlarni fonda yuborish (API javobini kutdirmaslik uchun)."""
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def barber_name(barber_id: int) -> str:
    b = config.BARBER_BY_ID.get(barber_id)
    return b.name if b else f"Usta {barber_id}"


def staff_chat_ids(barber_id: int) -> Set[int]:
    """Adminlar + shu navbatning ustasi. Ular botga /start bosgan bo'lishi kerak."""
    ids = set(config.ADMIN_IDS)
    usernames = set(config.ADMIN_USERNAMES)
    b = config.BARBER_BY_ID.get(barber_id)
    if b and b.username:
        usernames.add(b.username)
    for un in usernames:
        uid = db.user_id_by_username(un)
        if uid:
            ids.add(uid)
        else:
            log.warning("@%s botga hali /start bosmagan — unga xabar yuborib bo'lmaydi", un)
    return ids


async def send(bot: Bot, chat_id: int, text: str, kb: Optional[InlineKeyboardMarkup] = None) -> None:
    try:
        await bot.send_message(chat_id, text, reply_markup=kb, disable_web_page_preview=True)
    except TelegramAPIError as e:
        log.warning("Xabar yuborilmadi (%s): %s", chat_id, e)


def client_line(bk) -> str:
    name = escape(bk["name"] or "Mijoz")
    if bk["user_id"]:
        name = f'<a href="tg://user?id={bk["user_id"]}">{name}</a>'
    return name


def details(bk) -> str:
    lines = [
        f"💈 Usta: <b>{escape(barber_name(bk['barber_id']))}</b>",
        f"📅 Kun: <b>{schedule.human_date(bk['date'])}</b>",
        f"🕒 Vaqt: <b>{bk['time']}</b>",
    ]
    return "\n".join(lines)


def contact_lines(bk) -> str:
    lines = [f"👤 Mijoz: {client_line(bk)}"]
    if bk["phone"]:
        lines.append(f"📞 Telefon: {escape(bk['phone'])}")
    lines.append(f"✈️ Telegram: @{escape(bk['username'])}" if bk["username"] else "✈️ Telegram: username yo'q")
    return "\n".join(lines)


def staff_kb(bk) -> InlineKeyboardMarkup:
    rows = []
    if bk["username"]:
        rows.append([InlineKeyboardButton(text="✍️ Telegramda yozish", url=f"https://t.me/{bk['username']}")])
    rows.append([InlineKeyboardButton(text="❌ Navbatni bekor qilish", callback_data=f"cancel:{bk['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def client_kb(bk) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Navbatni bekor qilish", callback_data=f"cancel:{bk['id']}")]
    ])


async def new_booking(bot: Bot, bk) -> None:
    staff_text = f"🆕 <b>Yangi navbat!</b>\n\n{details(bk)}\n\n{contact_lines(bk)}"
    for chat_id in staff_chat_ids(bk["barber_id"]):
        await send(bot, chat_id, staff_text, staff_kb(bk))

    if bk["user_id"]:
        client_text = (
            f"✅ <b>Siz navbatga yozildingiz!</b>\n\n{details(bk)}\n\n"
            f"Sizni kutamiz. Vaqtdan {config.REMIND_BEFORE_MIN} daqiqa oldin eslatma yuboraman.\n"
            "Kela olmasangiz, iltimos navbatni bekor qiling — boshqa mijozga joy bo'shaydi."
        )
        await send(bot, bk["user_id"], client_text, client_kb(bk))


async def cancelled(bot: Bot, bk, by_user_id: int) -> None:
    if bk["kind"] != "client":
        return
    by_client = by_user_id == bk["user_id"]
    if by_client:
        text = f"🚫 <b>Mijoz navbatni bekor qildi</b>\n\n{details(bk)}\n\n{contact_lines(bk)}"
        for chat_id in staff_chat_ids(bk["barber_id"]):
            await send(bot, chat_id, text)
    else:
        if bk["user_id"]:
            await send(bot, bk["user_id"],
                       f"🚫 <b>Navbatingiz bekor qilindi</b>\n\n{details(bk)}\n\n"
                       "Savollar bo'lsa, sartaroshxona bilan bog'laning. Yangi vaqt tanlash uchun «Navbat olish» tugmasini bosing.")
        text = f"🚫 <b>Navbat xodim tomonidan bekor qilindi</b>\n\n{details(bk)}\n\n{contact_lines(bk)}"
        for chat_id in staff_chat_ids(bk["barber_id"]) - {by_user_id}:
            await send(bot, chat_id, text)


async def reminder_loop(bot: Bot) -> None:
    while True:
        try:
            n = schedule.now()
            days = schedule.upcoming_days()
            for bk in db.unreminded(days[0].isoformat(), days[min(1, len(days) - 1)].isoformat()):
                minutes = (schedule.slot_dt(bk["date"], bk["time"]) - n).total_seconds() / 60
                if 0 < minutes <= config.REMIND_BEFORE_MIN:
                    db.mark_reminded(bk["id"])
                    await send(bot, bk["user_id"],
                               f"⏰ <b>Eslatma!</b> Navbatingizga {int(minutes)} daqiqa qoldi.\n\n{details(bk)}\n\n"
                               "Kechiksangiz yoki kela olmasangiz, xabar bering 🙏", client_kb(bk))
        except Exception:
            log.exception("Eslatma yuborishda xato")
        await asyncio.sleep(60)
