import os
import re
import math
import json
import time
import random
import sqlite3
import asyncio
import zipfile
import html
import traceback
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont

import cloudinary
import cloudinary.uploader
from collections import Counter
from telegram import (
    Update,
    InputFile,
    InputMediaPhoto,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultPhoto,
    InlineQueryResultArticle,
    InlineQueryResultCachedPhoto,
    InputTextMessageContent
)
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    filters
)

from datetime import datetime
from zoneinfo import ZoneInfo

from db import update_counters,get_counters,update_drops,update_balance,clear_active_drop,update_harem,get_drops,get_balance,get_harem_rarity
from db import get_harem,transfer_character,set_fav,get_fav,who_collected,update_name,increment_character,decrement_character,user_has_character
from db import block_user,is_blocked,increment_streak,unblock_user,get_top_waifu_holders,reset_streak,get_streak
ADMIN_ID = [5192424390]
import os
USE_MOUNT = os.path.exists("/mnt/data")
BASE_PATH = "/mnt/data" if USE_MOUNT else "."
DB_PATH = os.path.join(BASE_PATH, "quiz.db")
os.makedirs("/mnt/data", exist_ok=True)
IMAGE_ZIP_PATH = os.path.join(BASE_PATH, "characters_backup.zip")
#CHARACTER_JSON_PATH = os.path.join(".", "BAKA1", "characters1.json")
CHARACTER_JSON_PATH = os.path.join(BASE_PATH, "characters.json")
import json

json_path = "characters.json"

if not os.path.exists(json_path):
    with open(json_path, "w") as f:
        json.dump({}, f) 

RARITY_CONFIG = {
    "Musician": {"cost": 25, "display": "🎸 Musician", "chance": 0.75, "symbol": "🎸"},
    "School": {"cost": 20, "display": "🎓 School", "chance": 0.75, "symbol": "🎓"},
    "Winter": {"cost": 20, "display": "❄️ Winter", "chance": 0.75, "symbol": "❄️"},
    "Kimono": {"cost": 30, "display": "🪭 Kimono", "chance": 0.50, "symbol": "🪭"},
    "Maid": {"cost": 20, "display": "🧹 Maid", "chance": 0.75, "symbol": "🧹"},
    "Saree": {"cost": 30, "display": "🥻 Saree", "chance": 0.50, "symbol": "🥻"},
    "Basketball": {"cost": 20, "display": "🏀 Basketball", "chance": 0.75, "symbol": "🏀"},
    "Halloween": {"cost": 25, "display": "🎃 Halloween", "chance": 0.75, "symbol": "🎃"},
    "Tennis": {"cost": 20, "display": "🥎 Tennis", "chance": 0.75, "symbol": "🥎"},
    "Bride": {"cost": 30, "display": "👰 Bride", "chance": 0.50, "symbol": "👰"},
    "Celestial": {"cost": 25, "display": "🎐 Celestial", "chance": 0.75, "symbol": "🎐"},
    "Nurse": {"cost": 30, "display": "💉 Nurse", "chance": 0.50, "symbol": "🩺"},
    "Christmas": {"cost": 25, "display": "🎄 Christmas", "chance": 0.75, "symbol": "🎄"},
    "Diwali": {"cost": 35, "display": "🪔 Diwali", "chance": 0.50, "symbol": "🪔"}
}


AUTHORIZED_USERS = [5105207985, 5192424390,6057581189,5716946356,6792709908]

cloudinary.config(
    cloud_name='dvpz1tzam',
    api_key='895687319552522',
    api_secret='RHMZdboQRoneTPZv8SyaSg0ITfg')
DB_PATH = "/mnt/data/quiz.db"

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ Exception: {context.error}")
    if isinstance(update, Update) and update.message:
        pass



def md2_escape(s: str) -> str:
    if s is None:
        return ""
    s = str(s)

    s = s.replace("\\", "\\\\")

    specials = "_*[]()~`>#+-=|{}.! "
    out = []
    for ch in s:
        if ch in specials:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def parse_search_term(search_term: str):
    s = (search_term or "").strip().lower()


    m = re.fullmatch(r"x(\d+)", s)
    multiplicity_ge = int(m.group(1)) if m else None

    id_eq = None
    if multiplicity_ge is None and s.isdigit():
        id_eq = int(s)

    text = "" if (multiplicity_ge is not None or id_eq is not None) else s
    return {"text": text, "id_eq": id_eq, "multiplicity_ge": multiplicity_ge}

def matches_text(char, text, RARITY_CONFIG):
    if not text:
        return True
    name = str(char.get("name", "")).lower()
    rarity_val = char.get("rarity")
    rarity_str = str(rarity_val).lower()
    symbol = str(RARITY_CONFIG.get(rarity_val, {}).get("symbol", "")).lower()
    return (text in name) or (text == rarity_str) or (text in symbol)

def filter_harem_in_memory(harem, search_term, RARITY_CONFIG):
    q = parse_search_term(search_term)

    if q["multiplicity_ge"] is not None:
        counts = Counter(c.get("char_id") for c in harem)
        have_ge = {cid for cid, cnt in counts.items() if cnt >= q["multiplicity_ge"]}
    else:
        have_ge = set()

    matched = []
    for c in harem:
        if q["multiplicity_ge"] is not None and c.get("char_id") not in have_ge:
            continue

        if q["id_eq"] is not None:
            try:
                if int(c.get("char_id")) != q["id_eq"]:
                    continue
            except Exception:
                continue

        if not matches_text(c, q["text"], RARITY_CONFIG):
            continue

        matched.append(c)

    return matched

def db_fetch_char_exact(owner_id: int, char_id_int: int):
    char_id_norm = str(char_id_int).zfill(3)

    doc = get_harem(owner_id)
    if not doc:
        return []

    if char_id_norm not in doc:
        return []

    stack_count = doc[char_id_norm]

    characters = load_characters()
    ch = characters.get(char_id_norm)
    if not ch:
        return []

    return [{
        "char_id": char_id_norm,
        "name": ch.get("name"),
        "rarity": ch.get("rarity"),
        "stack_count": int(stack_count or 1),
        "image_path": ch.get("image_path"),
    }]


def db_fetch_char_by_multiplicity(owner_id: int, n: int):

    doc = get_harem(owner_id)
    if not doc:
        return []

    characters = load_characters()
    out = []

    for cid, stack_count in doc.items():
        if int(stack_count) < n:
            continue


        ch = characters.get(cid)
        if not ch:
            continue

        out.append({
            "char_id": cid,
            "name": ch.get("name"),
            "rarity": ch.get("rarity"),
            "stack_count": int(stack_count),
            "image_path": ch.get("image_path"),
        })

    return out

async def inline_harem_gallery_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qraw = (update.inline_query.query or "").strip()
    if not qraw.startswith("harem:"):
        return

    parts = qraw.split(" ", 1)
    head = parts[0]
    if ":" not in head:
        print(f"[gallery] bad query format: '{qraw}'")
        return
    try:
        owner_id = int(head.split(":", 1)[1])
    except Exception:
        print(f"[gallery] bad owner id in query: '{qraw}'")
        return
    search_term = parts[1].strip().lower() if len(parts) > 1 else ""

    offset_str = update.inline_query.offset or "0"
    try:
        offset = int(offset_str)
    except ValueError:
        offset = 0
    if offset < 0:
        offset = 0
    page_size = 50

    q = parse_search_term(search_term)
    if q["id_eq"] is not None:
        matched = db_fetch_char_exact(owner_id, q["id_eq"])
    elif q["multiplicity_ge"] is not None:
        matched = db_fetch_char_by_multiplicity(owner_id, q["multiplicity_ge"])
    else:
        harem = get_user_harem(owner_id) or []
        matched = filter_harem_in_memory(harem, search_term, RARITY_CONFIG)

    matched.sort(key=lambda c: (str(c.get("name", "")).lower(), str(c.get("char_id", ""))))

    end = min(offset + page_size, len(matched))
    page = matched[offset:end]

    if not page:
        print(f"[gallery] empty page owner={owner_id} term='{search_term}' matched={len(matched)} offset={offset}")
        await update.inline_query.answer([], cache_time=1, is_personal=True, next_offset="")
        return

    results = []
    owner_name_md = md2_escape(get_user_display_name(owner_id) or "User")

    for i, char in enumerate(page):
        name_raw = str(char.get("name", "Unknown"))
        name_md = md2_escape(name_raw.title())
        char_id = str(char.get("char_id"))
        char_id_md = md2_escape(char_id)
        rarity = str(char.get("rarity"))
        rarity_md = md2_escape(rarity)
        image_url = char.get("image_path")
        if not image_url or not str(image_url).startswith(("http://", "https://")):
            print(f"[gallery] skip invalid image_url for {char_id}: {image_url}")
            continue
        symbol = RARITY_CONFIG.get(rarity, {}).get("symbol", "⭐")
        symbol_md = md2_escape(symbol)
        count = int(char.get("stack_count", 1) or 1)

        caption = (
            f"Look\\! Who is here👀 *{owner_name_md}*'s waifu\\!\n\n"
            f"`{char_id_md}` • *{name_md}* x{count}\n"
            f"🔮 *Rarity:* {symbol_md} `{rarity_md}`"
        )

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📦 Who collected?", callback_data=f"who_{char_id}")
        ]])

        results.append(
            InlineQueryResultPhoto(
                id=f"{char_id}:{offset+i}",
                photo_url=image_url,
                thumbnail_url=image_url,
                title=name_raw,
                caption=caption,
                parse_mode="MarkdownV2",
                reply_markup=keyboard
            )
        )

    next_offset = str(end) if end < len(matched) and results else ""

    print(f"[gallery] owner={owner_id} term='{search_term}' matched={len(matched)} offset={offset} end={end} returned={len(results)} next='{next_offset}'")
    if results:
        print(f"[gallery] first_result id={results[0].id} url={page[0].get('image_path')}")

    await update.inline_query.answer(
        results,
        cache_time=1,
        is_personal=True,
        next_offset=next_offset
    )

