"""
FaselHD Telegram Bot 🎬
بوت تليجرام لمشاهدة الأفلام والمسلسلات من FaselHD
"""

import os
import logging
import asyncio
import httpx
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from telegram.error import BadRequest

# ─── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN       = os.getenv("BOT_TOKEN", "8796812487:AAGuilWNNNZHbJrL5fWtRHj7r-aWtFifFpA")
TMDB_READ_TOKEN = os.getenv("TMDB_READ_TOKEN", (
    "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIyNzliMzBjNTEzMTE5YzdjMjQyMGNlZDUzZGM1OWFl"
    "MiIsIm5iZiI6MTc4MDY0OTY2My44NzgsInN1YiI6IjZhMjI4ZWJmZDIzZTI1ZDAxMGNlMzk3"
    "NyIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.P9CsC6MHKrU7kS6oUvF2J"
    "d2ZdlG4UfZdn0jLHjZWMjg"
))

FASEL_API   = "https://faselhdapi.onrender.com"
TMDB_API    = "https://api.themoviedb.org/3"
TMDB_IMG    = "https://image.tmdb.org/t/p/w500"
PAGE_SIZE   = 8

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ─── HTTP helpers ───────────────────────────────────────────────────────────────
async def fasel_get(path: str, **params) -> dict | None:
    url = f"{FASEL_API}{path}"
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(url, params=params)
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        log.error(f"FaselAPI error {path}: {e}")
    return None

async def tmdb_get(path: str, **params) -> dict | None:
    headers = {"Authorization": f"Bearer {TMDB_READ_TOKEN}"}
    params.setdefault("language", "ar-SA")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{TMDB_API}{path}", headers=headers, params=params)
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        log.error(f"TMDB error {path}: {e}")
    return None

async def get_tmdb_poster(title: str, is_movie: bool = True) -> str | None:
    """Search TMDB for a poster image URL."""
    endpoint = "/search/movie" if is_movie else "/search/tv"
    data = await tmdb_get(endpoint, query=title)
    if data and data.get("results"):
        poster = data["results"][0].get("poster_path")
        if poster:
            return f"{TMDB_IMG}{poster}"
    return None

# ─── Keyboards ─────────────────────────────────────────────────────────────────
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 أفلام", callback_data="discover_movies"),
         InlineKeyboardButton("📺 مسلسلات", callback_data="discover_tv-series")],
        [InlineKeyboardButton("🎭 أنمي", callback_data="discover_anime"),
         InlineKeyboardButton("🗂️ التصنيفات", callback_data="categories")],
        [InlineKeyboardButton("🔥 الأحدث", callback_data="discover_movies:1"),
         InlineKeyboardButton("🔍 بحث", callback_data="prompt_search")],
    ])

def back_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")]
    ])

# ─── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 *أهلاً بك في بوت FaselHD!*\n\n"
        "شاهد أحدث الأفلام والمسلسلات والأنمي بجودات متعددة 🍿\n\n"
        "اختر من القائمة أو ابحث مباشرة بالأمر:\n"
        "`/search اسم الفيلم`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=main_menu_keyboard())

# ─── /search ───────────────────────────────────────────────────────────────────
async def search_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = " ".join(ctx.args)
    if not query:
        await update.message.reply_text("✏️ اكتب اسم الفيلم أو المسلسل بعد الأمر:\n`/search اسم الفيلم`",
                                        parse_mode=ParseMode.MARKDOWN)
        return
    await do_search(update, ctx, query, page=1)

async def do_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                    query: str, page: int = 1, edit: bool = False):
    msg = update.message or update.callback_query.message
    wait = await msg.reply_text("🔍 جارٍ البحث...") if not edit else None

    data = await fasel_get("/search", query=query, page=page, pageSize=PAGE_SIZE)

    if not data or not data.get("data"):
        text = "❌ لا توجد نتائج لهذا البحث."
        if wait:
            await wait.edit_text(text)
        else:
            await msg.edit_text(text)
        return

    results   = data["data"]
    total     = data.get("total", len(results))
    total_pgs = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    buttons = []
    for item in results:
        itype = item.get("type", "movie")
        cid   = item.get("id")
        title = item.get("title") or item.get("name") or "بدون عنوان"
        emoji = "📺" if itype in ("tv", "series", "tv-series") else "🎬"
        cb    = f"tv_{cid}" if itype in ("tv", "series", "tv-series") else f"movie_{cid}"
        buttons.append([InlineKeyboardButton(f"{emoji} {title}", callback_data=cb)])

    # Pagination
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"search_{query}:{page-1}"))
    if page < total_pgs:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"search_{query}:{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")])

    text = f"🔍 نتائج البحث عن: *{query}*\nصفحة {page} من {total_pgs}"

    if wait:
        await wait.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                             reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                            reply_markup=InlineKeyboardMarkup(buttons))

