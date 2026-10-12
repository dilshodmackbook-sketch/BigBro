from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from . import config, db, notify, schedule

router = Router()


def webapp_kb() -> InlineKeyboardMarkup:
    if not config.WEBAPP_URL.startswith("https://"):
        return InlineKeyboardMarkup(inline_keyboard=[])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💈 Navbat olish", web_app=WebAppInfo(url=config.WEBAPP_URL))]
    ])


def _remember(m: Message) -> None:
    u = m.from_user
    if u:
        db.upsert_user(u.id, u.username, u.first_name, u.last_name)


@router.message(CommandStart())
async def start(m: Message) -> None:
    _remember(m)
    u = m.from_user
    text = (
        f"Assalomu alaykum, <b>{escape(u.first_name or '')}</b>! 👋\n\n"
        f"<b>{escape(config.SHOP_NAME)}</b> sartaroshxonasiga xush kelibsiz.\n\n"
        "Navbat kutib o'tirmang — bo'sh kun va vaqtni tanlab, oldindan yoziling. "
        "Pastdagi tugmani bosing 👇"
    )
    await m.answer(text, reply_markup=webapp_kb())
    if config.is_staff(u.id, u.username):
        await m.answer(
            "🔑 Siz <b>xodim</b> sifatida belgilangansiz.\n\n"
            "• Yangi navbatlar haqida shu yerga xabar keladi\n"
            "• /navbatlar — bugungi va ertangi navbatlar\n"
            "• Mini appda «Panel» bo'limi orqali navbatlarni boshqarishingiz mumkin"
        )


@router.message(Command("navbatlar"))
async def bookings_list(m: Message) -> None:
    _remember(m)
    u = m.from_user
    if not config.is_staff(u.id, u.username):
        await m.answer("Bu buyruq faqat xodimlar uchun.", reply_markup=webapp_kb())
        return
    days = schedule.upcoming_days()[:2]
    rows = db.active_in_range(days[0].isoformat(), days[-1].isoformat())
    parts = []
    for d in days:
        iso = d.isoformat()
        parts.append(f"📅 <b>{schedule.human_date(iso)}</b>")
        for b in config.BARBERS:
            items = [r for r in rows if r["date"] == iso and r["barber_id"] == b.id]
            parts.append(f"\n💈 <i>{escape(b.name)}</i> — {sum(r['kind'] == 'client' for r in items)} ta")
            for r in items:
                if r["kind"] == "blocked":
                    parts.append(f"<code>{r['time']}</code>  🔒 band qilingan")
                    continue
                extra = " · ".join(x for x in [
                    escape(r["phone"] or ""), f"@{escape(r['username'])}" if r["username"] else ""] if x)
                parts.append(f"<code>{r['time']}</code>  {notify.client_line(r)}  {extra}")
        parts.append("")
    await m.answer("\n".join(parts).strip() or "Navbatlar yo'q", reply_markup=webapp_kb())


@router.message(F.contact)
async def contact(m: Message) -> None:
    _remember(m)
    c = m.contact
    if c.user_id != m.from_user.id:
        await m.answer("Iltimos, o'zingizning raqamingizni yuboring.")
        return
    phone = schedule.normalize_phone(c.phone_number)
    if phone:
        db.set_phone(m.from_user.id, phone)
        await m.answer(f"✅ Raqamingiz saqlandi: {escape(phone)}")


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_cb(c: CallbackQuery) -> None:
    try:
        booking_id = int(c.data.split(":", 1)[1])
    except ValueError:
        await c.answer()
        return
    bk = db.get_booking(booking_id)
    u = c.from_user
    if not bk or not (bk["user_id"] == u.id or config.is_staff(u.id, u.username)):
        await c.answer("Ruxsat yo'q", show_alert=True)
        return
    if bk["status"] != "active" or not db.cancel_booking(booking_id, u.id):
        await c.answer("Bu navbat allaqachon bekor qilingan")
    else:
        await c.answer("Navbat bekor qilindi")
        notify.spawn(notify.cancelled(c.bot, bk, u.id))
    if c.message:
        try:
            await c.message.edit_text(c.message.html_text + "\n\n<b>❌ Bekor qilindi</b>", reply_markup=None)
        except Exception:
            pass
