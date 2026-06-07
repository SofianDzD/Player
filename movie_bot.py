import requests
import json
import logging
import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

# ===================== CONFIG =====================
BOT_TOKEN        = "8796812487:AAGuilWNNNZHbJrL5fWtRHj7r-aWtFifFpA"
TMDB_API_KEY     = "279b30c513119c7c2420ced53dc59ae2"
TMDB_READ_TOKEN  = (
    "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIyNzliMzBjNTEzMTE5YzdjMjQyMGNlZDUzZGM1OWF"
    "lMiIsIm5iZiI6MTc4MDY0OTY2My44NzgsInN1YiI6IjZhMjI4ZWJmZDIzZTI1ZDAxMGNlMzk3"
    "NyIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.P9CsC6MHKrU7kS6oUvF2J"
    "d2ZdlG4UfZdn0jLHjZWMjg"
)
OPENSUB_API_KEY  = "zWe9WsEghfwbc3y0zLcC8Otv4snuXxyE"
STREAM_BASE      = "https://missourimonster-vyla.hf.space"
TMDB_BASE        = "https://api.themoviedb.org/3"
TMDB_IMG         = "https://image.tmdb.org/t/p/w500"
OPENSUB_BASE     = "https://api.opensubtitles.com/api/v1"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Thread pool for running blocking HTTP calls in parallel
executor = ThreadPoolExecutor(max_workers=6)

# ===================== TMDB HELPERS =====================

TMDB_HEADERS = {
    "Authorization": f"Bearer {TMDB_READ_TOKEN}",
    "accept": "application/json",
}

GENRE_AR = {
    "Action": "أكشن", "Adventure": "مغامرة", "Animation": "رسوم متحركة",
    "Comedy": "كوميديا", "Crime": "جريمة", "Documentary": "وثائقي",
    "Drama": "دراما", "Family": "عائلي", "Fantasy": "خيال",
    "History": "تاريخي", "Horror": "رعب", "Music": "موسيقى",
    "Mystery": "غموض", "Romance": "رومانسي", "Science Fiction": "خيال علمي",
    "TV Movie": "تلفزيوني", "Thriller": "إثارة", "War": "حرب", "Western": "غربي",
}


def tmdb_get(endpoint: str, params: dict = None) -> dict:
    url = f"{TMDB_BASE}/{endpoint}"
    res = requests.get(url, headers=TMDB_HEADERS, params=params or {}, timeout=15)
    return res.json()


def merge_ar_en(ar: dict, en: dict) -> dict:
    if not ar.get("title"):
        ar["title"] = en.get("title", "")
    if not ar.get("overview"):
        ar["overview"] = en.get("overview", "")
    return ar


def merge_list(ar_list: list, en_list: list) -> list:
    en_map = {m["id"]: m for m in en_list}
    for m in ar_list:
        en = en_map.get(m["id"], {})
        if not m.get("title"):
            m["title"] = en.get("title", "")
        if not m.get("overview"):
            m["overview"] = en.get("overview", "")
    return ar_list


def search_movies(query: str) -> list:
    ar = tmdb_get("search/movie", {"query": query, "language": "ar-SA"}).get("results", [])
    en = tmdb_get("search/movie", {"query": query, "language": "en-US"}).get("results", [])
    if not ar:
        return en[:8]
    return merge_list(ar, en)[:8]


def get_movie_details(movie_id: int) -> dict:
    ar = tmdb_get(f"movie/{movie_id}", {"language": "ar-SA", "append_to_response": "external_ids"})
    en = tmdb_get(f"movie/{movie_id}", {"language": "en-US", "append_to_response": "external_ids"})
    return merge_ar_en(ar, en)


def get_popular_movies() -> list:
    ar = tmdb_get("movie/popular", {"language": "ar-SA"}).get("results", [])
    en = tmdb_get("movie/popular", {"language": "en-US"}).get("results", [])
    return merge_list(ar, en)[:8]