async def inline_all_waifus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = (update.inline_query.query or "").strip().lower()
    offset_str = update.inline_query.offset or "0"
    try:
        offset = int(offset_str)
    except ValueError:
        offset = 0
    if offset < 0:
        offset = 0
    page_size = 50

    characters = load_characters()
    all_chars = list(characters.items())
    total = len(all_chars)

    if query_text:
        matched = [
            (char_id, char) for char_id, char in all_chars
            if query_text in char.get('name', '').lower()
            or query_text in str(char.get('rarity', '')).lower()
            or query_text in str(RARITY_CONFIG.get(char.get('rarity'), {}).get("symbol", ""))
        ]
    else:
        matched = all_chars

    matched.sort(key=lambda kv: (str(kv[1].get("name","")).lower(), str(kv[0])))

    end = min(offset + page_size, len(matched))
    if offset >= len(matched):
        print(f"[all] empty page q='{query_text}' matched={len(matched)} offset={offset}")
        await update.inline_query.answer([], cache_time=1, is_personal=True, next_offset="")
        return

    results = []
    for i in range(offset, end):
        char_id, char = matched[i]
        name_raw = char.get("name", "Unknown")
        name_md = md2_escape(name_raw.title())
        rarity = str(char.get("rarity", "❓"))
        rarity_md = md2_escape(rarity)
        symbol = RARITY_CONFIG.get(rarity, {}).get("symbol", "⭐")
        symbol_md = md2_escape(symbol)
        file_id = char.get("file_id")
        image_url = char.get("image_path")
        char_id_md = md2_escape(str(char_id))

        count_line_md = md2_escape(f"Found: {len(matched)}" if query_text else f"Total: {total}")
        caption = (
            f"{count_line_md}\n"
            f"OwO\\! Look who we found\\!\n"
            f"`{char_id_md}` • {symbol_md} *{name_md}*\n"
            f"🔮 *Rarity:* {symbol_md} `{rarity_md}`"
        )

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📦 Who collected?", callback_data=f"who_{char_id}")
        ]])

        if file_id:
            result = InlineQueryResultCachedPhoto(
                id=f"{char_id}_{offset+i}",
                photo_file_id=file_id,
                title=f"{char_id} • {name_raw}",
                caption=caption,
                parse_mode="MarkdownV2",
                reply_markup=keyboard
            )
        elif image_url and image_url.startswith(("http://","https://")):
            result = InlineQueryResultPhoto(
                id=f"{char_id}_{offset+i}",
                photo_url=image_url,
                thumbnail_url=image_url,
                title=name_raw,
                caption=caption,
                parse_mode="MarkdownV2",
                reply_markup=keyboard
            )
        else:
            print(f"[all] skip invalid image for {char_id}: {image_url}")
            continue

        results.append(result)

    next_offset = str(end) if end < len(matched) and results else ""

    print(f"[all] q='{query_text}' total={total} matched={len(matched)} offset={offset} end={end} returned={len(results)} next='{next_offset}'")
    if results:
        first = results[0]
        origin = "file_id" if isinstance(first, InlineQueryResultCachedPhoto) else "url"
        print(f"[all] first_result origin={origin} id={first.id}")

    await update.inline_query.answer(
        results,
        cache_time=1,
        is_personal=True,
        next_offset=next_offset
    )

async def who_collected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    parts = data.split("_", 1)
    if len(parts) != 2:
        await query.answer("⚠️ Invalid data.", show_alert=True)
        return
    char_id = parts[1]

    characters = load_characters()
    char = characters.get(char_id)
    if not char:
        await query.answer("⚠️ Character not found.", show_alert=True)
        return

    name_md = md2_escape(char.get("name", "Unknown").title())
    rarity = str(char.get("rarity", "❓"))
    rarity_md = md2_escape(rarity)
    symbol = RARITY_CONFIG.get(rarity, {}).get("symbol", "⭐")
    symbol_md = md2_escape(symbol)
    char_id_md = md2_escape(str(char_id))

    base_caption = (
        f"OwO\\! Look who we found\\!\n"
        f"`{char_id_md}` • {symbol_md} *{name_md}*\n"
        f"🔮 *Rarity:* {symbol_md} `{rarity_md}`"
    )

    rows=who_collected(char_id)

    if not rows:
        await query.answer("❌ Nobody has collected this waifu yet.", show_alert=True)
        return

    lines = ["📦 *Top Collectors:*"]
    for row in rows:
        user_id = row["user_id"]
        stack_count = row["stack_count"]
        username = get_user_display_name(user_id) or user_id
        username_md = md2_escape(username)
        lines.append(f"• [${username_md}](tg://user?id={user_id}) x{int(stack_count or 1)}".replace("$", ""))

    full_caption = base_caption + "\n\n" + "\n".join(lines)

    try:
        if query.inline_message_id:
            await context.bot.edit_message_caption(
                inline_message_id=query.inline_message_id,
                caption=full_caption,
                parse_mode="MarkdownV2"
            )
        elif query.message:
            await query.message.edit_caption(full_caption, parse_mode="MarkdownV2")
        else:
            await query.answer("⚠️ Can't edit caption.", show_alert=True)
            return
        await query.answer()
    except Exception as e:
        err = str(e)
        if "message is not modified" in err.lower():
            await query.answer()
            return
        print(f"[❌ Caption Edit Error] {err}")
        await query.answer("⚠️ Could not update caption.", show_alert=True)

def get_user_display_name(user_id: int) -> str:
    return get_balance(user_id,"Name")

def load_characters() -> Dict:


    if not os.path.exists(CHARACTER_JSON_PATH):
        return {}
    with open(CHARACTER_JSON_PATH, "r") as f:
        return json.load(f)

def normalize_name(name: str) -> str:
    return ''.join(name.lower().split())


def names_match(user_input: str, actual_name: str) -> bool:
    user_clean = normalize_name(user_input)
    if user_clean.startswith('/'):
        user_clean = user_clean[1:]
    
    actual_clean = actual_name.lower().split()  
    
    actual_words = [''.join(word.split()) for word in actual_clean]
    
    return user_clean in actual_words

ALLOWED_CHAT_IDS = [ -1002043895840,-1002120721604]  

def should_trigger_drop(chat_id: int):
    if chat_id not in ALLOWED_CHAT_IDS:
        return
    
    current=get_counters(chat_id,"Count")
    interval=get_counters(chat_id,"Interval")
    print(f"DEBUG {current}/{interval}")
    if current>=interval:
        update_counters(chat_id,"Count",0,reset=True)
        return True
    else:
        return False


def create_drop(chat_id: int) -> Optional[Dict]:
    print("Triggered Drop")
    characters = load_characters()
    
    if not characters:
        print("❌ No characters available to drop.")
        return None

    # Bride_characters = {cid: c for cid, c in characters.items() if str(c.get('rarity', '')).lower() == 'bride'}
    Bride_characters=characters
    
    if not Bride_characters:
        print("❌ No 'Bride' rarity characters available to drop.")
        return None

    char_id = random.choice(list(Bride_characters.keys()))
    char = Bride_characters[char_id]

    char_id= char_id
    char_name= char['name']
    rarity= char['rarity']
    image_path= char['image_path']
    
    update_drops(chat_id,char_id,char_name,rarity,image_path)

    return {
        'char_id': char_id,
        'char_name': char['name'],
        'rarity': char['rarity'],
        'image_path': char['image_path']
    }

def get_character_by_id(char_id: str) -> dict | None:
    characters = load_characters()
    return characters.get(char_id)



