# 🎬 FaselHD Telegram Bot

بوت تليجرام احترافي لمشاهدة الأفلام والمسلسلات من FaselHD

---

## 🚀 التثبيت والتشغيل

### المتطلبات
- Python 3.10+
- pip

### الخطوات

```bash
# 1. تثبيت المكتبات
pip install -r requirements.txt

# 2. تعديل التوكنات في bot.py أو عبر متغيرات البيئة
export BOT_TOKEN="توكن_البوت_من_BotFather"
export TMDB_READ_TOKEN="توكن_TMDB_الخاص_بك"

# 3. تشغيل البوت
python bot.py
```

---

## 🌐 النشر على Railway / Render (مجاناً)

### Railway:
1. ارفع الملفات على GitHub
2. اذهب إلى [railway.app](https://railway.app) وأنشئ مشروعاً جديداً
3. ربطه بالـ repo
4. أضف متغيرات البيئة: `BOT_TOKEN` و `TMDB_READ_TOKEN`
5. Railway سيشغله تلقائياً ✅

### Render:
1. أنشئ Web Service أو Background Worker
2. أضف `pip install -r requirements.txt` كـ Build Command
3. أضف `python bot.py` كـ Start Command

---

## ✨ المميزات

| الميزة | الوصف |
|--------|-------|
| 🔍 بحث ذكي | ابحث بالاسم مباشرةً |
| 🎬 أفلام | تصفح وشاهد الأفلام |
| 📺 مسلسلات | تنقل بين المواسم والحلقات |
| 🎭 أنمي | قسم خاص بالأنمي |
| 🗂️ تصنيفات | تصفح حسب النوع |
| 🖼️ بوسترات | صور عالية الجودة من TMDB |
| ▶️ روابط مباشرة | جودات متعددة 1080p / 720p / 480p |

---

## 🔑 الحصول على توكنات

### BOT_TOKEN:
1. افتح [@BotFather](https://t.me/BotFather) في تليجرام
2. أرسل `/newbot`
3. اتبع التعليمات وستحصل على التوكن

### TMDB_READ_TOKEN:
1. أنشئ حساباً على [themoviedb.org](https://www.themoviedb.org)
2. اذهب إلى الإعدادات > API
3. انسخ **Read Access Token**

---

## 📁 هيكل المشروع

```
faselhd_bot/
├── bot.py           # الكود الرئيسي
├── requirements.txt # المكتبات المطلوبة
└── README.md        # هذا الملف
```

---

## 🔗 APIs المستخدمة

- **FaselHD API**: `https://faselhdapi.onrender.com`
- **TMDB API**: `https://api.themoviedb.org/3`

---

> ⚠️ للاستخدام الشخصي فقط
