# 📚 Uy vazifalari boti (Homework Bot)

Telegram bot: o'qituvchi guruh yaratadi va vazifa qo'yadi, o'quvchi guruhga kod orqali
qo'shilib vazifani topshiradi, o'qituvchi javobni ko'rib baho qo'yadi.

**Stack:** Python 3.11 · aiogram 3 · SQLite (aiosqlite)

## Imkoniyatlar

**O'qituvchi**
- ➕ Guruh yaratish (avtomatik 6 belgili qo'shilish kodi)
- 👥 Guruhlar ro'yxati, o'quvchilar soni
- 📝 Vazifa qo'shish (sarlavha, izoh, muddat) — guruhdagi hamma o'quvchiga avtomatik xabar
- 📋 Vazifalar, kelgan javoblar (matn/fayl) va 1–5 oralig'ida baho qo'yish

**O'quvchi**
- 🔑 Kod orqali guruhga qo'shilish
- 📚 Vazifalar ro'yxati holat belgilari bilan (⏳ topshirilmagan · ❗ muddati o'tgan · ✅ topshirilgan · [baho])
- 📤 Matn, rasm, hujjat, video yoki ovozli xabar bilan topshirish (qayta topshirish ham mumkin)
- 📊 Baholar va o'rtacha ball

## O'rnatish

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # BOT_TOKEN ni @BotFather dan olib qo'ying
python bot.py
```

## Tekshirish

Haqiqiy Telegram serverisiz, soxta API bilan uchidan-uchiga smoke test:

```bash
python tests/smoke_test.py
```

Test ro'yxatdan o'tish → guruh → vazifa → topshirish → baholash zanjirini va
chegaraviy holatlarni (begona callback, noto'g'ri format, FSM bekor qilish) tekshiradi.

## Struktura

```
bot.py            # ishga tushirish nuqtasi
config.py         # .env sozlamalari
db/database.py    # SQLite ulanishi va sxema
db/queries.py     # barcha SQL so'rovlar
handlers/         # common (ro'yxatdan o'tish), teacher, student
keyboards.py      # reply/inline tugmalar va callback data
states.py         # FSM holatlari
filters.py        # rol bo'yicha filtr
middlewares.py    # foydalanuvchini bazadan yuklash
notify.py         # xavfsiz xabar yuborish
utils.py          # vaqt formati (UTC+5) va matn yordamchilari
tests/smoke_test.py
```

## Ma'lumotlar bazasi

`users` · `groups` · `memberships` · `assignments` · `submissions`
(foreign key + `ON DELETE CASCADE`, `submissions` da `(assignment_id, student_id)` unikal).

## Keyingi bosqichlar (rejalashtirilgan)

- Deadline eslatmalari (APScheduler)
- Guruh statistikasi va Excel/CSV hisobot
- Vazifani tahrirlash/o'chirish, o'quvchini guruhdan chiqarish
- Ko'p tillilik va admin paneli
- FSM uchun Redis storage, PostgreSQL ga o'tish