def get_user_harem(user_id: int, rarity_filter: str = None):

    owned = get_harem(user_id)
    if not owned:
        return []

    characters = load_characters()
    harem = []

    for char_id, stack_count in owned.items():
        if char_id not in characters:
            continue

        char = characters[char_id]

        if rarity_filter and str(char['rarity']) != rarity_filter:
            continue

        harem.append({
            "char_id": char_id,
            "name": char["name"],
            "rarity": char["rarity"],
            "stack_count": stack_count,
            "image_path": char.get("image_path", "characters/default.png"),
        })

    return harem


def get_rarity_cost(rarity) -> int:
    return RARITY_CONFIG.get(rarity, {"cost": 50})["cost"]

def get_rarity_display(rarity) -> str:
    return RARITY_CONFIG.get(rarity, {"display": str(rarity)})["display"]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = chat.id
    user_id = update.effective_user.id
    username = update.effective_user.first_name

    if chat.type == "private":
        return

    if update.message.text and update.message.text.startswith('/'):
        return

    if is_blocked(user_id):
        return

    update_counters(chat_id, "Count", 1)

    should_drop = should_trigger_drop(chat_id)
    if should_drop:
        drop = create_drop(chat_id)
        if drop:
            try:
                image_path = drop['image_path']
                is_url = re.match(r"^https?://", image_path)
                photo = image_path if is_url else open(image_path, "rb")
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption="✨ A wild Waifu has appeared!\nType /wish <name> to try your luck!",
                    parse_mode="Markdown"
                )
                if not is_url:
                    photo.close()
            except Exception as e:
                print(f"[DROP IMAGE ERROR] {e}")
        return

    last_user = context.chat_data.get("last_user")

    if last_user == user_id:
        ok, warn = increment_streak(user_id)
    else:
        reset_streak(last_user) if last_user else None
        ok, warn = increment_streak(user_id)

    doc=get_streak(user_id  )
    streak = doc.get("Streak", 0)

    context.chat_data["last_user"] = user_id

    if warn or streak >= 10:
        await update.message.reply_text(
            f"⚠️ {username}, you are blocked for 10 minutes due to spamming."
        )
        block_user(user_id)
        reset_streak(user_id)
        context.chat_data["last_user"] = None
        return




async def unlock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ADMIN_ID:
        await update.message.reply_text("❌ You need to be an admin to use this command.")
        return

    chat = update.effective_chat
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    else:
        await update.message.reply_text("⚠️ Please reply to the user's message to unlock them.")
        return

    if unblock_user(target_user.id):
        await update.message.reply_text(f"✅ User {target_user.first_name} has been unlocked from the spam block.")
    else:
        await update.message.reply_text("Error agaya h bc")

import os, re

async def trigger_character_drop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    while True:
        drop_data = create_drop(chat_id)
        rarity = drop_data.get("rarity")
        if rarity == "Bride":
            break
        else:
            print(f"[DROP REJECTED] Rarity is not 'School': {rarity}, retrying...")

    image_path = drop_data.get("image_path")
    if not image_path:
        print("[DROP ERROR] No image_path in drop_data")
        return

    if not isinstance(image_path, (str, bytes, bytearray)):
        print(f"[DROP ERROR] image_path invalid type: {type(image_path).__name__} -> {image_path}")
        return

    try:
        is_url = bool(re.match(r"^https?://", image_path))
        if is_url:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=image_path,
                caption="✨ A wild character has appeared!\nTry to /wish for them!",
                parse_mode="Markdown"
            )
        else:
            if not os.path.isabs(image_path):
                image_path = os.path.abspath(image_path)
            if not os.path.exists(image_path):
                print(f"[DROP IMAGE ERROR] Not found: {image_path} | cwd={os.getcwd()}")
                return
            with open(image_path, "rb") as photo:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption="✨ A wild character has appeared!\nTry to /wish for them!",
                    parse_mode="Markdown"
                )
    except Exception as e:
        print(f"[DROP IMAGE ERROR] {e}")


DAILY_WISH_LIMIT = 3
IST = ZoneInfo("Asia/Kolkata")

def today_key(ts: datetime | None = None) -> str:
    dt = datetime.now(IST) if ts is None else ts.astimezone(IST)
    return dt.strftime('%Y-%m-%d')


wish_usage_cache: dict[int, dict[str, int]] = {}

async def can_use_wish_mem(user_id: int) -> tuple[bool, int]:
    day = today_key()
    used = wish_usage_cache.get(user_id, {}).get(day, 0)
    return used < DAILY_WISH_LIMIT, DAILY_WISH_LIMIT - used

async def record_wish_mem(user_id: int) -> int:
    day = today_key()
    user = wish_usage_cache.setdefault(user_id, {})
    user[day] = user.get(day, 0) + 1
    return user[day]

import random
WISH_LIMIT_BLOCK_MSG = "Daily /wish limit reached (3/3). Try again tomorrow (resets at 00:00 IST)."

async def wish_command(update: 'Update', context: 'ContextTypes.DEFAULT_TYPE'):
    ADMIN_USER_ID = 5192424390
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.first_name

    if is_blocked(user_id):
        await update.message.reply_text(f"⛔ {username}, you are temporarily blocked from using /wish due to spamming. Try again later.")
        return

    can, remaining = await can_use_wish_mem(user_id)
    if not can:
        await update.message.reply_text(WISH_LIMIT_BLOCK_MSG)
        return

    if not context.args:
        await update.message.reply_text("Usage: `/wish <character name>`", parse_mode="Markdown")
        return

    guessed_name = " ".join(context.args)
    active_drop = get_drops(chat_id)
    if not active_drop:
        await update.message.reply_text("No character available to wish for!")
        return

    if not names_match(guessed_name, active_drop['Char name']):
        await update.message.reply_text("That's not who appeared! Try again.")
        return

    rarity_key = int(active_drop['Rarity']) if str(active_drop['Rarity']).isdigit() else str(active_drop['Rarity'])
    rarity_info = RARITY_CONFIG.get(rarity_key, {"cost": 50, "chance": 0.5, "display": "⭐ Unknown", "symbol": "⭐"})
    cost, chance = rarity_info["cost"], rarity_info["chance"]
    rarity_display, rarity_symbol = rarity_info["display"], rarity_info["symbol"]

    current_lunars = get_balance(user_id,"Lunar Crystals")
    if current_lunars < cost:
        await update.message.reply_text(f"Not enough 🌙 Lunar Crystals! You need {cost} but have {current_lunars}.")
        return

    if not update_balance(user_id,"Lunar Crystals",-cost):
        await update.message.reply_text("❌ Failed to deduct Lunars.")
        return

    user_name = username
    char_name = active_drop['Char name']
    char_id = active_drop['Char id']

    success = (random.random() <= 100)
    clear_active_drop(chat_id)

    used = await record_wish_mem(user_id)
    remaining_after = max(0, DAILY_WISH_LIMIT - used)

    if success:
        update_harem(user_id,char_id,1,rarity=None)
        await update.message.reply_text(
            f"✅ *{user_name}*, you got a new waifu!\n\n"
            f"🌸 *NAME:* {char_name}\n"
            f"{rarity_symbol} *RARITY:* {rarity_display}\n"
            f"🌙 *Lunar Crystals USED:* {cost}\n"
            f"📅 Remaining wishes today: {remaining_after}/{DAILY_WISH_LIMIT}",
            parse_mode="Markdown"
        )
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=f"🎉 {user_name} got {char_name} ({rarity_display}⭐)")
    else:
        await update.message.reply_text(
            f"😔 *{user_name}*, you tried to wish for *{char_name}*, but they slipped away...\n"
            f"🌙 *Lunar Crystals LOST:* {cost}\n"
            f"📅 Remaining wishes today: {remaining_after}/{DAILY_WISH_LIMIT}",
            parse_mode="Markdown"
        )
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=f"💨 {user_name} failed to get {char_name} ({rarity_display}⭐)")

async def get_waifus(waifus,rarity):
    if not waifus:
        return[]
    char1=load_characters()
    harem=[]

    for char_id,stack_count in waifus.items():
        if char_id not in char1:
            continue

        char=char1[char_id]
        if rarity and str(char['rarity'])!=rarity:
            continue

        image_path=char.get('image_path',None)
        harem.append(
            {
                'char_id':char_id,
                'name':char['name'],
                'rarity':char['rarity'],
                'stack_count':stack_count,
                'image_path':image_path
            }
        )
    return harem

async def harem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("harem cmmd triggered")

    user = update.effective_user
    user_id = user.id
    first_name = user.first_name or user.username or "User"
    update_name(user_id,first_name)

    rarity_filter = get_harem_rarity(user_id)
    waifus = get_harem(user_id)
    harem=await get_waifus(waifus,rarity=rarity_filter)
    print('got user harem')

    if not harem:
        filter_msg = f" (filtered by {rarity_filter})" if rarity_filter else ""
        await update.message.reply_text(
            f"Your harem is empty{filter_msg}! Start wishing for characters when they drop."
        )
        return

    await send_harem_page(update, context, user_id, 1, 'date')