def get_top_rated_movies() -> list:
    ar = tmdb_get("movie/top_rated", {"language": "ar-SA"}).get("results", [])
    en = tmdb_get("movie/top_rated", {"language": "en-US"}).get("results", [])
    return merge_list(ar, en)[:8]


def get_now_playing() -> list:
    ar = tmdb_get("movie/now_playing", {"language": "ar-SA"}).get("results", [])
    en = tmdb_get("movie/now_playing", {"language": "en-US"}).get("results", [])
    return merge_list(ar, en)[:8]


# ===================== OPENSUBTITLES HELPERS =====================

OPENSUB_HEADERS = {
    "Api-Key": OPENSUB_API_KEY,
    "Content-Type": "application/json",
    "User-Agent": "MovieTelegramBot v1.0",
}


def search_subtitle(tmdb_id: int, imdb_id: str = None) -> dict | None:
    """
    Search OpenSubtitles for Arabic subtitle.
    Returns dict with file_id and name, or None.
    """
    params = {"languages": "ar", "type": "movie"}
    if imdb_id:
        params["imdb_id"] = imdb_id.replace("tt", "")
    else:
        params["tmdb_id"] = tmdb_id

    try:
        res = requests.get(
            f"{OPENSUB_BASE}/subtitles",
            headers=OPENSUB_HEADERS,
            params=params,
            timeout=15,
        )
        data = res.json()
        results = data.get("data", [])
        if not results:
            return None

        # Pick best: prefer .srt, most downloads
        best = None
        for item in results:
            attrs = item.get("attributes", {})
            files = attrs.get("files", [])
            if not files:
                continue
            ext = attrs.get("format", "srt")
            if ext not in ("srt", "ass", "ssa"):
                ext = "srt"
            if best is None or attrs.get("download_count", 0) > best.get("downloads", 0):
                best = {
                    "file_id": files[0]["file_id"],
                    "name": files[0].get("file_name", "subtitle") + f".{ext}",
                    "downloads": attrs.get("download_count", 0),
                    "ext": ext,
                }
        return best
    except Exception as e:
        logger.error(f"OpenSubtitles search error: {e}")
        return None


def get_subtitle_download_url(file_id: int) -> str | None:
    """Get a one-time download URL from OpenSubtitles."""
    try:
        res = requests.post(
            f"{OPENSUB_BASE}/download",
            headers=OPENSUB_HEADERS,
            json={"file_id": file_id},
            timeout=15,
        )
        data = res.json()
        return data.get("link")
    except Exception as e:
        logger.error(f"OpenSubtitles download error: {e}")
        return None


# ===================== STREAMING HELPERS =====================

