from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove, ForceReply
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, CallbackContext, ConversationHandler
from quiz import register_quiz_handlers
from gacha import register_gacha_handlers,ensure_gacha_columns
from harem import register_harem_handlers,init_harem_database,create_user_preferences_table#create_sample_characters
from mine import register_game_handlers
import os
import sqlite3
from datetime import time,timedelta,timezone
import pytz
from telegram.ext import Application
from datetime import datetime, timezone, timedelta
from shop import register_shop_handlers
import json
from pvp import apply_daily_interest, register_monster_handlers,reset_defeats_today,auto_unlock_modes
ADMIN_IDS = [5192424390,5716946356]
# ======= CONFIG =======
#TOKEN = "7592457873:AAEFFNDOVQWcRZ6bJQCisjSNkoGauHRXUAE"
TOKEN = "7952386138:AAHUwRqnHcRvHVholUSy7hPzyAicdZQ8Isg"
TEXT_FOLDER = "texts"
IMAGE_FOLDER = "images"
BANNER_FOLDER = os.path.join(IMAGE_FOLDER, "banners")
GUIDES_FOLDER = os.path.join(IMAGE_FOLDER, "guides")
THEATRE_FOLDER = os.path.join(IMAGE_FOLDER, "theatre")
# ======= INIT FOLDERS =======
os.makedirs(TEXT_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(BANNER_FOLDER, exist_ok=True)

os.makedirs(GUIDES_FOLDER, exist_ok=True)
os.makedirs(THEATRE_FOLDER, exist_ok=True)
KNOWN_COMMANDS = {
    "start", "quiz", "setintervals", "mines", "stopmine", "primogems", "dice",
    "addprimos", "send", "tran", "wish", "multiwish", "characters", "pity",
    "database", "data", "list", "party", "monster", "call", "msgcount",
    "monsterboard", "paimonbox", "resetpaimon", "backupdb", "restoredb", "tic",
    "tc", "cancel", "rps", "guide", "add", "banners", "theatre", "stic",

    # Harem & Gift System
    "harem", "gift", "fav", "force", "hall", "interval", "hmsgcount",

    # Character Management
    "addchar", "cancelchar", "restorechars", "backupch", "backupimages", "restoreimages"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name

    keyboard = [
        [InlineKeyboardButton("🌐 GENSHIN GROUP ✨", url="https://t.me/+ZkAWjJCIHMg0ODFl")],
        [InlineKeyboardButton("📩 CONTACT BAKA 👀", url="https://t.me/Anush_X_02")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    # Real, clean Genshin image
    image_url = "https://ibb.co/m5L39pPt"

    await update.message.reply_photo(
        photo=image_url,
        caption=(
            f"👋 Hey there {name}!\n\n"
            f"I’m *BAKA Bot*, a Genshin-themed bot developed by the admins.\n"
            f"Gamble, collect, and vibe with us 🎲✨\n\n"
            f"Need help? Use /help(wip) or join our Genshin group below!"
        ),
        reply_markup=markup,
        parse_mode="Markdown"
    )

import os
import json
from datetime import datetime, timezone, timedelta
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, ReplyKeyboardRemove,
    InputMediaPhoto, Update
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ConversationHandler,
    MessageHandler, filters, ContextTypes
)
import cloudinary
import cloudinary.uploader

# Cloudinary config
cloudinary.config(
    cloud_name='dvpz1tzam',
    api_key='895687319552522',
    api_secret='RHMZdboQRoneTPZv8SyaSg0ITfg'
)

BAKA_JSON_PATH = "baka.json"
ADMIN_USER_IDS = {5192424390}  # Set your admin IDs

DEFAULT_THEATRE_IMAGE_URL = "https://i.ibb.co/LDjdXBYJ/Img2url-bot.jpg"
DEFAULT_THEATRE_CAPTION = "🎭 Theatre Entries"
DEFAULT_GUIDE_IMAGE_URL = "https://i.ibb.co/LDjdXBYJ/Img2url-bot.jpg"  
DEFAULT_GUIDE_CAPTION = "📘 Guide Entries"


IST = timezone(timedelta(hours=5, minutes=30))
DEADEND = datetime(2025, 8, 19, 15, 30, tzinfo=IST)
# Conversation states (for upload flow if integrated later)
CHOOSE_TYPE, GET_ENTRY_NAME, UPLOAD_IMAGE, IMAGE_CAPTION = range(4)

# --- Helper to load JSON data and ensure dict structure ---
# ======= BANNER =======
def get_banners(data):
    return data.get("banners", [])

def get_nav_buttons(index, total):
    buttons = []
    if index > 0:
        buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data="banner_prev"))
    if index < total - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data="banner_next"))
    return InlineKeyboardMarkup([buttons])



async def show_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    banners = get_banners(data)
    index = context.user_data.get("banner_index", 0)

    if not banners:
        msg = "No banners found."
        if update.message:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.message.edit_text(msg)
        return

    banner = banners[index]
    image_url = banner.get("image_url")
    caption = banner.get("caption", "")

    # Load DEADEND datetime dynamically
    deadend_iso = data.get('deadend_time')
    if deadend_iso:
        DEADEND = datetime.fromisoformat(deadend_iso)
        now = datetime.now(DEADEND.tzinfo)  # use same timezone
        delta = DEADEND - now
    else:
        delta = None

    if delta and delta.total_seconds() > 0:
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        time_left = f"\n\nTime remaining: {days}d {hours}h {minutes}m"
    else:
        time_left = "\n\nBanner ended."

    full_caption = caption + time_left
    reply_markup = get_nav_buttons(index, len(banners))

    if update.callback_query:
        media = InputMediaPhoto(media=image_url, caption=full_caption)
        await update.callback_query.message.edit_media(media=media, reply_markup=reply_markup)
    else:
        await update.message.reply_photo(photo=image_url, caption=full_caption, reply_markup=reply_markup)