async def send_harem_page(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, page: int, sort_by: str):
    rarity_filter = get_harem_rarity(user_id)
    waifus = get_harem(user_id)
    harem=await get_waifus(waifus,rarity=rarity_filter)

    if not harem:
        filter_msg = f" (filtered by {rarity_filter})" if rarity_filter else ""
        await update.message.reply_text(f"\u274c Your harem is empty{filter_msg}!")
        return

    fav_id = get_fav(user_id)


    chars_per_page = 10
    total_pages = math.ceil(len(harem) / chars_per_page)
    page = max(1, min(page, total_pages))
    start_idx, end_idx = (page - 1) * chars_per_page, page * chars_per_page
    page_chars = harem[start_idx:end_idx]

    user_name = update.effective_user.first_name
    filter_info = f" • {rarity_filter} Only" if rarity_filter else ""
    caption = f"👑 *{user_name}'s Harem* — Page {page}/{total_pages}{filter_info}\n"
    caption += "=" * 35+ "\n"

    for char in page_chars:
        rarity_data = RARITY_CONFIG.get(char['rarity'], {"symbol": "⭐"})
        symbol = rarity_data.get("symbol", "⭐")
        stack = f" ×{char['stack_count']}" if char['stack_count'] > 1 else ""
        fav = " 💖" if char['char_id']==fav_id else ""
        caption += f"➔ `{char['char_id']}` | {symbol} | {char['name'].title()}{stack}{fav}\n"

    caption += "=" * 35

    keyboard = []

    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton("⬅️ Prev", callback_data=f"harem_page_{page - 1}_{sort_by}_{user_id}")
        )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton("Next ➡️", callback_data=f"harem_page_{page + 1}_{sort_by}_{user_id}")
        )
    if nav_row:
        keyboard.append(nav_row)

  
    action_row = [
        InlineKeyboardButton("🖼 View Gallery", switch_inline_query_current_chat=f"harem:{user_id}"),
        InlineKeyboardButton("❌ Close", callback_data=f"harem_close_{user_id}")
    ]
    keyboard.append(action_row)

    
    display_char = next((char for char in harem if char['char_id'] == fav_id),None)
    if display_char is None:
        display_char = random.choice(harem) if harem else None
    print(char,fav_id)
    image_path = display_char.get('image_path', 'characters/default.png') if display_char else 'characters/default.png'
    print(image_path)
    is_url = re.match(r'^https?://', image_path)

    try:
        print("✅ Sending harem page...")
        if is_url:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image_path,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            with open(image_path, "rb") as img_file:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=img_file,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
    except Exception as e:
        print("❌ Failed to send harem photo, fallback to text:", e)
        await update.message.reply_text(
            text=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )


async def harem_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    data_parts = data.split('_')

    if data.startswith("harem_page_"):
        page = int(data_parts[2])
        sort_by = data_parts[3]
        owner_id = int(data_parts[4])

        if user_id != owner_id:
            await query.answer("❌ You can't control someone else's harem.", show_alert=True)
            return

        await query.answer()

        rarity_filter = get_harem_rarity(owner_id)
        waifus = get_harem(owner_id)
        harem = await get_waifus(waifus, rarity=rarity_filter)


        if not harem:
            await query.edit_message_caption("\u274c Harem empty.")
            return

        fav_id = get_fav(user_id)

        chars_per_page = 10
        total_pages = math.ceil(len(harem) / chars_per_page)
        page = max(1, min(page, total_pages))
        start_idx, end_idx = (page - 1) * chars_per_page, page * chars_per_page
        page_chars = harem[start_idx:end_idx]

        user_name = query.from_user.first_name
        filter_info = f" • {rarity_filter} Only" if rarity_filter else ""
        caption = f"👑 *{user_name}'s Harem* — Page {page}/{total_pages}{filter_info}\n"
        caption += "=" * 35 + "\n"

        for char in page_chars:
            rarity_data = RARITY_CONFIG.get(char['rarity'], {"symbol": "⭐"})
            symbol = rarity_data.get("symbol", "⭐")
            stack = f" ×{char['stack_count']}" if char['stack_count'] > 1 else ""
            fav = " 💖" if char['char_id']==fav_id else ""
            caption += f"➔ `{char['char_id']}` | {symbol} | {char['name'].title()}{stack}{fav}\n"

        caption += "=" * 35

        keyboard = []
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"harem_page_{page - 1}_{sort_by}_{owner_id}"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"harem_page_{page + 1}_{sort_by}_{owner_id}"))
        if nav_row:
            keyboard.append(nav_row)

        action_row = [
            InlineKeyboardButton("🖼 View Gallery", switch_inline_query_current_chat=f"harem:{owner_id}"),
            InlineKeyboardButton("❌ Close", callback_data=f"harem_close_{owner_id}")
        ]
        keyboard.append(action_row)

        display_char = next((char for char in harem if char['char_id'] == fav_id), None)
        if display_char is None:
            display_char = random.choice(harem) if harem else None
        image_path = display_char.get('image_path', 'characters/default.png') if display_char else 'characters/default.png'

        is_url = re.match(r'^https?://', image_path)

        try:
            if is_url:
                await query.edit_message_media(
                    media=InputMediaPhoto(media=image_path, caption=caption, parse_mode="Markdown"),
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                with open(image_path, "rb") as img_file:
                    await query.edit_message_media(
                        media=InputMediaPhoto(media=img_file, caption=caption, parse_mode="Markdown"),
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
        except Exception as e:
            print("❌ Failed to edit harem page:", e)
        return

    elif data.startswith("harem_close_"):
        owner_id = int(data.split("_")[2])
        if user_id != owner_id:
            await query.answer("\u274c Only the owner can close this.", show_alert=True)
            return
        await query.answer()
        await query.delete_message()
        return


    elif data.startswith("harem_info_"):
        char_id = data.split("_")[2]
        characters = load_characters()
        char = characters.get(char_id)

        if not char:
            await query.answer("\u274c Character not found.")
            return

        rarity = char.get("rarity", "❓")
        symbol = RARITY_CONFIG.get(rarity, {}).get("symbol", "⭐")
        caption = f"*ID:* `{char_id}`\n*Name:* {char['name'].title()}\n*Rarity:* {rarity} {symbol}"

        await query.edit_message_media(
            media=InputMediaPhoto(media=char['image_path'], caption=caption, parse_mode="Markdown")
        )

async def rarity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    current_filter = get_harem_rarity(user_id)

    keyboard = []
    rarity_buttons = []

    for rarity, config in RARITY_CONFIG.items():
        display = config.get("display", str(rarity))
        rarity_buttons.append(
            InlineKeyboardButton(
                f"{display}", callback_data=f"rarity_set_{rarity}_{user_id}"
            )
        )
    
    for i in range(0, len(rarity_buttons), 3):
        keyboard.append(rarity_buttons[i:i+3])
    
    keyboard.append([
        InlineKeyboardButton("🌟 Show All", callback_data=f"rarity_all_{user_id}"),
        InlineKeyboardButton("❌ Close", callback_data=f"rarity_close_{user_id}")
    ])
    
    filter_text = f"Current filter: {current_filter}" if current_filter else "No filter active"
    text = f"🎯 Rarity Filter Settings\n\n{filter_text}\n\nSelect a rarity to filter your harem:"
    
    await update.message.reply_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def rarity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    data_parts = data.split('_')

    if len(data_parts) >= 4 and data_parts[0] == 'rarity' and data_parts[1] == 'set':
        rarity = data_parts[2]
        owner_id = int(data_parts[3])

        if user_id != owner_id:
            await query.answer("❌ You can't control someone else's settings.", show_alert=True)
            return

        update_harem(user_id, char_id=None, count=0, rarity=rarity, replace=True)

        rarity_display = RARITY_CONFIG.get(rarity, {}).get("display", str(rarity))
        
        await query.answer(f"✅ Filter set to {rarity_display}")
        await query.edit_message_text(
            text=f"✅ **Rarity Filter Updated**\n\n"
                 f"Your harem will now only show **{rarity_display}** characters.\n"
                 f"Use `/harem` to view your filtered collection!",
            parse_mode="Markdown"
        )
        return

    if data.startswith("rarity_all_"):
        owner_id = int(data.split("_")[2])
        if user_id != owner_id:
            await query.answer("❌ You can't control someone else's settings.", show_alert=True)
            return


        update_harem(user_id, char_id=None, count=0, rarity=None, replace=True)

        
        await query.answer("✅ Filter removed")
        await query.edit_message_text(
            text="✅ **Rarity Filter Removed**\n\n"
                 "Your harem will now show all characters.\n"
                 "Use `/harem` to view your full collection!",
            parse_mode="Markdown"
        )
        return

    if data.startswith("rarity_close_"):
        owner_id = int(data.split("_")[2])
        if user_id != owner_id:
            await query.answer("❌ Only the owner can close this.", show_alert=True)
            return

        await query.answer()
        await query.delete_message()
        return

import re 

async def fav_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Usage: `/fav <character_id>`", parse_mode="Markdown")
        return

    raw_id = context.args[0]
    char_id = raw_id.lstrip("0").zfill(3)

    if char_id not in get_harem(user_id):
        await update.message.reply_text("❌ You don't own this character!")
        return

    characters = load_characters()
    if char_id not in characters:
        await update.message.reply_text("❌ Character not found!")
        return

    char = characters[char_id]
    rarity_display = get_rarity_display(char['rarity'])

    keyboard = [[
        InlineKeyboardButton("✅ Yes", callback_data=f"fav_yes_{char_id}_{user_id}"),
        InlineKeyboardButton("❌ No", callback_data="fav_no")
    ]]

    caption = f"Set *{rarity_display} {char['name']}* as your harem display?"

    try:
        image_path = char['image_path']
        is_url = re.match(r"^https?://", image_path)

        if is_url:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image_path,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            with open(image_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

    except Exception as e:
        print(f"[FAV IMAGE ERROR] {e}")
        await update.message.reply_text(
            text=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
async def fav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data_parts = query.data.split('_')

    if data_parts[0] == 'fav':
        if data_parts[1] == 'yes' and len(data_parts) == 4:
            char_id = data_parts[2]
            allowed_user_id = int(data_parts[3])

            if user_id != allowed_user_id:
                await query.reply_text("⚠️ You can't set someone else's favorite.")
                return

            if set_fav(user_id, char_id):
                characters = load_characters()
                char = characters.get(char_id)
                if not char:
                    await query.edit_message_caption("❌ Character not found.")
                    return

                rarity_display = get_rarity_display(char['rarity'])
                name = char['name']
                caption = f"✅ *{rarity_display} {name}* is now your harem display character!"

                await query.edit_message_caption(caption, parse_mode="Markdown")
            else:
                await query.edit_message_caption("❌ Failed to set favorite character.")
        
        elif data_parts[1] == 'no':
            await query.delete_message()

async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    sender_id = sender.id

    if not update.message.reply_to_message:
        await update.message.reply_text("❗ Reply to a user with `/gift <char_id>` to gift them a character.")
        return

    receiver = update.message.reply_to_message.from_user
    receiver_id = receiver.id

    if sender_id == receiver_id:
        await update.message.reply_text("🙅 You can't gift a character to yourself!")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/gift <char_id>`", parse_mode="Markdown")
        return

    char_id = context.args[0].zfill(3)

    character = get_character_by_id(char_id)
    if not character:
        await update.message.reply_text("❌ Character not found.")
        return

    success = transfer_character(sender_id, receiver_id, char_id)

    if not success:
        await update.message.reply_text("⚠️ You don't own that character.")
        return

    rarity = character.get("rarity", "Unknown")
    rarity_display = RARITY_CONFIG.get(rarity, {}).get("display", rarity)
    symbol = RARITY_CONFIG.get(rarity, {}).get("symbol", "🎴")

    await update.message.reply_text(
        f"🎁 *Gift Successful!*\n\n"
        f"👤 *Sender:* {sender.mention_markdown()}\n"
        f"👥 *Receiver:* {receiver.mention_markdown()}\n"
        f"🎴 *Character:* {symbol} *{character['name']}* `#{char_id}`\n"
        f"⭐ *Rarity:* {rarity_display}",
        parse_mode="Markdown"
    )



def get_rarity_details(rarity):
    info = RARITY_CONFIG.get(rarity, {})
    return {
        "cost": info.get("cost", 50),
        "chance": info.get("chance", 1.0),
        "display": info.get("display", str(rarity)),
        "symbol": info.get("symbol", "🎐")
    }

async def hall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):


    keyboard = []
    row = []

    for idx, (rarity, config) in enumerate(RARITY_CONFIG.items(), start=1):
        display = config.get("display", str(rarity))
        row.append(InlineKeyboardButton(display, callback_data=f"hall_rarity_{rarity}"))
        if idx % 3 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("📜 Show All", callback_data="hall_rarity_ALL")
    ])

    await update.message.reply_text(
        "📜 *HALL OF CHARACTERS*\nChoose a rarity to filter by:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def hall_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    await query.answer()

    try:
        characters = load_characters()
    except Exception:
        await query.edit_message_text("❌ Failed to load character list.")
        return

    selected_rarity = data.split("hall_rarity_")[1]

    user_id = query.from_user.id

    if selected_rarity == "ALL" and user_id not in ADMIN_IDS:
        await query.edit_message_text("🚫 You are not authorized to view *ALL* characters.")
        return

    filtered = []
    for char_id, char in characters.items():
        char_rarity = str(char.get("rarity"))
        if selected_rarity == "ALL" or selected_rarity == char_rarity:
            filtered.append((char_id, char))

    if not filtered:
        await query.edit_message_text("❌ No characters with that rarity.")
        return

    msg = ""
    if selected_rarity != "ALL":
        rarity_info = RARITY_CONFIG.get(selected_rarity, {})
        symbol = rarity_info.get("symbol", "⭐")
        display = rarity_info.get("display", selected_rarity)
        msg += f"{symbol} *{display}*\n"

    for char_id, char in filtered:
        rarity = char["rarity"]
        r_info = RARITY_CONFIG.get(rarity, {})
        msg += (
            f"ID: {char_id}\n"
            f"Name: {char['name']}\n"
            f"Rarity: {r_info.get('display', rarity)}\n"
            f"Symbol: {r_info.get('symbol', '⭐')}\n"
            f"Lunars: {r_info.get('cost', 100)}\n"
            f"Capture Chance: {int(r_info.get('chance', 1.0) * 100)}%\n"
            f"---\n"
        )

    if len(msg) > 4000:
        parts = [msg[i:i + 4000] for i in range(0, len(msg), 4000)]
        for part in parts:
            await query.message.reply_text(part)
        await query.delete_message()
    else:
        await query.edit_message_text(msg, parse_mode="Markdown")



ADMIN_IDS = [5105207985, 5192424390,6057581189,5716946356,6792709908]
LOG_ADMIN_ID = 5192424390  


def is_admin_dm(update: Update) -> bool:
    return (update.message.from_user.id in ADMIN_IDS and 
            update.message.chat.type == 'private')

async def add_char_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_dm(update):
        await update.message.reply_text("❌ This command is only available for admin in DM.")
        return

    await update.message.reply_text("📸 Send the character image (JPG/PNG/WEBP/GIF).")
    context.user_data["add_char_stage"] = "awaiting_image"

import os
import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from cloudinary.uploader import upload as cloudinary_upload

WAIFUS_JSON = os.path.join(BASE_PATH, "waifus.json")
CHARACTER_IMAGE_DIR = os.path.join(BASE_PATH, "images") 

async def handle_add_char_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_dm(update):
        return

    if context.user_data.get("add_char_stage") != "awaiting_image":
        return

    if not update.message.photo:
        await update.message.reply_text("❌ Please send a valid image.")
        return

    try:
        file = await update.message.photo[-1].get_file()
        context.user_data["temp_file"] = file
        context.user_data["add_char_stage"] = "awaiting_name"

        await update.message.reply_text("✅ Image received!\n📝 Now send the character name (e.g., `shenhe`).")

    except Exception as e:
        await update.message.reply_text(f"❌ Error processing image: {str(e)}")
        context.user_data.clear()


async def handle_dynamic_char_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_dm(update):
        return

    stage = context.user_data.get("add_char_stage")
    message_text = update.message.text.strip()

    if stage == "awaiting_name":
        name = message_text
        context.user_data["char_name"] = name
        context.user_data["add_char_stage"] = "awaiting_rarity"
        rarity_options = "`, `".join(str(r) for r in RARITY_CONFIG.keys())
        await update.message.reply_text(
            f"✅ Name set to: {name}\n⭐ Now send rarity like `{rarity_options}`"
        )
        return

    elif stage == "awaiting_rarity":
        rarity_input = message_text.strip()
        matched_rarity = None

        for key in RARITY_CONFIG:
            if isinstance(key, int) and rarity_input.isdigit() and int(rarity_input) == key:
                matched_rarity = key
                break
            elif isinstance(key, str) and rarity_input.lower() == key.lower():
                matched_rarity = key
                break

        if matched_rarity is None:
            valid = "`, `".join(str(k) for k in RARITY_CONFIG)
            await update.message.reply_text(f"❌ Invalid rarity. Use one of: `{valid}`")
            return

        rarity = matched_rarity
        name = context.user_data.get("char_name")
        temp_file = context.user_data.get("temp_file")

        try:
            image_bytes = await temp_file.download_as_bytearray()
            result = cloudinary_upload(image_bytes, folder="waifus")
            cloud_url = result['secure_url']
            filename = os.path.basename(result['public_id']) + ".jpg"

            if os.path.exists(CHARACTER_JSON_PATH):
                with open(CHARACTER_JSON_PATH, "r", encoding="utf-8") as f:
                    characters = json.load(f)
            else:
                characters = {}

            updated = False
            updated_id = None

            for cid, char in characters.items():
                if char["name"].lower() == name.lower() and str(char["rarity"]).lower() == str(rarity).lower():
                    updated = True
                    updated_id = cid
                    break

            if not updated:
                existing_ids = [int(k) for k in characters.keys() if k.isdigit()]
                updated_id = str(max(existing_ids + [0]) + 1).zfill(3)

            context.user_data["confirm_payload"] = {
                "name": name,
                "rarity": rarity,
                "image_path": cloud_url,
                "updated": updated,
                "updated_id": updated_id,
                "characters": characters,
                "filename": filename
            }

            action_text = "♻️ *Editing existing character*" if updated else "🆕 *Adding new character*"
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data="confirm_char"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel_char")
                ]
            ]

            await update.message.reply_text(
                f"{action_text}\n\n"
                f"*ID:* `{updated_id}`\n"
                f"*Name:* {name}\n"
                f"*Rarity:* {rarity}\n\n"
                f"🌐 Cloud URL: {cloud_url}\nDo you want to save this character?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

        except Exception as e:
            await update.message.reply_text(f"❌ Upload error: {str(e)}")
            context.user_data.clear()


async def handle_char_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    payload = context.user_data.get("confirm_payload")

    if not payload:
        await query.edit_message_text("❌ Session expired or invalid.")
        return

    if query.data == "cancel_char":
        context.user_data.clear()
        await query.edit_message_text("❌ Character creation/editing cancelled.")
        return

    if query.data == "confirm_char":
        characters = payload["characters"]
        updated_id = payload["updated_id"]

        characters[updated_id] = {
            "name": payload["name"],
            "rarity": payload["rarity"],
            "image_path": payload["image_path"]
        }

        with open(CHARACTER_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(characters, f, indent=2, ensure_ascii=False)

        await query.edit_message_text(
            f"✅ Saved character!\n\n*ID:* `{updated_id}`\n*Name:* {payload['name']}\n*Rarity:* {payload['rarity']}",
            parse_mode="Markdown"
        )
        CHANNEL_ID = -1002871188921
        log_text = (
            f"📥 *Character {'Updated' if payload['updated'] else 'Added'} by:* "
            f"`{query.from_user.full_name}` (`{query.from_user.id}`)\n"
            f"*ID:* `{updated_id}`\n"
            f"*Name:* {payload['name']}\n"
            f"*Rarity:* {payload['rarity']}\n"
            f"*Saved to:* `{payload['image_path']}`"
        )

        await context.bot.send_message(
        chat_id=LOG_ADMIN_ID,
        text=log_text,
        parse_mode="Markdown"
    )

        await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=log_text,
        parse_mode="Markdown"
    )

        context.user_data.clear()



async def cancel_add_char(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_dm(update):
        await update.message.reply_text("❌ This command is only available for admin in DM.")
        return

    user = update.effective_user

    if context.user_data.get("add_char_stage"):
        context.user_data.clear()
        await update.message.reply_text("❌ Character addition cancelled.")

        await context.bot.send_message(
            chat_id=LOG_ADMIN_ID,
            text=f"⚠️ *Character addition cancelled by:* `{user.full_name}` (`{user.id}`)",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("ℹ️ No active character addition process to cancel.")

def is_admin(update: Update) -> bool:
    return update.message.from_user.id in ADMIN_IDS

async def open_char(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /open <id>")
        return

    try:
        char_id = str(int(context.args[0])).zfill(3)
        with open(CHARACTER_JSON_PATH, "r", encoding="utf-8") as f:
            characters = json.load(f)

        if char_id not in characters:
            await update.message.reply_text("❌ Character ID not found.")
            return

        char = characters[char_id]
        img_path = char.get("image_path")

        caption = (
            f"*ID:* `{char_id}`\n"
            f"*Name:* {char['name']}\n"
            f"*Rarity:* {char['rarity']}\n"
        )

        is_url = re.match(r"^https?://", img_path)

        if is_url:
            await update.message.reply_photo(
                photo=img_path,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN
            )
        elif os.path.exists(img_path):
            with open(img_path, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN
                )
        else:
            await update.message.reply_text("❌ Image not found locally or URL is invalid.")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {type(e).__name__}\n{e}")


async def delete_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("🚫 You don't have permission to use this command.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: /delete <id>")
        return

    char_id = context.args[0].zfill(3)
    if not os.path.exists(CHARACTER_JSON_PATH):
        await update.message.reply_text("❌ characters.json not found.")
        return

    with open(CHARACTER_JSON_PATH, "r", encoding="utf-8") as f:
        characters = json.load(f)

    char = characters.get(char_id)
    if not char:
        await update.message.reply_text(f"❌ Character ID `{char_id}` not found.", parse_mode="Markdown")
        return

    context.user_data["pending_delete"] = {
        "char_id": char_id,
        "name": char["name"],
        "rarity": char["rarity"],
        "image_path": char.get("image_path"),
        "requester_id": user_id
    }

    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, delete", callback_data="confirm_delete"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")
        ]
    ]

    await update.message.reply_text(
        f"⚠️ Are you sure you want to delete:\n\n"
        f"*ID:* `{char_id}`\n"
        f"*Name:* `{char['name']}`\n"
        f"*Rarity:* `{char['rarity']}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def delete_character_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    pending = context.user_data.get("pending_delete")

    if not pending:
        await query.edit_message_text("⚠️ No character pending deletion.")
        return

    if user_id != pending.get("requester_id"):
        await query.answer("❌ Only the original requester can confirm this.", show_alert=True)
        return

    if query.data == "cancel_delete":
        await query.edit_message_text("❎ Character deletion cancelled.")
        context.user_data.pop("pending_delete", None)
        return

    char_id = pending["char_id"]
    name = pending["name"]
    rarity = pending["rarity"]
    image_path = pending["image_path"]

    try:
        with open(CHARACTER_JSON_PATH, "r", encoding="utf-8") as f:
            characters = json.load(f)

        if char_id in characters:
            del characters[char_id]

        with open(CHARACTER_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(characters, f, indent=2, ensure_ascii=False)
    except Exception as e:
        await query.edit_message_text(f"❌ Error updating JSON: {e}")
        return

    if image_path:
        try:
            if image_path.startswith("https://res.cloudinary.com/"):
                match = re.search(r'/waifus/(.+?)\.(jpg|jpeg|png|webp|gif|bmp)$', image_path)
                if match:
                    public_id = f"waifus/{match.group(1)}"
                    cloudinary.uploader.destroy(public_id)
            elif os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            print(f"[Image Delete Error] {e}")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_inventory WHERE char_id = ?", (char_id,))
        removed = cursor.rowcount
        conn.commit()
        conn.close()
    except Exception as e:
        await query.edit_message_text(f"✅ Character deleted but DB cleanup failed:\n`{e}`", parse_mode="Markdown")
        context.user_data.pop("pending_delete", None)
        return

    await query.edit_message_text(
        f"✅ Deleted character:\n\n"
        f"*ID:* `{char_id}`\n"
        f"*Name:* {name}\n"
        f"*Rarity:* {rarity}\n"
        f"🗃️ Removed from user inventory: `{removed}` records.",
        parse_mode="Markdown"
    )
    context.user_data.pop("pending_delete", None)



async def force_drop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_ID:
        await update.message.reply_text("❌ This command is admin-only.")
        return

    await trigger_character_drop(update, context)

async def set_drop_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if user_id not in ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /interval <messages> (e.g. /interval 50)")
        return

    interval = max(1, int(context.args[0]))

    update_counters(chat_id,"Interval",interval)

    await update.message.reply_text(f"✅ Drop interval set to every {interval} messages.")


from telegram import InputFile
import shutil

awaiting_json_restore = {} 

async def clear_json_flag_later(user_id, delay=120):
    await asyncio.sleep(delay)
    awaiting_json_restore.pop(user_id, None)

async def backup_characters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("❌ You're not authorized.")
        return

    try:
        with open(CHARACTER_JSON_PATH, "rb") as f:
            await update.message.reply_document(
                document=InputFile(f, filename="characters_backup.json"),
                caption="📦 Here is your character backup.\n📥 Now upload your `.json` within 2 minutes to restore."
            )
        awaiting_json_restore[user_id] = True
        asyncio.create_task(clear_json_flag_later(user_id))
    except FileNotFoundError:
        await update.message.reply_text("❌ characters.json not found.")

async def handle_uploaded_json_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        return

    if not awaiting_json_restore.get(user_id):
        return 

    document = update.message.document
    if not document or not document.file_name.endswith(".json"):
        return

    try:
        tg_file = await document.get_file()
        await tg_file.download_to_drive("characters_upload.json")
        await update.message.reply_text("📥 File saved as `characters_upload.json`. Use /restorechars to load it.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to upload JSON: {e}")

    awaiting_json_restore.pop(user_id, None)

async def restore_characters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("❌ You’re not authorized.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("ℹ️ Reply to the uploaded `.json` file with /restorechars.")
        return

    doc_msg = update.message.reply_to_message

    if not doc_msg.document or not doc_msg.document.file_name.endswith(".json"):
        await update.message.reply_text("❌ That’s not a .json file.")
        return

    try:

        file = await doc_msg.document.get_file()
        await file.download_to_drive("characters_upload.json")
    except Exception as e:
        await update.message.reply_text(f"❌ Download failed: {e}")
        return

    try:
        shutil.copyfile("characters_upload.json", CHARACTER_JSON_PATH)
        await update.message.reply_text("✅ characters.json restored successfully! (new file created if none existed)")
    except Exception as e:
        await update.message.reply_text(f"❌ Restore failed: {e}")
        return
    awaiting_json_restore.pop(user_id, None)



awaiting_image_restore = {}  

async def clear_image_flag_later(user_id, delay=120):
    await asyncio.sleep(delay)
    awaiting_image_restore.pop(user_id, None)

async def backup_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("❌ You're not authorized.")
        return

    if not os.path.exists(CHARACTER_IMAGE_DIR):
        await update.message.reply_text("❌ No image folder found.")
        return

    with zipfile.ZipFile(IMAGE_ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(CHARACTER_IMAGE_DIR):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, CHARACTER_IMAGE_DIR)
                zipf.write(full_path, arcname)

    with open(IMAGE_ZIP_PATH, "rb") as f:
        await update.message.reply_document(
            InputFile(f, filename="characters_backup.zip"),
            caption="🖼 Character images backup.\n📥 Now upload your `.zip` and reply to it with /restoreimages within 2 minutes."
        )

    awaiting_image_restore[user_id] = True
    asyncio.create_task(clear_image_flag_later(user_id))

async def handle_uploaded_image_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        return

    if not awaiting_image_restore.get(user_id):
        return 

    document = update.message.document
    if not document or not document.file_name.endswith(".zip"):
        return

    try:
        tg_file = await document.get_file()
        await tg_file.download_to_drive("characters_upload.zip")
        await update.message.reply_text("📥 File saved as `characters_upload.zip`. Reply to it with /restoreimages to restore.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to upload ZIP: {e}")

    awaiting_image_restore.pop(user_id, None)

async def restore_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("❌ You're not authorized.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("ℹ️ Reply to the ZIP file with /restoreimages.")
        return

    doc_msg = update.message.reply_to_message
    if not doc_msg.document or not doc_msg.document.file_name.endswith(".zip"):
        await update.message.reply_text("❌ That’s not a .zip file.")
        return

    try:
        tg_file = await doc_msg.document.get_file()
        await tg_file.download_to_drive("characters_upload.zip")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to download ZIP: {e}")
        return

    try:
        os.makedirs(CHARACTER_IMAGE_DIR, exist_ok=True)
        for file in os.listdir(CHARACTER_IMAGE_DIR):
            file_path = os.path.join(CHARACTER_IMAGE_DIR, file)
            if os.path.isfile(file_path):
                os.remove(file_path)

        with zipfile.ZipFile("characters_upload.zip", "r") as zip_ref:
            zip_ref.extractall(CHARACTER_IMAGE_DIR)

        await update.message.reply_text("✅ Character images restored successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Restore failed: {e}")


async def hmsg_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    interval=get_counters(chat_id,"Interval")
    count=get_counters(chat_id,"Count")
    remaining = interval - count
    msg = "💖 **Harem Drop Counter**\n"
    msg += f"💬 Messages: {count}/{interval}\n"
    msg += f"⏳ Remaining: {remaining} messages until next drop"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def add_waifu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ADMIN_ID:
        await update.message.reply_text("BAKA! You don't have rights.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ *Reply to someone to add waifu!*\nUsage: `/addwaifu <id>`",
            parse_mode="Markdown"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ *No character ID provided!*\nUsage: `/addwaifu <id>`",
            parse_mode="Markdown"
        )
        return

    try:
        char_id = context.args[0].zfill(3)

        target_user = update.message.reply_to_message.from_user
        target_id = target_user.id
        target_name = target_user.full_name

        # Load characters from JSON
        characters = load_characters()
        char_info = characters.get(char_id)

        if not char_info:
            await update.message.reply_text(f"❌ Character ID `{char_id}` not found.")
            return

        increment_character(target_id, char_id)

        name = char_info.get("name", "Unknown")
        rarity = char_info.get("rarity")
        symbol = RARITY_CONFIG.get(rarity, {}).get("symbol", "⭐")

        await update.message.reply_text(
            f"✅ Added *{name}* ({char_id}) to `{target_name}`'s harem.\n"
            f"🔮 Rarity: {symbol} `{rarity}`",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Failed to add waifu.\nError: `{e}`", parse_mode="Markdown")
async def remove_waifu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ADMIN_ID:
        await update.message.reply_text("BAKA! You don't have rights.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ *Reply to someone to remove waifu!*\nUsage: `/rwaifu <id>`",
            parse_mode="Markdown"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ *No character ID provided!*",
            parse_mode="Markdown"
        )
        return

    try:
        char_id = context.args[0].zfill(3)
        target_user = update.message.reply_to_message.from_user
        target_id = target_user.id
        target_name = target_user.full_name

        characters = load_characters()
        char_info = characters.get(char_id)

        if not char_info:
            await update.message.reply_text(f"❌ Character ID `{char_id}` not found.")
            return

        if not user_has_character(target_id, char_id):
            await update.message.reply_text(
                f"❌ {target_name} doesn't have waifu `{char_id}`."
            )
            return

        decrement_character(target_id, char_id)

        name = char_info.get("name", "Unknown")
        rarity = char_info.get("rarity")
        symbol = RARITY_CONFIG.get(rarity, {}).get("symbol", "⭐")

        await update.message.reply_text(
            f"🗑️ Removed *{name}* ({char_id}) from `{target_name}`'s harem.\n"
            f"🔮 Rarity: {symbol} `{rarity}`",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed.\nError: `{e}`",
            parse_mode="Markdown"
        )
async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ *Reply to someone to trade waifu!*\nUsage: `/trade <YourWaifuID> <TheirWaifuID>`",
            parse_mode="Markdown"
        )
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "⚠️ *Provide exactly two waifu IDs!*\nUsage: `/trade <YourWaifuID> <TheirWaifuID>`",
            parse_mode="Markdown"
        )
        return

    sending_id = context.args[0].zfill(3)
    receiving_id = context.args[1].zfill(3)

    sender = update.effective_user
    sender_id = sender.id
    sender_name = sender.full_name

    receiver = update.message.reply_to_message.from_user
    receiver_id = receiver.id
    receiver_name = receiver.full_name

    characters = load_characters()
    char1 = characters.get(sending_id)
    char2 = characters.get(receiving_id)

    if not char1 or not char2:
        await update.message.reply_text("❌ One or both waifu IDs are invalid.")
        return

    if not user_has_character(sender_id, sending_id):
        await update.message.reply_text(f"❌ You don’t own waifu `{sending_id}`.")
        return

    if not user_has_character(receiver_id, receiving_id):
        await update.message.reply_text(f"❌ {receiver_name} doesn’t own waifu `{receiving_id}`.")
        return

    send_name = char1["name"].title()
    send_rarity = char1["rarity"]
    send_symbol = RARITY_CONFIG.get(send_rarity, {}).get("symbol", "⭐")

    recv_name = char2["name"].title()
    recv_rarity = char2["rarity"]
    recv_symbol = RARITY_CONFIG.get(recv_rarity, {}).get("symbol", "⭐")

    context.chat_data["waifu_trade"] = {
        "sender_id": sender_id,
        "sender_name": sender_name,
        "sending_id": sending_id,

        "receiver_id": receiver_id,
        "receiver_name": receiver_name,
        "receiving_id": receiving_id
    }

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept", callback_data="trade_ACCEPT"),
            InlineKeyboardButton("❌ Reject", callback_data="trade_REJECT")
        ]
    ])

    await update.message.reply_text(
        f"📦 *Trade Request:*\n\n"
        f"*{sender_name}* wants to trade their waifu:\n"
        f"• `{sending_id}` → {send_symbol} *{send_name}*\n\n"
        f"in exchange for *{receiver_name}*'s waifu:\n"
        f"• `{receiving_id}` → {recv_symbol} *{recv_name}*\n\n"
        f"{receiver_name}, do you accept this trade?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def handle_trade_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    trade = context.chat_data.get("waifu_trade")

    if not trade:
        await query.edit_message_text("❌ Trade expired or not found.")
        return

    user_id = query.from_user.id

    if user_id != trade["receiver_id"]:
        await query.answer("Only the receiver can respond to this trade.", show_alert=True)
        return

    if query.data == "trade_ACCEPT":

        sender_id = trade["sender_id"]
        receiver_id = trade["receiver_id"]
        sending_id = trade["sending_id"]
        receiving_id = trade["receiving_id"]

        transfer_character(sender_id, receiver_id, sending_id)
        transfer_character(receiver_id, sender_id, receiving_id)

        characters = load_characters()
        name1 = characters[sending_id]["name"].title()
        name2 = characters[receiving_id]["name"].title()

        await query.edit_message_text(
            f"✅ *Trade Completed!*\n\n"
            f"*{trade['sender_name']}* gave `{sending_id}` → *{name1}*\n"
            f"*{trade['receiver_name']}* gave `{receiving_id}` → *{name2}*",
            parse_mode="Markdown"
        )

    else:
        await query.edit_message_text("❌ Trade rejected.")



MASTER_CHARACTERS = {
    "Aloy", "Amber", "Arlecchino", "Kamisato Ayaka", "Barbara", "Beiduo",
    "Candace", "Charlotte", "Chasca", "Chevreuse", "Chiori", "Citlali", "Clorinde",
    "Collei", "Dehya", "Diona", "Dori", "Emilie", "Escoffier", "Eula Lawrence", "Faruzan",
    "Fischl", "Furina", "Ganyu", "Hu Tao", "Iansan", "Jean", "Kachina", "Keqing",
    "Kirara", "Klee", "Kujou Sara", "Kuki Shinobu",
    "Lan Yan", "Layla", "Lisa", "Lynette", "Mavuika", "Yumemizuki Mizuki", "Mona", "Mualani",
    "Nahida", "Navia", "Nilou", "Ningguang", "Noelle", "Qiqi", "Raiden Shogun",
    "Rosaria", "Sayu", "Shenhe","Sangonomiya Kokomi", "Sigewinne", "Skirk", "Sucrose", "Varesa",
    "Xiangling", "Xianyun", "Xinyan", "Yanfei", "Yaoyao","Xilonen","Lumine", "Yae Miko", "Yelan",
    "Yoimiya", "Yun Jin", "Ineffa"
}


def normalize(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', name.lower())


async def check_command(update, context):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🚫 You are not authorized to use this tool.")
        return
    keyboard = []
    row = []
    for idx, (rarity, config) in enumerate(RARITY_CONFIG.items(), start=1):
        display = config.get("display", str(rarity))
        row.append(InlineKeyboardButton(display, callback_data=f"check_rarity_{rarity}"))
        if idx % 3 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("📜 Show All", callback_data="check_rarity_ALL")])
    await update.message.reply_text(
        "🔎 *CHARACTER CHECK TOOL*\nChoose a rarity to verify characters:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def check_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("🚫 You are not authorized to use this tool.")
        return

    selected_rarity = query.data.split("check_rarity_")[1]

    try:
        characters = load_characters()
    except Exception:
        await query.edit_message_text("❌ Failed to load character list.")
        return

    db_chars = []
    for c in characters.values():
        if selected_rarity == "ALL" or str(c.get("rarity")) == selected_rarity:
            db_chars.append(c["name"])

    master_norm_map = {normalize(name): name for name in MASTER_CHARACTERS}
    db_norm_map = {normalize(name): name for name in db_chars}

    master_keys = set(master_norm_map.keys())
    db_keys = set(db_norm_map.keys())

    present_keys = master_keys & db_keys
    missing_keys = master_keys - db_keys
    extra_keys = db_keys - master_keys

    present = sorted(master_norm_map[k] for k in present_keys)
    missing = sorted(master_norm_map[k] for k in missing_keys)
    extra = sorted(db_norm_map[k] for k in extra_keys)

    msg = f"📊 *Character Verification ({selected_rarity})*\n\n"
    msg += f"✅ Present Waifus: {len(present)}\n" + (", ".join(present) if present else "—") + "\n\n"
    msg += f"⚠️ Missing Waifus: {len(missing)}\n" + (", ".join(missing) if missing else "—") + "\n\n"
    msg += f"❌ Extra Waifus: {len(extra)}\n" + (", ".join(extra) if extra else "—") + "\n"

    if len(msg) > 4000:
        parts = [msg[i:i + 4000] for i in range(0, len(msg), 4000)]
        for part in parts:
            await query.message.reply_text(part, parse_mode=ParseMode.MARKDOWN)
        await query.delete_message()
    else:
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
    if len(msg) > 4000:
        parts = [msg[i:i + 4000] for i in range(0, len(msg), 4000)]
        for part in parts:
            await query.message.reply_text(part, parse_mode=ParseMode.MARKDOWN)
        await query.delete_message()
    else:
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)

LEADERBOARD_BANNER = "https://i.ibb.co/LDjdXBYJ/Img2url-bot.jpg" 
async def wtop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = get_top_waifu_holders()

    if not rows:
        await update.message.reply_text("No waifu data available.")
        return

    lines = ["🏆 <b>Top Waifu Collectors</b> 🏆\n"]

    for i, (user_id, total) in enumerate(rows, start=1):
        username = get_user_display_name(user_id) or "User"
        safe_name = html.escape(username)

        mention = f"<a href='tg://user?id={user_id}'>{safe_name}</a>"

        lines.append(f"{i}. {mention} — <b>{total}</b> waifus")

    text = "\n".join(lines)

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=LEADERBOARD_BANNER,
        caption=text,
        parse_mode="HTML"
    )



