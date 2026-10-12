# BIG BRO — sartaroshxona uchun navbat boti (Telegram Mini App)

Mijoz botni ochadi → ustani, kunni, vaqtni tanlaydi → Telegram username avtomatik olinadi,
telefon raqami bir tugma bilan ulashiladi (yoki qo'lda yoziladi) → navbat band qilinadi.
Admin (@bunyodovf) va usta Telegramda darhol xabar oladi.

## Imkoniyatlar
- Oq-qora, minimalist dizayn (Telegram tungi rejimida avtomatik qora fon)
- Usta tanlash yoki «Farqi yo'q» (bo'sh ustaga avtomatik biriktiriladi)
- Kunlar gorizontal kartochkalarda, vaqtlar ertalab / kunduzi / kechqurun guruhlarida
- O'tib ketgan va band vaqtlarni tanlab bo'lmaydi, bitta vaqtga ikki kishi yozila olmaydi
- Bitta mijoz bir vaqtda bitta faol navbat oladi, xohlasa bekor qiladi
- Admin/ustaga xabar: vaqt, ism, telefon, @username + «Yozish» va «Bekor qilish» tugmalari
- Mijozga tasdiq xabari va navbatdan 60 daqiqa oldin eslatma
- Xodimlar uchun «Panel»: kunlik ro'yxat, qo'ng'iroq qilish, yozish, bekor qilish,
  joyida kelgan mijoz uchun vaqtni «Band qilish»
- `/navbatlar` buyrug'i — bugungi va ertangi navbatlar

## Ishga tushirish
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # BOT_TOKEN, WEBAPP_URL, BARBERS ni to'ldiring
.venv/bin/python main.py
```
Mini app faqat **HTTPS** manzilda ishlaydi. Sinash uchun:
```bash
cloudflared tunnel --url http://localhost:8080
```
chiqgan `https://....trycloudflare.com` manzilini `.env` dagi `WEBAPP_URL` ga yozib, botni qayta ishga tushiring.
Doimiy ishlashi uchun VPS + domen (nginx → 8080) kerak.

## Muhim
- **Admin va ustalar botga bir marta `/start` bosishi shart** — aks holda Telegram botga ularga yozishga ruxsat bermaydi.
- Ustalar `.env` da: `BARBERS=Aziz:aziz_username;Jasur:jasur_username`
- Ish vaqti, slot davomiyligi, dam olish kunlari, tanaffus — barchasi `.env` da.
# BigBro