async def banners_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["banner_index"] = 0
    await show_banner(update, context)

async def banner_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "banner_next":
        context.user_data["banner_index"] = context.user_data.get("banner_index", 0) + 1
    elif query.data == "banner_prev":
        context.user_data["banner_index"] = context.user_data.get("banner_index", 0) - 1

    await show_banner(update, context)

# ======= GUIDE =======

# Default placeholders
DEFAULT_GUIDE_IMAGE_URL = "https://res.cloudinary.com/dvpz1tzam/image/upload/v1755956697/5179ce59-60a6-4222-831a-ffbf33e60a51_ozavve.png"
DEFAULT_GUIDE_CAPTION = "Select a guide entry below:"
DEFAULT_THEATRE_IMAGE_URL = "https://res.cloudinary.com/dvpz1tzam/image/upload/v1755956698/generated-image_5_pbuseg.png"
DEFAULT_THEATRE_CAPTION = "Select a theatre entry below:"

# ======= GUIDE =======

def get_guide_options_markup(data):
    guide_entries = data.get("guides", {})
    buttons = [
        InlineKeyboardButton(name, callback_data=f"guide_show:{name}")
        for name in sorted(guide_entries.keys())
    ]
    if buttons:
        # 3 buttons per row
        return InlineKeyboardMarkup([buttons[i:i+3] for i in range(0, len(buttons), 3)])
    else:
        return InlineKeyboardMarkup([[InlineKeyboardButton("No guides found", callback_data="none")]])

async def guide_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    markup = get_guide_options_markup(data)
    await update.message.reply_photo(
        photo=DEFAULT_GUIDE_IMAGE_URL,
        caption=DEFAULT_GUIDE_CAPTION,
        reply_markup=markup
    )


async def guide_show_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    entry_name = query.data.split(":", 1)[1]
    data = load_data()
    entry = data.get("guides", {}).get(entry_name)

    if not entry:
        await query.message.edit_text(f"No guide found with name '{entry_name}'.")
        return

    # Filter out invalid images
    images = [img for img in entry.get("images", []) if isinstance(img, dict) and img.get("url")]
    caption = entry.get("caption", "")

    if not images:
        await query.message.edit_text("No valid images found for this guide.")
        return

    context.user_data['guide_view'] = {
        "entry_name": entry_name,
        "images": images,
        "caption": caption,
        "index": 0
    }

    img = images[0]
    url = img.get("url")
    img_caption = img.get("caption", "") or caption

    buttons = []
    if len(images) > 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data="guide_next"))
    buttons.append(InlineKeyboardButton("🔙 Back", callback_data="guide_menu"))

    await query.message.edit_media(
        media=InputMediaPhoto(media=url, caption=img_caption),
        reply_markup=InlineKeyboardMarkup([buttons])
    )

async def guide_nav_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    nav_data = context.user_data.get('guide_view')
    if not nav_data:
        await query.message.edit_text("Navigation data missing. Use /guide to start again.")
        return

    images = nav_data['images']
    caption = nav_data['caption']
    index = nav_data['index']

    if query.data == "guide_next":
        index = min(index + 1, len(images) - 1)
    elif query.data == "guide_prev":
        index = max(index - 1, 0)
    elif query.data == "guide_menu":
        buttons = [
            InlineKeyboardButton(name, callback_data=f"guide_show:{name}")
            for name in sorted(load_data().get("guides", {}).keys())
        ]
        button_rows = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
        reply_markup = InlineKeyboardMarkup(button_rows)

        await query.message.edit_media(
            media=InputMediaPhoto(media=DEFAULT_GUIDE_IMAGE_URL, caption=DEFAULT_GUIDE_CAPTION),
            reply_markup=reply_markup
        )
        context.user_data.pop("guide_view", None)
        return

    nav_data['index'] = index
    img = images[index]
    url = img.get("url")
    img_caption = img.get("caption", "") if img.get("caption") else (caption if index == 0 else "")

    buttons = []
    if index > 0:
        buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data="guide_prev"))
    if index < len(images) - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data="guide_next"))
    buttons.append(InlineKeyboardButton("🔙 Back", callback_data="guide_menu"))

    await query.message.edit_media(
        media=InputMediaPhoto(media=url, caption=img_caption),
        reply_markup=InlineKeyboardMarkup([buttons])
    )


# ======= THEATRE =======

def get_theatre_options_markup(data):
    theatre_entries = data.get("theatre", {})
    buttons = [
        InlineKeyboardButton(name, callback_data=f"theatre_show:{name}")
        for name in sorted(theatre_entries.keys())
    ]
    if buttons:
        return InlineKeyboardMarkup([buttons[i:i+4] for i in range(0, len(buttons), 4)])
    else:
        return InlineKeyboardMarkup([[InlineKeyboardButton("No theatre found", callback_data="none")]])

async def theatre_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    markup = get_theatre_options_markup(data)
    await update.message.reply_photo(
        photo=DEFAULT_THEATRE_IMAGE_URL,
        caption=DEFAULT_THEATRE_CAPTION,
        reply_markup=markup
    )

async def theatre_show_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    entry_name = query.data.split(":", 1)[1]
    data = load_data()
    entry = data.get("theatre", {}).get(entry_name)

    if not entry:
        await query.message.edit_text(f"No theatre found with name '{entry_name}'.")
        return

    # Filter invalid images
    images = [img for img in entry.get("images", []) if isinstance(img, dict) and img.get("url")]
    if not images:
        await query.message.edit_text("No valid images found for this theatre.")
        return

    context.user_data['theatre_view'] = {
        "entry_name": entry_name,
        "images": images,
        "index": 0
    }

    img = images[0]
    url = img.get("url")
    caption = img.get("caption", "")

    buttons = []
    if len(images) > 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data="theatre_next"))
    buttons.append(InlineKeyboardButton("🔙 Back", callback_data="theatre_menu"))

    await query.message.edit_media(
        media=InputMediaPhoto(media=url, caption=caption),
        reply_markup=InlineKeyboardMarkup([buttons])
    )