def fetch_stream_sources(movie_id: int) -> list:
    """
    Fetch sources via SSE with strict timeouts:
    - connect timeout: 8s
    - read timeout: 8s per chunk
    - hard cap: stop after 12s total OR 15 sources OR 'done' event
    """
    import time
    sources = []
    deadline = time.time() + 12          # hard 12-second wall clock limit
    MAX_SOURCES = 15

    try:
        url = f"{STREAM_BASE}/movie"
        # timeout=(connect, read) — read timeout fires if no data for 8s
        with requests.get(
            url,
            params={"id": movie_id},
            stream=True,
            timeout=(8, 8),
        ) as res:
            for line in res.iter_lines():
                # Hard deadline check
                if time.time() > deadline:
                    logger.warning(f"Stream deadline reached for movie {movie_id}, stopping early")
                    break

                if not line or not line.startswith(b"data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                if event.get("type") == "source":
                    s = event["source"]
                    url_val = s.get("url", "")
                    if url_val:
                        sources.append({"label": s.get("label", "مشاهدة"), "url": url_val})
                    if len(sources) >= MAX_SOURCES:
                        break
                elif event.get("type") == "done":
                    break

    except requests.exceptions.Timeout:
        logger.warning(f"Stream timeout for movie {movie_id}, returning {len(sources)} sources collected so far")
    except Exception as e:
        logger.error(f"Stream error for movie {movie_id}: {e}")

    return sources


# ===================== UI HELPERS =====================

def format_movie_caption(movie: dict) -> str:
    ar_title   = movie.get("title", "").strip()
    orig_title = movie.get("original_title", "").strip()

    if ar_title and ar_title != orig_title:
        title_line = f"🎬 *{ar_title}*\n🔤 _{orig_title}_"
    elif ar_title:
        title_line = f"🎬 *{ar_title}*"
    else:
        title_line = f"🎬 *{orig_title or 'بدون عنوان'}*"

    year        = (movie.get("release_date") or "")[:4]
    rating      = movie.get("vote_average", 0)
    overview    = (movie.get("overview") or "لا يوجد وصف متاح.").strip()
    runtime     = movie.get("runtime", 0)
    runtime_str = f"{runtime // 60}س {runtime % 60}د" if runtime else "غير معروف"
    stars       = "⭐" * round(rating / 2) if rating else ""
    genre_names = [g["name"] for g in movie.get("genres", [])]
    genre_ar    = ", ".join([GENRE_AR.get(g, g) for g in genre_names])

    return (
        f"{title_line}\n\n"
        f"📅 السنة: {year or 'غير معروف'}\n"
        f"⏱ المدة: {runtime_str}\n"
        f"🎭 النوع: {genre_ar or 'غير معروف'}\n"
        f"⭐ التقييم: {rating:.1f}/10 {stars}\n\n"
        f"📖 *القصة:*\n{overview[:700]}{'...' if len(overview) > 700 else ''}"
    )


def movies_keyboard(movies: list, back_label: str = "") -> InlineKeyboardMarkup:
    buttons = []
    for m in movies:
        title = m.get("title") or m.get("name") or "فيلم"
        year  = (m.get("release_date") or "")[:4]
        label = f"🎬 {title} ({year})" if year else f"🎬 {title}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"movie_{m['id']}")])
    if back_label:
        buttons.append([InlineKeyboardButton(f"← {back_label}", callback_data="back_home")])
    return InlineKeyboardMarkup(buttons)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔥 الأكثر مشاهدة",  callback_data="popular"),
            InlineKeyboardButton("⭐ الأعلى تقييماً", callback_data="top_rated"),
        ],
        [
            InlineKeyboardButton("🎞 يُعرض الآن", callback_data="now_playing"),
            InlineKeyboardButton("🔍 بحث",         callback_data="search_hint"),
        ],
    ])


# ===================== HANDLERS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *مرحباً بك في بوت الأفلام!* 🎬\n\n"
        "• 🔍 اكتب اسم الفيلم مباشرة للبحث\n"
        "• 🔥 تصفح الأكثر مشاهدة\n"
        "• ⭐ الأعلى تقييماً\n"
        "• 🎞 يُعرض الآن\n\n"
        "عند اختيار سيرفر المشاهدة سيُرسل لك:\n"
        "▶️ رابط يفتح VLC تلقائياً مع الترجمة العربية 🇸🇦\n\n"
        "اختر من القائمة أو ابحث:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *تعليمات الاستخدام:*\n\n"
        "• اكتب اسم الفيلم للبحث\n"
        "• /start — القائمة الرئيسية\n"
        "• /popular — الأكثر مشاهدة\n"
        "• /toprated — الأعلى تقييماً\n"
        "• /nowplaying — يُعرض الآن\n\n"
        "📱 *كيف تشاهد مع الترجمة:*\n"
        "1. اختر الفيلم ثم السيرفر\n"
        "2. سيرسل البوت زر *افتح في VLC*\n"
        "3. اضغطه — يفتح VLC مع الترجمة مباشرة!\n"
        "4. أو يرسل ملف الترجمة *.srt* يدوياً",
        parse_mode=ParseMode.MARKDOWN,
    )


async def popular_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movies = get_popular_movies()
    await update.message.reply_text(
        "🔥 *الأفلام الأكثر مشاهدة:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=movies_keyboard(movies, "القائمة الرئيسية"),
    )