def register_harem_handlers(application):

    application.add_handler(CommandHandler("wish", wish_command), group=0)
    application.add_handler(CommandHandler("harem", harem_command), group=0)
    application.add_handler(CommandHandler("fav", fav_command), group=0)
    application.add_handler(CommandHandler("gift", gift_command), group=0)
    application.add_handler(CommandHandler("force", force_drop_command), group=0)
    application.add_handler(CommandHandler("hall", hall_command), group=0)
    application.add_handler(CommandHandler("interval", set_drop_interval), group=0)
    application.add_handler(CommandHandler("hmsgcount", hmsg_count), group=0)
    application.add_handler(CommandHandler("addchar", add_char_command, filters.ChatType.PRIVATE), group=0)
    application.add_handler(CommandHandler("cancelchar", cancel_add_char, filters.ChatType.PRIVATE), group=0)
    application.add_handler(CommandHandler("delete", delete_character), group=0)
    application.add_handler(CommandHandler("open", open_char), group=0)
    application.add_handler(CommandHandler("backupch", backup_characters), group=0)
    application.add_handler(CommandHandler("restorechars", restore_characters), group=0)
    application.add_handler(CommandHandler("rarity", rarity_command), group=0)
    application.add_handler(CommandHandler("addwaifu", add_waifu), group=0)
    application.add_handler(CommandHandler("rwaifu", remove_waifu))
    application.add_handler(CommandHandler("trade", trade))
    application.add_handler(CommandHandler("unblock", unlock_command))
    application.add_handler(CommandHandler("check", check_command),group=0)
    application.add_handler(CommandHandler("wtop", wtop_cmd))
    application.add_handler(CallbackQueryHandler(check_callback, pattern="^check_rarity_"),group=0)

    application.add_handler(CallbackQueryHandler(handle_trade_response, pattern="^trade_"))
    application.add_handler(CallbackQueryHandler(handle_char_confirmation, pattern="^(confirm_char|cancel_char)$"), group=0)
    application.add_handler(CallbackQueryHandler(harem_callback, pattern="^harem_"), group=0)
    application.add_handler(CallbackQueryHandler(fav_callback, pattern="^fav_"), group=0)
    application.add_handler(CallbackQueryHandler(delete_character_callback, pattern="^(confirm_delete|cancel_delete)$"), group=0)
    application.add_handler(CallbackQueryHandler(hall_callback, pattern=r"^hall_rarity_"), group=0)
    application.add_handler(CallbackQueryHandler(rarity_callback, pattern="^rarity_"), group=0)

    application.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE & filters.User(5192424390), handle_uploaded_json_file), group=0)
    application.add_handler(MessageHandler(filters.Document.ZIP & filters.ChatType.PRIVATE & filters.User(5192424390), handle_uploaded_image_zip), group=0)
    application.add_handler(InlineQueryHandler(inline_harem_gallery_handler, pattern=r"^harem:"))
    application.add_handler(InlineQueryHandler(inline_all_waifus_handler)) 
    application.add_handler(CallbackQueryHandler(who_collected_callback, pattern=r"^who_"))

    application.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_add_char_image), group=1)
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_dynamic_char_commands), group=1)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message), group=2)
    #application.add_error_handler(error_handler)