async def theatre_nav_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    nav_data = context.user_data.get('theatre_view')
    if not nav_data or query.data == "theatre_menu":
        # Back to menu
        data = load_data()
        theatre_entries = data.get("theatre", {})
        buttons = [
            InlineKeyboardButton(name, callback_data=f"theatre_show:{name}")
            for name in sorted(theatre_entries.keys())
        ]
        button_rows = [buttons[i:i+4] for i in range(0, len(buttons), 4)]
        await query.message.edit_media(
            media=InputMediaPhoto(media=DEFAULT_THEATRE_IMAGE_URL, caption=DEFAULT_THEATRE_CAPTION),
            reply_markup=InlineKeyboardMarkup(button_rows)
        )
        context.user_data.pop("theatre_view", None)
        return

    images = nav_data['images']
    index = nav_data['index']

    if query.data == "theatre_next":
        index = min(index + 1, len(images) - 1)
    elif query.data == "theatre_prev":
        index = max(index - 1, 0)

    nav_data['index'] = index
    img = images[index]
    url = img.get("url")
    caption = img.get("caption", "")

    buttons = []
    if index > 0:
        buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data="theatre_prev"))
    if index < len(images) - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data="theatre_next"))
    buttons.append(InlineKeyboardButton("🔙 Back", callback_data="theatre_menu"))

    await query.message.edit_media(
        media=InputMediaPhoto(media=url, caption=caption),
        reply_markup=InlineKeyboardMarkup([buttons])
    )



# --- Theatre Related ---



# Import statements assumed present...

# Conversation states
USE_MOUNT = os.path.exists("/mnt/data")
BAKA_JSON_PATH = "/mnt/data/baka.json"
CHOOSE_TYPE, GET_ENTRY_NAME, UPLOAD_IMAGE, IMAGE_CAPTION = range(4)
CHAR_GET_NAME, CHAR_UPLOAD_IMAGE = range(10, 12)