# ─── Discover / Categories ─────────────────────────────────────────────────────
async def show_discover(query_obj, category: str = "movies", page: int = 1):
    """Show discovered content list."""
    data = await fasel_get(f"/discover/{category}", page=page, pageSize=PAGE_SIZE)

    if not data or not data.get("data"):
        await query_obj.edit_message_text("❌ لا يوجد محتوى في هذا التصنيف.")
        return

    results   = data["data"]
    total     = data.get("total", len(results))
    total_pgs = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    LABELS = {
        "movies":     "🎬 الأفلام",
        "tv-series":  "📺 المسلسلات",
        "anime":      "🎭 الأنمي",
    }
    label = LABELS.get(category, f"📂 {category}")

    buttons = []
    for item in results:
        itype = item.get("type", "movie")
        cid   = item.get("id")
        title = item.get("title") or item.get("name") or "بدون عنوان"
        emoji = "📺" if itype in ("tv", "series", "tv-series") else "🎬"
        cb    = f"tv_{cid}" if itype in ("tv", "series", "tv-series") else f"movie_{cid}"
        buttons.append([InlineKeyboardButton(f"{emoji} {title}", callback_data=cb)])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"discover_{category}:{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page}/{total_pgs}", callback_data="noop"))
    if page < total_pgs:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"discover_{category}:{page+1}"))
    buttons.append(nav)
    buttons.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")])

    await query_obj.edit_message_text(
        f"{label}\nصفحة {page} من {total_pgs}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_categories(query_obj):
    data = await fasel_get("/allCategories")
    if not data:
        await query_obj.edit_message_text("❌ تعذر تحميل التصنيفات.")
        return

    cats    = data if isinstance(data, list) else data.get("data", [])
    buttons = []
    row     = []
    for i, cat in enumerate(cats[:24]):  # max 24 buttons
        cid   = cat.get("id") or cat.get("slug") or i
        name  = cat.get("name") or cat.get("title") or str(cid)
        row.append(InlineKeyboardButton(name, callback_data=f"cat_{cid}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")])

    await query_obj.edit_message_text(
        "🗂️ *التصنيفات*\nاختر تصنيفاً:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_category(query_obj, cat_id, page: int = 1):
    data = await fasel_get(f"/categories/{cat_id}", page=page, pageSize=PAGE_SIZE)
    if not data or not data.get("data"):
        await query_obj.edit_message_text("❌ لا يوجد محتوى.")
        return

    results   = data["data"]
    total     = data.get("total", len(results))
    total_pgs = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    cat_name  = data.get("category", {}).get("name", f"تصنيف {cat_id}")

    buttons = []
    for item in results:
        itype = item.get("type", "movie")
        cid   = item.get("id")
        title = item.get("title") or item.get("name") or "بدون عنوان"
        emoji = "📺" if itype in ("tv", "series", "tv-series") else "🎬"
        cb    = f"tv_{cid}" if itype in ("tv", "series", "tv-series") else f"movie_{cid}"
        buttons.append([InlineKeyboardButton(f"{emoji} {title}", callback_data=cb)])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"cat_{cat_id}:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/{total_pgs}", callback_data="noop"))
    if page < total_pgs:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"cat_{cat_id}:{page+1}"))
    buttons.append(nav)
    buttons.append([InlineKeyboardButton("🗂️ التصنيفات", callback_data="categories"),
                    InlineKeyboardButton("🏠", callback_data="main_menu")])

    await query_obj.edit_message_text(
        f"📂 *{cat_name}*  —  صفحة {page}/{total_pgs}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ─── Movie Detail ──────────────────────────────────────────────────────────────
async def show_movie(query_obj, movie_id):
    data = await fasel_get(f"/movie/{movie_id}")
    if not data:
        await query_obj.edit_message_text("❌ تعذر تحميل بيانات الفيلم.")
        return

    title    = data.get("title") or data.get("name") or "فيلم"
    year     = data.get("year") or data.get("date", "")[:4] if data.get("date") else ""
    story    = data.get("story") or data.get("description") or ""
    rating   = data.get("rate") or data.get("rating") or ""
    duration = data.get("duration") or ""
    genres   = ", ".join(data.get("genres", [])[:3]) if data.get("genres") else ""
    video_id = data.get("videoId") or data.get("video_id") or data.get("id")

    text = f"🎬 *{title}*"
    if year:      text += f"  ({year})"
    if rating:    text += f"\n⭐ {rating}"
    if duration:  text += f"  ⏱️ {duration}"
    if genres:    text += f"\n🏷️ {genres}"
    if story:     text += f"\n\n📝 {story[:300]}{'…' if len(story)>300 else ''}"

    buttons = []
    if video_id:
        buttons.append([InlineKeyboardButton("▶️ مشاهدة الآن", callback_data=f"watch_{video_id}")])
    buttons.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")])
    kb = InlineKeyboardMarkup(buttons)

    # Try to send with poster
    poster_url = await get_tmdb_poster(title, is_movie=True)
    thumb      = data.get("thumbnail") or data.get("poster") or poster_url

    try:
        if thumb:
            await query_obj.message.reply_photo(
                photo=thumb, caption=text,
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb
            )
            await query_obj.message.delete()
        else:
            await query_obj.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except BadRequest:
        await query_obj.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ─── TV Series Detail ──────────────────────────────────────────────────────────
async def show_tv(query_obj, tv_id, season: int = 1):
    data = await fasel_get(f"/tv/{tv_id}")
    if not data:
        await query_obj.edit_message_text("❌ تعذر تحميل بيانات المسلسل.")
        return

    title   = data.get("title") or data.get("name") or "مسلسل"
    year    = data.get("year") or ""
    story   = data.get("story") or data.get("description") or ""
    rating  = data.get("rate") or data.get("rating") or ""
    seasons = data.get("seasons") or []
    genres  = ", ".join(data.get("genres", [])[:3]) if data.get("genres") else ""

    # Determine episodes count
    ep_count = 0
    if seasons:
        # Try to find episodes for current season
        for s in seasons:
            s_num = s.get("number") or s.get("season_number") or 1
            if int(s_num) == season:
                ep_count = s.get("episodes_count") or s.get("episodesCount") or 0
                break
        if ep_count == 0 and seasons:
            ep_count = seasons[0].get("episodes_count") or seasons[0].get("episodesCount") or 20

    text = f"📺 *{title}*"
    if year:    text += f"  ({year})"
    if rating:  text += f"\n⭐ {rating}"
    if genres:  text += f"\n🏷️ {genres}"
    if story:   text += f"\n\n📝 {story[:250]}{'…' if len(story)>250 else ''}"
    text += f"\n\n🎞️ الموسم {season}"

    # Episodes buttons (max 10 per view)
    buttons = []
    max_ep  = max(ep_count, 1)
    start_ep = 1
    ep_per_page = 10
    row = []
    for ep in range(start_ep, min(start_ep + ep_per_page, max_ep + 1)):
        row.append(InlineKeyboardButton(f"الحلقة {ep}", callback_data=f"episode_{tv_id}_{season}_{ep}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Season nav
    if len(seasons) > 1:
        season_row = []
        for s in seasons[:6]:
            s_num = s.get("number") or s.get("season_number") or 1
            season_row.append(InlineKeyboardButton(
                f"م{s_num}", callback_data=f"tv_{tv_id}_s{s_num}"
            ))
        buttons.append(season_row)

    buttons.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")])
    kb = InlineKeyboardMarkup(buttons)

    poster_url = await get_tmdb_poster(title, is_movie=False)
    thumb      = data.get("thumbnail") or data.get("poster") or poster_url

    try:
        if thumb:
            await query_obj.message.reply_photo(
                photo=thumb, caption=text,
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb
            )
            await query_obj.message.delete()
        else:
            await query_obj.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except BadRequest:
        await query_obj.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ─── Episode ───────────────────────────────────────────────────────────────────
async def show_episode(query_obj, tv_id, season: int, episode: int):
    data = await fasel_get(f"/tv/{tv_id}/episode/{episode}")
    if not data:
        await query_obj.edit_message_text("❌ تعذر تحميل الحلقة.")
        return

    title    = data.get("title") or f"حلقة {episode}"
    video_id = data.get("videoId") or data.get("video_id") or data.get("id")

    text = f"📺 *{title}*\nالحلقة {episode} — الموسم {season}"

    buttons = []
    if video_id:
        buttons.append([InlineKeyboardButton("▶️ مشاهدة الحلقة", callback_data=f"watch_{video_id}")])

    nav = []
    if episode > 1:
        nav.append(InlineKeyboardButton("◀️ السابقة", callback_data=f"episode_{tv_id}_{season}_{episode-1}"))
    nav.append(InlineKeyboardButton("▶️ التالية", callback_data=f"episode_{tv_id}_{season}_{episode+1}"))
    buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 المسلسل", callback_data=f"tv_{tv_id}"),
                    InlineKeyboardButton("🏠", callback_data="main_menu")])

    await query_obj.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup(buttons))