async def top_rated_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movies = get_top_rated_movies()
    await update.message.reply_text(
        "⭐ *الأفلام الأعلى تقييماً:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=movies_keyboard(movies, "القائمة الرئيسية"),
    )


async def now_playing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movies = get_now_playing()
    await update.message.reply_text(
        "🎞 *يُعرض الآن في السينما:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=movies_keyboard(movies, "القائمة الرئيسية"),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if not q:
        return
    msg = await update.message.reply_text("🔍 جارٍ البحث...")
    movies = search_movies(q)
    if not movies:
        await msg.edit_text("❌ لم يتم العثور على نتائج. حاول بكلمات مختلفة.")
        return
    await msg.edit_text(
        f"🔍 *نتائج البحث عن:* `{q}`\n\nاختر فيلماً:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=movies_keyboard(movies, "القائمة الرئيسية"),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data

    # ── Back home ──────────────────────────────────────────
    if data == "back_home":
        await query.edit_message_text(
            "🎬 *القائمة الرئيسية*\nاختر تصنيفاً أو ابحث عن فيلم:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(),
        )

    # ── Categories ─────────────────────────────────────────
    elif data == "popular":
        movies = get_popular_movies()
        await query.edit_message_text(
            "🔥 *الأفلام الأكثر مشاهدة:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=movies_keyboard(movies, "القائمة الرئيسية"),
        )

    elif data == "top_rated":
        movies = get_top_rated_movies()
        await query.edit_message_text(
            "⭐ *الأفلام الأعلى تقييماً:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=movies_keyboard(movies, "القائمة الرئيسية"),
        )

    elif data == "now_playing":
        movies = get_now_playing()
        await query.edit_message_text(
            "🎞 *يُعرض الآن في السينما:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=movies_keyboard(movies, "القائمة الرئيسية"),
        )

    elif data == "search_hint":
        await query.edit_message_text(
            "🔍 *البحث عن فيلم:*\n\nاكتب اسم الفيلم وسأجد لك النتائج!\n\nمثال: `Inception` أو `أنت عمري`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← رجوع", callback_data="back_home")]]),
        )

    # ── Movie details ───────────────────────────────────────
    elif data.startswith("movie_"):
        movie_id = int(data.split("_")[1])
        await query.edit_message_text("⏳ جارٍ تحميل معلومات الفيلم...")
        movie   = get_movie_details(movie_id)
        caption = format_movie_caption(movie)
        poster  = movie.get("poster_path")
        poster_url = f"{TMDB_IMG}{poster}" if poster else None

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ اختر سيرفر المشاهدة", callback_data=f"watch_{movie_id}")],
            [InlineKeyboardButton("← رجوع", callback_data="back_home")],
        ])

        if poster_url:
            try:
                await query.message.delete()
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=poster_url,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
                return
            except Exception:
                pass
        await query.edit_message_text(caption, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    # ── Server selection ────────────────────────────────────
    elif data.startswith("watch_"):
        movie_id = int(data.split("_")[1])

        # Show immediate feedback
        status_msg = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="⏳ جارٍ البحث عن سيرفرات المشاهدة...",
        )

        # Run blocking SSE fetch in thread pool (non-blocking for bot)
        loop = asyncio.get_event_loop()
        sources = await loop.run_in_executor(executor, fetch_stream_sources, movie_id)

        await status_msg.delete()

        if not sources:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ *لم يتم العثور على مصادر مشاهدة لهذا الفيلم حالياً.*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← رجوع", callback_data=f"movie_{movie_id}")]]),
            )
            return

        # Store sources in context so we can retrieve after server pick
        context.user_data[f"sources_{movie_id}"] = sources

        buttons = []
        for i, src in enumerate(sources[:10]):
            label = src["label"] or f"سيرفر {i+1}"
            buttons.append([InlineKeyboardButton(
                f"🖥 {label}",
                callback_data=f"play_{movie_id}_{i}"
            )])
        buttons.append([InlineKeyboardButton("← رجوع للفيلم", callback_data=f"movie_{movie_id}")])

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"🖥 *اختر سيرفر المشاهدة:*\n\nعدد السيرفرات المتاحة: {len(sources)}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    # ── Play: fetch subtitle + build VLC link ───────────────
    elif data.startswith("play_"):
        parts    = data.split("_")
        movie_id = int(parts[1])
        src_idx  = int(parts[2])

        sources = context.user_data.get(f"sources_{movie_id}", [])
        if not sources or src_idx >= len(sources):
            await query.answer("❌ انتهت الجلسة، ابحث عن الفيلم مجدداً.", show_alert=True)
            return

        stream_url   = sources[src_idx]["url"]
        server_label = sources[src_idx]["label"]

        # Show immediate feedback
        status_msg = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="🔍 جارٍ البحث عن ترجمة عربية...",
        )

        loop = asyncio.get_event_loop()

        # Run movie details + subtitle search IN PARALLEL
        def fetch_movie_and_subtitle():
            movie   = get_movie_details(movie_id)
            imdb_id = movie.get("external_ids", {}).get("imdb_id") or movie.get("imdb_id")
            sub     = search_subtitle(movie_id, imdb_id)
            sub_url = get_subtitle_download_url(sub["file_id"]) if sub else None
            return movie, sub, sub_url

        movie, sub_info, sub_url = await loop.run_in_executor(executor, fetch_movie_and_subtitle)

        await status_msg.delete()

        title    = movie.get("title") or movie.get("original_title") or "الفيلم"

        sub_status = "✅ *تم العثور على ترجمة عربية!*" if sub_url else "⚠️ *لم يتم العثور على ترجمة عربية لهذا الفيلم.*"

        # Telegram does NOT allow vlc:// in inline buttons — send as text instead
        text = (
            f"🎬 *{title}*\n"
            f"🖥 السيرفر: {server_label}\n\n"
            f"{sub_status}\n\n"
            f"🔗 *رابط البث:*\n`{stream_url}`\n\n"
            f"📋 انسخ الرابط وافتحه في VLC:\n"
            f"VLC ← فتح شبكة ← الصق الرابط\n\n"
            f"_(إذا وجدت ترجمة، سيتم إرسالها كملف في الرسالة التالية)_"
        )

        buttons = []
        # Use https stream URL directly as button if it starts with https
        if stream_url.startswith("https://") or stream_url.startswith("http://"):
            buttons.append([InlineKeyboardButton("▶️ فتح رابط البث", url=stream_url)])
        if sub_url and (sub_url.startswith("https://") or sub_url.startswith("http://")):
            buttons.append([InlineKeyboardButton("📥 تحميل الترجمة العربية", url=sub_url)])
        buttons.append([InlineKeyboardButton("🖥 تغيير السيرفر", callback_data=f"watch_{movie_id}")])
        buttons.append([InlineKeyboardButton("← رجوع للفيلم",   callback_data=f"movie_{movie_id}")])

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(buttons),
        )

        # Send subtitle file as document for manual use
        if sub_url:
            try:
                sub_bytes = await loop.run_in_executor(
                    executor,
                    lambda: requests.get(sub_url, timeout=15).content
                )
                fname = sub_info.get("name", "arabic_subtitle.srt")
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=sub_bytes,
                    filename=fname,
                    caption=(
                        f"📄 ملف الترجمة العربية لـ *{title}*\n\n"
                        "إذا لم يفتح VLC تلقائياً، افتح الفيلم يدوياً وأضف هذا الملف كترجمة."
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as e:
                logger.error(f"Failed to send subtitle file: {e}")


# ===================== MAIN =====================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("help",       help_command))
    app.add_handler(CommandHandler("popular",    popular_command))
    app.add_handler(CommandHandler("toprated",   top_rated_command))
    app.add_handler(CommandHandler("nowplaying", now_playing_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🚀 البوت يعمل الآن...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