# --- JSON helpers ---
def load_data():
    if not os.path.exists(BAKA_JSON_PATH):
        return {"banners": [], "guides": {}, "theatre": {}, "characters": {}}
    with open(BAKA_JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Normalize guide images: convert any string URLs to objects with empty caption
    guides = data.get("guides", {})
    for guide_name, guide_data in guides.items():
        images = guide_data.get("images", [])
        norm_images = []
        for img in images:
            if isinstance(img, str):
                norm_images.append({"url": img, "caption": ""})
            else:
                norm_images.append(img)
        guides[guide_name]["images"] = norm_images
    data["guides"] = guides

    # Normalize theatre images similarly
    theatre = data.get("theatre", {})
    for theatre_name, theatre_data in theatre.items():
        images = theatre_data.get("images", [])
        norm_images = []
        for img in images:
            if isinstance(img, str):
                norm_images.append({"url": img, "caption": ""})
            else:
                norm_images.append(img)
        theatre[theatre_name]["images"] = norm_images
    data["theatre"] = theatre

    # Normalize character keys to lowercase for consistency
    characters = data.get("characters", {})
    normalized_characters = {}
    for k, v in characters.items():
        normalized_characters[k.strip().lower()] = v
    data["characters"] = normalized_characters

    return data

def save_data(data):
    with open(BAKA_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# --- Handlers ---

async def start_cloud(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("You are not authorized.")
        return ConversationHandler.END

    # Only allow in private chat (DM)
    if update.effective_chat.type != "private":
        await update.message.reply_text("This command can only be used in private chat (DM).")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("Banner", callback_data="type_banner"),
         InlineKeyboardButton("Guide", callback_data="type_guide")],
        [InlineKeyboardButton("Theatre", callback_data="type_theatre"),
         InlineKeyboardButton("Character", callback_data="type_character")]
    ]
    await update.message.reply_text("Select type to upload:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_TYPE


async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctype = query.data.split('_')[1]

    context.user_data['upload'] = {
        "type": ctype,
        "images": [],
        "caption": None,
        "entry_name": None,
        "edit_index": None
    }

    if ctype == 'banner':
        data = load_data()
        banners = data.get("banners", [])
        if len(banners) >= 3:
            # Ask the user which banner to replace next
            await query.edit_message_text(
                "Maximum 3 banners reached. Send the number (1, 2, or 3) of the banner to replace."
            )
            return GET_ENTRY_NAME  # Re-use this for number input
        else:
            context.user_data['upload']['edit_index'] = None
            await query.edit_message_text("Selected Banner. Send the banner image.")
            return UPLOAD_IMAGE

    elif ctype in ['guide', 'theatre']:
        await query.edit_message_text("Please send the name/title for this entry.")
        return GET_ENTRY_NAME

    else:  # character
        await query.edit_message_text("Please send the character name.")
        return CHAR_GET_NAME


async def get_entry_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    ut = context.user_data['upload']['type']

    if ut == 'banner':
        if text in ['1', '2', '3']:
            context.user_data['upload']['edit_index'] = int(text) - 1
            await update.message.reply_text(f"Replacing banner #{text}. Please send the new banner image.")
            return UPLOAD_IMAGE
        else:
            await update.message.reply_text("Invalid input. Please send 1, 2, or 3 to choose which banner to replace.")
            return GET_ENTRY_NAME

    else:
        context.user_data['upload']['entry_name'] = text
        await update.message.reply_text(f"Entry name set to '{text}'. Send the first image.")
        return UPLOAD_IMAGE


async def save_current_upload(context: ContextTypes.DEFAULT_TYPE):
    if 'upload' not in context.user_data:
        return

    ut = context.user_data['upload']['type']
    images = context.user_data['upload'].get('images', [])
    entry_name = context.user_data['upload'].get('entry_name')
    edit_index = context.user_data['upload'].get('edit_index')
    data = load_data()

    if ut == 'banner':
        if images:
            banners = data.setdefault('banners', [])

            new_banner = {
                "image_url": images[-1]['url'],
                "caption": images[-1].get('caption') or ""
            }

            # Ensure banners list has exactly 3 entries (fill with empty if needed)
            while len(banners) < 3:
                banners.append({"image_url": "", "caption": ""})

            if edit_index is not None and 0 <= edit_index < 3:
                banners[edit_index] = new_banner
            else:
                if len(banners) < 3:
                    banners.append(new_banner)

            data['banners'] = banners[:3]

            context.user_data['upload']['images'] = []
            context.user_data['upload']['caption'] = None
            context.user_data['upload']['edit_index'] = None

    # existing guide, theatre, character handling unchanged ...
    elif ut == 'guide':
        if entry_name:
            collection = data.setdefault('guides', {})
            existing = collection.get(entry_name, {"caption": "", "images": []})
            existing_images = existing.get('images', [])
            norm_existing_images = []
            for img in existing_images:
                if isinstance(img, str):
                    norm_existing_images.append({"url": img, "caption": ""})
                else:
                    norm_existing_images.append(img)

            new_images = images
            combined_images = norm_existing_images + new_images

            entry_caption = context.user_data['upload'].get('caption') or existing.get('caption', '')

            collection[entry_name] = {
                "caption": entry_caption,
                "images": combined_images
            }

            context.user_data['upload']['images'] = []
            context.user_data['upload']['caption'] = None

    elif ut == 'theatre':
        if entry_name:
            collection = data.setdefault('theatre', {})
            existing = collection.get(entry_name, {"images": []})
            existing_images = existing.get('images', [])
            norm_existing_images = []
            for img in existing_images:
                if isinstance(img, str):
                    norm_existing_images.append({"url": img, "caption": ""})
                else:
                    norm_existing_images.append(img)

            new_images = images
            combined_images = norm_existing_images + new_images

            collection[entry_name] = {
                "images": combined_images
            }

            context.user_data['upload']['images'] = []
            context.user_data['upload']['caption'] = None

    elif ut == 'character':
        pass

    save_data(data)


async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'upload' not in context.user_data:
        await update.message.reply_text("Start with /cloud.")
        return ConversationHandler.END
    if not update.message.photo:
        await update.message.reply_text("Please send a photo.")
        return UPLOAD_IMAGE

    photo_file = update.message.photo[-1]
    file = await photo_file.get_file()
    photo_bytes = await file.download_as_bytearray()

    ut = context.user_data['upload']['type']
    folder = f"genshin/main/{ut}"
    if ut == 'character':
        folder = "genshin/main/character"

    result = cloudinary.uploader.upload(photo_bytes, folder=folder)
    url = result.get('secure_url')
    if not url:
        await update.message.reply_text("Upload failed, try again.")
        return UPLOAD_IMAGE

    if ut == 'banner':
        context.user_data['upload']['images'] = [{"url": url, "caption": None}]
    else:
        context.user_data['upload']['images'].append({"url": url, "caption": None})

    keyboard = [
        [InlineKeyboardButton("Yes", callback_data="caption_yes"),
         InlineKeyboardButton("No", callback_data="caption_no")]
    ]
    await update.message.reply_text("Add a caption to this image?", reply_markup=InlineKeyboardMarkup(keyboard))
    return IMAGE_CAPTION

async def image_caption_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ut = context.user_data['upload']['type']

    if query.data == 'caption_yes':
        sent = await query.message.reply_text(
            "Please reply to this message with the caption text.",
            reply_markup=ForceReply(selective=True)
        )
        context.user_data['caption_prompt_message_id'] = sent.message_id
        return IMAGE_CAPTION
    else:
        await save_current_upload(context)
        if ut == 'banner':
            await query.edit_message_text("Caption skipped for banner.\nSend another image or /done to finish.")
        else:
            await query.edit_message_text("Caption skipped.\nSend next image or /done if finished.")
        return UPLOAD_IMAGE

async def receive_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption_prompt_id = context.user_data.get('caption_prompt_message_id')
    reply_to_message = update.message.reply_to_message

    if not reply_to_message or reply_to_message.message_id != caption_prompt_id:
        await update.message.reply_text("Please reply directly to the bot's caption prompt message!")
        return IMAGE_CAPTION

    text = update.message.text.strip()
    if context.user_data['upload']['images']:
        context.user_data['upload']['images'][-1]['caption'] = text

    await save_current_upload(context)

    ut = context.user_data['upload']['type']
    if ut == 'banner':
        await update.message.reply_text("Caption saved. Send another image or /done to finish.")
    else:
        await update.message.reply_text("Caption saved. Send next image or /done to finish.")
    return UPLOAD_IMAGE
async def save_current_upload(context: ContextTypes.DEFAULT_TYPE):
    if 'upload' not in context.user_data:
        return

    ut = context.user_data['upload']['type']
    images = context.user_data['upload'].get('images', [])
    entry_name = context.user_data['upload'].get('entry_name')
    edit_index = context.user_data['upload'].get('edit_index')
    data = load_data()

    if ut == 'banner':
        if images:
            banners = data.setdefault('banners', [])

            new_banner = {
                "image_url": images[-1]['url'],
                "caption": images[-1].get('caption') or ""
            }

            # Ensure banners list has exactly 3 entries (fill with empty if needed)
            while len(banners) < 3:
                banners.append({"image_url": "", "caption": ""})

            if edit_index is not None and 0 <= edit_index < 3:
                banners[edit_index] = new_banner
            else:
                # Append only if under 3 banners
                if len(banners) < 3:
                    banners.append(new_banner)

            # Trim to max 3 banners if somehow more
            data['banners'] = banners[:3]

            context.user_data['upload']['images'] = []
            context.user_data['upload']['caption'] = None
            context.user_data['edit_index'] = None


    elif ut == 'guide':
        if entry_name:
            collection = data.setdefault('guides', {})
            existing = collection.get(entry_name, {"caption": "", "images": []})
            existing_images = existing.get('images', [])
            norm_existing_images = []
            for img in existing_images:
                if isinstance(img, str):
                    norm_existing_images.append({"url": img, "caption": ""})
                else:
                    norm_existing_images.append(img)

            new_images = images
            combined_images = norm_existing_images + new_images

            entry_caption = context.user_data['upload'].get('caption') or existing.get('caption', '')

            collection[entry_name] = {
                "caption": entry_caption,
                "images": combined_images
            }

            context.user_data['upload']['images'] = []
            context.user_data['upload']['caption'] = None

    elif ut == 'theatre':
        if entry_name:
            collection = data.setdefault('theatre', {})
            existing = collection.get(entry_name, {"images": []})
            existing_images = existing.get('images', [])
            norm_existing_images = []
            for img in existing_images:
                if isinstance(img, str):
                    norm_existing_images.append({"url": img, "caption": ""})
                else:
                    norm_existing_images.append(img)

            new_images = images
            combined_images = norm_existing_images + new_images

            collection[entry_name] = {
                "images": combined_images
            }

            context.user_data['upload']['images'] = []
            context.user_data['upload']['caption'] = None

    elif ut == 'character':
        pass

    save_data(data)





async def done_uploading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_current_upload(context)
    await update.message.reply_text("Upload session finished. Use /cloud to start new upload.")
    context.user_data.pop('upload', None)
    context.user_data.pop('edit_index', None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Upload cancelled.", reply_markup=ReplyKeyboardRemove())
    context.user_data.pop('upload', None)
    context.user_data.pop('edit_index', None)
    return ConversationHandler.END

# --- Character upload flow ---

async def char_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data['upload']['entry_name'] = name
    await update.message.reply_text(f"Character name set: {name}\nSend the image for this character.")
    return CHAR_UPLOAD_IMAGE
async def char_upload_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'upload' not in context.user_data:
        await update.message.reply_text("Please start with /cloud.")
        return ConversationHandler.END
    if not update.message.photo:
        await update.message.reply_text("Please send a photo.")
        return CHAR_UPLOAD_IMAGE

    photo_file = update.message.photo[-1]
    file = await photo_file.get_file()
    photo_bytes = await file.download_as_bytearray()

    result = cloudinary.uploader.upload(photo_bytes, folder="genshin/main/character")
    url = result.get('secure_url')
    if not url:
        await update.message.reply_text("Upload failed, try again.")
        return CHAR_UPLOAD_IMAGE

    name = context.user_data['upload'].get('entry_name')
    if not name:
        await update.message.reply_text("Name missing, please restart upload with /cloud.")
        return ConversationHandler.END

    data = load_data()
    characters = data.setdefault("characters", {})
    normalized_name = name.strip().lower()
    characters[normalized_name] = url
    save_data(data)

    context.user_data['upload']['entry_name'] = None
    await update.message.reply_text(f"Character '{name}' saved. Send next character name or /done to finish.")
    return CHAR_GET_NAME


DATABASE = "/mnt/data/quiz.db"

import html  
from telegram.constants import ParseMode

async def database(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ BAKA !!You don't have permission to do that.")
        return

    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT u.user_id, u.primogems, g.pity_4, g.pity_5
            FROM users u
            LEFT JOIN gacha_state g ON u.user_id = g.user_id
        """)
        rows = cursor.fetchall()

        if not rows:
            await update.message.reply_text("📦 No data found in the database.")
            return

        msg = "📊 <b>User Database Snapshot:</b>\n"

        for row in rows:
            uid, primogems, pity_4, pity_5 = row
            try:
                user = await context.bot.get_chat(uid)
                display_name = user.full_name or f"User {uid}"
                username = user.username  
            except:
                display_name = f"User {uid}"
                username = None

            escaped_name = html.escape(display_name)

            if username:  
                mention = f"<a href='https://t.me/{username}'>{username}</a>"  
            else:  # fallback to user id link
                mention = f"<a href='tg://user?id={uid}'>{uid}</a>"

            msg += (
                f"\n👤 {mention}\n"
                f"💎 Primogems: {primogems}\n"
                f"⭐ Pity 4★: {pity_4 if pity_4 is not None else '—'}\n"
                f"✨ Pity 5★: {pity_5 if pity_5 is not None else '—'}\n"
            )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=msg,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )




    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

    finally:
        try:
            conn.close()
        except:
            pass
IMAGE_URL = "https://res.cloudinary.com/dvpz1tzam/image/upload/v1752989365/generated-image_4_djjntd.png"  

async def primosboard(update: Update, context: CallbackContext):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, primogems
            FROM users
        """)
        rows = cursor.fetchall()

        if not rows:
            await update.message.reply_text("📦 No data found in the database.")
            return

        # Sort users by primogems descending, pick top 10
        rows.sort(key=lambda x: x[1], reverse=True)
        top_users = rows[:10]

        msg = "🏆 <b>Primogems Leaderboard</b> 🪙\n\n"

        for idx, (uid, primogems) in enumerate(top_users, 1):
            try:
                user = await context.bot.get_chat(uid)
                display_name = user.full_name or f"User {uid}"
                username = user.username
            except Exception:
                display_name = f"User {uid}"
                username = None

            escaped_name = html.escape(display_name)
            if username:
                mention = f"<a href='https://t.me/{username}'>{escaped_name}</a>"
            else:
                mention = f"<a href='tg://user?id={uid}'>{escaped_name}</a>"

            msg += f"{idx} {mention} — <b>{primogems}</b>💎\n"

        # Send image with caption (replace IMAGE_URL with your link)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=IMAGE_URL,
            caption=msg,
            parse_mode=ParseMode.HTML,
            
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    finally:
        try:
            conn.close()
        except:
            pass


async def daily_interest_job_wrapper(context):
    await apply_daily_interest(context.application)

async def auto_unlock_modes_job_wrapper(context):
    await auto_unlock_modes(context.application)

async def reset_defeats_job_wrapper(context: ContextTypes.DEFAULT_TYPE):
    await reset_defeats_today(context.application)

def setup_daily_jobs(application):
    job_queue = application.job_queue
    ist = pytz.timezone("Asia/Kolkata")

    # Daily interest 00:00 IST
    job_queue.run_daily(
        daily_interest_job_wrapper,
        time=time(hour=0, minute=0, tzinfo=ist),
        name="daily_interest_job"
    )

    # Reset defeats_today 00:01 IST
    job_queue.run_daily(
        reset_defeats_job_wrapper,
        time=time(hour=0, minute=1, tzinfo=ist),
        name="reset_defeats_job"
    )

    job_queue.run_repeating(
        auto_unlock_modes_job_wrapper,
        interval=60, 
        first=0,
        name="auto_unlock_modes_job"
    )

    print("✅ Daily interest job scheduled for 00:00 IST")
    print("✅ Reset defeats_today job scheduled for 00:01 IST")
    print("✅ Auto unlock mode job scheduled every 1 minute")

async def jobtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test the daily jobs by running them after 1 minute"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ This command is admin-only.")
        return
    
    from datetime import datetime, timedelta
    import pytz
    
    job_queue = context.application.job_queue
    ist = pytz.timezone("Asia/Kolkata")
    
    # Calculate 1 minute from now
    now = datetime.now(ist)
    test_time = now + timedelta(minutes=1)
    
    # Remove existing test jobs if any
    current_jobs = job_queue.get_jobs_by_name("test_daily_interest")
    for job in current_jobs:
        job.schedule_removal()
    
    current_jobs = job_queue.get_jobs_by_name("test_reset_defeats")
    for job in current_jobs:
        job.schedule_removal()
    

    job_queue.run_once(
        daily_interest_job_wrapper,
        when=test_time,
        name="test_daily_interest"
    )
    
    job_queue.run_once(
        reset_defeats_job_wrapper,
        when=test_time + timedelta(seconds=5), 
        name="test_reset_defeats"
    )
    

    await update.message.reply_text(
        f"🧪 **Job Test Scheduled**\n\n"
        f"⏰ Current time: {now.strftime('%H:%M:%S')} IST\n"
        f"🚀 Jobs will run at: {test_time.strftime('%H:%M:%S')} IST\n\n"
        f"📋 **Schedule:**\n"
        f"• Daily Interest: {test_time.strftime('%H:%M:%S')}\n"
        f"• Reset Defeats: {(test_time + timedelta(seconds=5)).strftime('%H:%M:%S')}\n\n"
        f"✅ Wait 1 minute for execution..."
    )

async def changetime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check authorization
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("You are not authorized.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Please provide date and time as: YYYY-MM-DD HH:MM\nExample: /changetime 2025-08-19 15:30")
        return

    datetime_str = " ".join(args[:2])
    try:
        # Accept input as YYYY-DD-MM (per your example) and parse accordingly
        # So split date to parts and reorder to proper datetime
        date_part = args[0]  # e.g. "2025-19-1"
        year, day, month = map(int, date_part.split('-'))
        hour, minute = map(int, args[1].split(':'))
        new_deadend = datetime(year, month, day, hour, minute, tzinfo=IST)
    except Exception:
        await update.message.reply_text("Invalid format. Use: /changetime YYYY-DD-MM HH:MM\nExample: /changetime 2025-19-01 15:30")
        return

    data = load_data()
    data['deadend_time'] = new_deadend.isoformat()
    save_data(data)


def get_remaining_time_str():
    data = load_data()
    deadend_iso = data.get('deadend_time')
    if not deadend_iso:
        return "Deadend time not set."

    deadend_dt = datetime.fromisoformat(deadend_iso)
    now = datetime.now(deadend_dt.tzinfo)

    if deadend_dt <= now:
        return "Deadend time has passed."

    delta = deadend_dt - now
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    return f"Time remaining: {days} days, {hours} hours, {minutes} minutes."
async def send_character_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.strip().lower().lstrip('/')

    data = load_data()
    characters = data.get("characters", {})
    char_texts = {

    }

    alias_map = {}
    for full_name in set(characters.keys()) | set(char_texts.keys()):
        normalized_full_name = full_name.lower()
        parts = normalized_full_name.split()
        # Add full name itself
        alias_map[normalized_full_name] = full_name

        for part in parts:
            for i in range(3, len(part) + 1):
                alias = part[:i]
                if alias not in alias_map:
                    alias_map[alias] = full_name

    canonical_name = alias_map.get(command)

    if canonical_name is None:
        candidates = [name for alias, name in alias_map.items() if alias.startswith(command)]
        candidates = list(set(candidates))  # remove duplicates

        if len(candidates) == 1:
            canonical_name = candidates[0]
        elif len(candidates) > 1:
            candidates_sorted = sorted(candidates)
            await update.message.reply_text(
                f"Multiple characters match your command: {', '.join([c.title() for c in candidates_sorted])}. "
                "Please use a more specific command."
            )
            return
        else:
            return

    url = characters.get(canonical_name.lower())
    text = char_texts.get(canonical_name.lower(), "")

    if url:
        await update.message.reply_photo(photo=url, caption=f"{canonical_name.title()}\n\n{text}")
    else:
        await update.message.reply_text(f"{canonical_name.title()}\n\n{text}")


import os

async def cloudbackup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check admin authorization if needed
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("You are not authorized to perform this action.")
        return

    # Path to your baka.json file
    baka_json_path = BAKA_JSON_PATH  # ensure this is the correct path

    if not os.path.exists(baka_json_path):
        await update.message.reply_text("Backup file not found.")
        return

    # Send the file as document to the user
    await update.message.reply_document(document=open(baka_json_path, "rb"), filename="baka.json")
import tempfile
import errno
import shutil
async def restore_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin gate
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("You are not authorized to perform this action.")
        return

    # Must be a reply with a document named baka.json (or at least a document)
    msg = update.message
    if not msg or not msg.reply_to_message or not msg.reply_to_message.document:
        await msg.reply_text("Reply to a baka.json file with /restorebaka.")
        return

    doc = msg.reply_to_message.document

    # Optional: enforce exact filename check
    if (doc.file_name or "").lower() != "baka.json":
        await msg.reply_text("The replied document must be named baka.json.")
        return

    # Ensure parent dir exists
    os.makedirs(os.path.dirname(BAKA_JSON_PATH), exist_ok=True)

    # Download to a temp file in the same directory for safest atomic replace
    tmp_dir = os.path.dirname(BAKA_JSON_PATH) or "."
    fd, tmp_path = tempfile.mkstemp(prefix="baka_restore_", suffix=".json", dir=tmp_dir)
    os.close(fd)  # will reopen via PTB downloader

    try:
        # Get file and download
        tg_file = await doc.get_file()  # PTB async API
        await tg_file.download_to_drive(tmp_path)  # save to temp path [web:4][web:1]

        # Basic validation: ensure downloaded JSON is non-empty
        if os.path.getsize(tmp_path) == 0:
            raise ValueError("Downloaded file is empty.")

        # Atomic replace of the target file
        # On modern Python, os.replace is atomic and overwrites destination if exists [web:16][web:10]
        os.replace(tmp_path, BAKA_JSON_PATH)
        await msg.reply_text("Restore successful. baka.json has been replaced.")
    except OSError as e:
        # Cross-device moves are handled by os.replace on modern Python, but catch errors anyway [web:16][web:10]
        # Fallback strategy if ever needed:
        if getattr(e, "errno", None) == errno.EXDEV:
            # Cross-device edge-case fallback: copy then atomic rename [web:7]
            copy_tmp = tmp_path + ".copy"
            shutil.copyfile(tmp_path, copy_tmp)
            os.replace(copy_tmp, BAKA_JSON_PATH)
            await msg.reply_text("Restore successful (cross-device).")
        else:
            await msg.reply_text(f"Restore failed: {e!s}")
        # Clean up temp if still exists
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
    except Exception as e:
        await msg.reply_text(f"Restore failed: {e!s}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
def load_data():
    with open(BAKA_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(BAKA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# /edit command
async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("You are not authorized to perform this action.")
        return
    data = load_data()
    keyboard = [[InlineKeyboardButton(k, callback_data=f"edit|{k}")] for k in data.keys()]
    await update.message.reply_text("Choose a section:", reply_markup=InlineKeyboardMarkup(keyboard))

# Callback handler
async def edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
      # Only allow original user
    original_user_id = int(query.data.split("|")[0])  # store ID in callback_data
    if query.from_user.id != original_user_id:
        await query.answer("You cannot use this.", show_alert=True)
        return
    path = query.data.split("|")[1:]  # ignore "edit"
    data = load_data()

    # Walk into JSON by path
    node = data
    for key in path:
        if key.isdigit():  # handle lists
            node = node[int(key)]
        else:
            node = node[key]

    # If node is dict/list → show choices
    if isinstance(node, dict):
        keyboard = [[InlineKeyboardButton(k, callback_data=f"edit|{'|'.join(path+[k])}")] for k in node.keys()]
    elif isinstance(node, list):
        keyboard = [[InlineKeyboardButton(str(i), callback_data=f"edit|{'|'.join(path+[str(i)])}")] for i in range(len(node))]
    else:
        # Leaf → show Delete/Back
        parent_path = "|".join(path[:-1])
        keyboard = [
            [InlineKeyboardButton("Delete", callback_data=f"delete|{'|'.join(path)}")],
            [InlineKeyboardButton("Back", callback_data=f"edit|{parent_path}")]
        ]

    await query.edit_message_text(f"Path: {'/'.join(path)}", reply_markup=InlineKeyboardMarkup(keyboard))

# Delete handler
async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    path = query.data.split("|")[1:]
    data = load_data()
    node = data
    for key in path[:-1]:
        node = node[int(key)] if key.isdigit() else node[key]
    
    last_key = path[-1]
    if last_key.isdigit():
        node.pop(int(last_key))
    else:
        node.pop(last_key)

    save_data(data)
    await query.edit_message_text("Deleted successfully ✅")
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
OWNER_ID  = 5192424390
WEBAPP_URL = "https://web-apps-production.up.railway.app/"

async def webtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton(text="Open Mini App", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        "Tap to open the Mini App, then press Send to Bot.",
        reply_markup=ReplyKeyboardMarkup(kb),
    )

async def webapp_receiver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.effective_message.web_app_data.data
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {"raw": raw}

    u = update.effective_user
    clicker = {
        "id": u.id,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "username": u.username,
    }
    await update.message.reply_text("Received. Forwarding to owner…", reply_markup=ReplyKeyboardRemove())
    text = "Mini App submission:\n" + json.dumps({"clicker": clicker, "payload": payload}, ensure_ascii=False, indent=2)
    await context.bot.send_message(chat_id=OWNER_ID, text=text)

from telegram.ext import CommandHandler

USER_COMMANDS = [
    "/bank","/banner","/characters","/check","/claim","/clash","/daily","/dart","/deposit",
    "/dice","/explore","/fav","/flip","/gift","/guide","/hall","/harem","/hmsgcount",
    "/interest","/inv","/leaderboard","/list","/mines","/mode","/monster","/monsterboard",
    "/msgcount","/multiwish","/open","/paimonbox","/party","/pboard","/pity","/primogems",
    "/quiz","/rarity","/removeid","/rps","/send","/shop","/start","/steal","/stopmine",
    "/tc","/tic","/trade","/tran","/waifu","/wish","/withdraw","/wtop"
]

async def help_command(update, context):
    cmds = "\n".join(sorted(USER_COMMANDS))
    text = (
        "Here are the available commands:\n\n"
        f"{cmds}\n\n"
        "Tip: Use /guide for a quick start and /banner to see current banners."
    )
    await update.message.reply_text(text)

ADMIN_COMMANDS = [
    "/add","/addchar","/addid","/addquestion","/airdrop","/backupch","/backupdb",
    "/backupimages","/bankstats","/cancel","/cancelchar","/changetime","/clashboard",
    "/cloud","/cloudbackup","/convert","/database","/delete","/done","/edit","/force",
    "/hinterval","/interval","/jobtest","/questions","/resetdefeats","/resetmonster",
    "/resetpaimon","/resetrolls","/restorebaka","/restorechars","/restoredb","/restoreimages",
    "/rlock","/rwaifu","/setintervals","/setwaifu","/test","/unblock","/webtest"
]
async def ahelp_command(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Unauthorized.")
        return
    cmds = "\n".join(sorted(ADMIN_COMMANDS))
    text = "Admin commands:\n\n" + cmds + "\n\nNote: Use with care."
    await update.message.reply_text(text)
def setup_application():
    """Setup the application with all handlers"""
    application = Application.builder().token(TOKEN).build()

    # Your existing setup
    init_harem_database()
    create_user_preferences_table()
    register_quiz_handlers(application)
    register_gacha_handlers(application)
    register_harem_handlers(application)
    register_game_handlers(application)
    register_monster_handlers(application)
    register_shop_handlers(application)
    

    ensure_gacha_columns()

    #web apps
    application.add_handler(CommandHandler("webtest", webtest))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_receiver))
    application.add_handler(CommandHandler("ahelp", ahelp_command))
    application.add_handler(CommandHandler("help", help_command))
    # Add all your existing handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cloudbackup", cloudbackup_command))
    application.add_handler(CommandHandler("restorebaka", restore_command))
    application.add_handler(CommandHandler("changetime", changetime_command))
    application.add_handler(CommandHandler("banner", banners_command))
    application.add_handler(CallbackQueryHandler(banner_button_handler, pattern=r"^banner_"))

    application.add_handler(CommandHandler("guide", guide_command))
    application.add_handler(CallbackQueryHandler(guide_show_handler, pattern=r"^guide_show:"))
    application.add_handler(CallbackQueryHandler(guide_nav_handler, pattern=r"^guide_(next|prev|menu)$"))
    
    application.add_handler(CommandHandler("theatreinfo", theatre_command))
    application.add_handler(CallbackQueryHandler(theatre_show_handler, pattern=r"^theatre_show:"))
    application.add_handler(CallbackQueryHandler(theatre_nav_handler, pattern=r"^theatre_(next|prev|menu)$"))
    application.add_handler(CommandHandler("database", database))
    application.add_handler(CommandHandler("pboard", primosboard))
    application.add_handler(MessageHandler(filters.COMMAND, send_character_image), group=100)
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CallbackQueryHandler(edit_callback, pattern=r"^\d+\|edit\|"))

    # application.add_handler(MessageHandler(filters.COMMAND, handle_name), group=100)
    application.add_handler(CommandHandler("jobtest", jobtest))

    
    # Conversation handler with all states in lower priority group (group 3)
    conv_handler = ConversationHandler(
    entry_points=[CommandHandler('cloud', start_cloud)],
    states={
        CHOOSE_TYPE: [CallbackQueryHandler(choose_type, pattern='^type_')],
        GET_ENTRY_NAME: [MessageHandler(filters.TEXT & (~filters.COMMAND), get_entry_name)],
        UPLOAD_IMAGE: [
            MessageHandler(filters.PHOTO & (~filters.COMMAND), receive_image),
            CommandHandler('done', done_uploading),
            CommandHandler('cancel', cancel)
        ],
        IMAGE_CAPTION: [
            CallbackQueryHandler(image_caption_choice, pattern='^caption_'),
            MessageHandler(filters.TEXT & (~filters.COMMAND), receive_caption),
            CommandHandler('cancel', cancel)
        ],
        CHAR_GET_NAME: [MessageHandler(filters.TEXT & (~filters.COMMAND), char_get_name)],
        CHAR_UPLOAD_IMAGE: [
            MessageHandler(filters.PHOTO & (~filters.COMMAND), char_upload_image),
            CommandHandler('done', done_uploading),
            CommandHandler('cancel', cancel),
        ],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)
    application.add_handler(conv_handler, group=3)

    setup_daily_jobs(application)
    
    return application


# ======= START BOT =======
if __name__ == "__main__":
    print("🚀 Starting bot...")
    
    # Setup and run the bot
    application = setup_application()
    print("🤖 Bot is running...")
    print("📅 Daily interest will run automatically at 12:00 AM IST")
    
    # Run the bot
    application.run_polling()