# ─── Watch / Direct Link ───────────────────────────────────────────────────────
async def show_watch_links(query_obj, video_id: str):
    await query_obj.edit_message_text("⏳ جارٍ تحميل روابط المشاهدة...")

    data = await fasel_get("/directlink", id=video_id)
    if not data:
        await query_obj.edit_message_text("❌ تعذر الحصول على رابط المشاهدة.")
        return

    # Parse quality links
    links = []
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, str) and val.startswith("http"):
                links.append((key, val))
            elif isinstance(val, dict):
                url = val.get("url") or val.get("link") or val.get("src") or ""
                if url:
                    links.append((key, url))

    if not links and isinstance(data, dict):
        url = data.get("url") or data.get("link") or data.get("directUrl") or ""
        if url:
            links = [("مشاهدة", url)]

    if not links:
        # Maybe it's a list
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    q   = item.get("quality") or item.get("label") or "مشاهدة"
                    url = item.get("url") or item.get("link") or item.get("src") or ""
                    if url:
                        links.append((q, url))

    if not links:
        await query_obj.edit_message_text(
            "⚠️ لا توجد روابط متاحة حالياً لهذا المحتوى.\n"
            "قد تكون الحلقة غير محدثة بعد.",
            reply_markup=back_main_keyboard()
        )
        return

    # Quality labels
    QUALITY_EMOJI = {"1080": "🔵 1080p", "720": "🟢 720p", "480": "🟡 480p",
                     "360": "🔴 360p", "auto": "⚡ Auto"}
    buttons = []
    for label, url in links[:6]:
        qlabel = next((v for k, v in QUALITY_EMOJI.items() if k in str(label)), f"▶️ {label}")
        buttons.append([InlineKeyboardButton(qlabel, url=url)])

    buttons.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")])

    await query_obj.edit_message_text(
        "🎬 *اختر جودة المشاهدة:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ─── Callback Router ───────────────────────────────────────────────────────────
async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()

    # Main menu
    if data == "main_menu":
        await q.edit_message_text(
            "🎬 *القائمة الرئيسية*\nاختر ما تريد مشاهدته:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard()
        )
        return

    if data == "noop":
        return

    if data == "prompt_search":
        await q.edit_message_text(
            "🔍 أرسل اسم الفيلم أو المسلسل مباشرةً في الرسالة التالية:",
            reply_markup=back_main_keyboard()
        )
        ctx.user_data["awaiting_search"] = True
        return

    # Discover
    if data.startswith("discover_"):
        rest     = data[len("discover_"):]
        parts    = rest.split(":")
        category = parts[0]
        page     = int(parts[1]) if len(parts) > 1 else 1
        await show_discover(q, category, page)
        return

    # Categories list
    if data == "categories":
        await show_categories(q)
        return

    # Specific category
    if data.startswith("cat_"):
        rest  = data[4:]
        parts = rest.split(":")
        cat_id = parts[0]
        page   = int(parts[1]) if len(parts) > 1 else 1
        await show_category(q, cat_id, page)
        return

    # Movie detail
    if data.startswith("movie_"):
        movie_id = data[6:]
        await show_movie(q, movie_id)
        return

    # TV detail (with optional season)
    if data.startswith("tv_"):
        rest = data[3:]
        if "_s" in rest:
            tv_id, season = rest.split("_s")
            await show_tv(q, tv_id, season=int(season))
        else:
            await show_tv(q, rest)
        return

    # Episode
    if data.startswith("episode_"):
        parts   = data[8:].split("_")
        tv_id   = parts[0]
        season  = int(parts[1]) if len(parts) > 1 else 1
        episode = int(parts[2]) if len(parts) > 2 else 1
        await show_episode(q, tv_id, season, episode)
        return

    # Watch / direct link
    if data.startswith("watch_"):
        video_id = data[6:]
        await show_watch_links(q, video_id)
        return

    # Search pagination
    if data.startswith("search_"):
        rest  = data[7:]
        parts = rest.rsplit(":", 1)
        query = parts[0]
        page  = int(parts[1]) if len(parts) > 1 else 1
        await do_search(update, ctx, query, page, edit=True)
        return

# ─── Inline text search (when user sends a message while awaiting) ──────────────
async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("awaiting_search"):
        ctx.user_data["awaiting_search"] = False
        await do_search(update, ctx, update.message.text, page=1)
    else:
        # Treat any text as a search
        await do_search(update, ctx, update.message.text, page=1)

# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    log.info("🤖 Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
