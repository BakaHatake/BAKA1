from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
)
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import asyncio
import json 
import random
from datetime import datetime, timedelta
from harem import (
    load_characters,
    RARITY_CONFIG,
)

from db import get_balance,update_shop,get_shop,update_balance,refresh_shop,get_harem,record_roll,increment_character,get_primogems,update_primos
from db import get_setwaifu_count,get_user_path,set_user_path,increment_setwaifu_count,clear_user_path,increment_pity,roll_for_path_waifu,update_harem
DEFAULT_BANNER = "https://res.cloudinary.com/dvpz1tzam/image/upload/v1752917631/74ca7946-ebeb-4873-b24e-f00fd1219dce_fqsepm.png"
WIN_BANNER = "https://res.cloudinary.com/dvpz1tzam/image/upload/v1752918095/01d1867d-d611-4dda-8abc-7ea78c49656f_n6rk6a.png"
LOSE_BANNER = "https://res.cloudinary.com/dvpz1tzam/image/upload/v1752918099/generated-image_1_l25yk8.png"


ADMIN_IDS = [5192424390]

import random

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

from datetime import datetime

def generate_random_waifus(num=5):
    characters = load_characters()
    waifu_items = list(characters.items())

    random.shuffle(waifu_items)
    selected = []
    used = set()

    for char_id, char in waifu_items:
        if char_id in used:
            continue
        selected.append({
            "char_id": char_id,
            "name": char.get("name"),
            "rarity": char.get("rarity")
        })
        used.add(char_id)
        if len(selected) >= num:
            break

    return selected
from datetime import datetime


async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    shop_data = get_shop(user_id)
    
    today = datetime.now().strftime("%Y-%m-%d")
    if shop_data is None:
        waifus = generate_random_waifus()
        refreshes = 0
        rolls = 0
        rolled_ids = []
        update_shop(user_id,waifus,today)

    else:
        waifus = shop_data["Waifus"]
        refreshes = shop_data["Refreshes"]
        rolls = shop_data["Rolls"]
        rolled_ids = shop_data["Rolled ids"]

    user_harem = get_harem(user_id)
    print("USER_HAREM:", user_harem, type(user_harem))

    owned_ids = {char_id: count for char_id, count in user_harem.items()}

    lunar = get_balance(user_id, "Lunar Crystals")

    caption = f"📦 **Your Waifu Shop**\n🌙 Lunar Crystals: `{lunar}`\n🎲 Rolls used: `{rolls}/3` | 🔁 Refreshes: `{refreshes}/2`\n\n"

    for w in waifus:
        rarity_info = RARITY_CONFIG[w["rarity"]]
        cost = rarity_info["cost"] * 10
        emoji = rarity_info["symbol"]
        owned = ""
        if w["char_id"] in owned_ids:
            owned = f"✅ x{owned_ids[w['char_id']]}"
        caption += f" `{w['char_id']}` | {w['name']} | {emoji} | 🌙 {cost} | {owned}\n"

    caption += "\n_Tap a waifu ID below to roll!_"

    # 🔐 Lock the shop by attaching user_id to callback_data
    buttons, row = [], []
    for i, w in enumerate(waifus):
        row.append(
            InlineKeyboardButton(
                str(w['char_id']),
                callback_data=f"shoproll_{user_id}_{w['char_id']}"
            )
        )
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # 🔐 Locked refresh button
    buttons.append([
        InlineKeyboardButton("🔄 Refresh Shop (500 💎)", callback_data=f"shoprefresh_{user_id}")
    ])

    markup = InlineKeyboardMarkup(buttons)
    await context.bot.send_photo(
    chat_id=update.effective_chat.id,
    photo=DEFAULT_BANNER,
    caption=caption,
    parse_mode="Markdown",
    reply_markup=markup,
    reply_to_message_id=update.effective_message.message_id
)




async def handle_waifu_roll(query, waifu_id: str, context: ContextTypes.DEFAULT_TYPE, shop_owner_id: int):
    user_id = query.from_user.id

    # 🔒 Restrict use to shop owner ONLY
    if user_id != shop_owner_id:
        await query.answer("⛔ This shop is not for you. Use /shop to access your own!", show_alert=True)
        return

    shop_data = get_shop(shop_owner_id)

    if shop_data is None:
        await query.answer("❌ Shop expired. Use /shop again.", show_alert=True)
        return

    if shop_data["Rolls"] >= 3:
        await query.answer("🎲 Max 3 rolls per day reached!", show_alert=True)
        return

    if waifu_id in shop_data["Rolled ids"]:
        await query.answer("❌ You already rolled this waifu!", show_alert=True)
        return

    waifu_list = shop_data["Waifus"]
    waifu = next((w for w in waifu_list if w["char_id"] == waifu_id), None)
    if not waifu:
        await query.answer("❌ Waifu not found in your shop!", show_alert=True)
        return

    cost = RARITY_CONFIG[waifu["rarity"]]["cost"]*10 
    chance = 0.90

    if get_balance(user_id, "Lunar Crystals") < cost:
        await query.answer("🌙 Not enough lunar crystals!", show_alert=True)
        return

    success = random.random() < chance
    update_balance(user_id, "Lunar Crystals", -cost)
    record_roll(user_id, waifu_id)

    if success:
        increment_character(user_id, waifu_id)
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=WIN_BANNER,
                caption=f"🎉 You rolled for <b>{waifu['name']}</b> and <b>WON!</b> 👑\nShe's now in your harem!",
                parse_mode="HTML"
            )
        )
    else:
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=LOSE_BANNER,
                caption=f"💔 You rolled for <b>{waifu['name']}</b> and <b>FAILED!</b> 😢\nBetter luck next time!",
                parse_mode="HTML"
            )
        )


from telegram.error import TelegramError
import html 

async def handle_shop_refresh(query, context, actual_user_id: int):
    user_id = query.from_user.id

    # 🔒 Only allow the actual owner of the shop to refresh
    if user_id != actual_user_id:
        await query.answer("⛔ This shop is not for you. Use /shop to open your own!", show_alert=True)
        return

    shop_data = get_shop(actual_user_id)

    if shop_data["Refreshes"] >= 2:
        await query.answer("🔁 Max 2 refreshes per day!", show_alert=True)
        return

    if get_balance(actual_user_id,"Primogems") < 500:
        await query.answer("💎 Not enough primogems to refresh!", show_alert=True)
        return

    update_balance(actual_user_id,"Primogems",-500)
    new_waifus = generate_random_waifus()
    refresh_shop(actual_user_id, new_waifus)
    shop_data = get_shop(actual_user_id)

    user_harem = get_harem(actual_user_id)
    owned_ids = {char_id: count for char_id, count in user_harem.items()}
    rolled_ids = shop_data.get("Rolled ids", [])
    lunar = get_balance(user_id, "Lunar Crystals")
    waifus = shop_data["Waifus"]

    caption = f"📦 <b>Your Waifu Shop (Refreshed)</b>\n"
    caption += f"🌙 <b>lunar crystals:</b> <code>{lunar}</code>\n"
    caption += f"🎲 Rolls used: <code>{shop_data['Rolls']}/3</code> | 🔁 Refreshes: <code>{shop_data['Refreshes']}/2</code>\n\n"

    for w in waifus:
        emoji = RARITY_CONFIG[w['rarity']]['symbol']
        cost = RARITY_CONFIG[w['rarity']]['cost'] * 10
        name = html.escape(w['name'])  
        status = ""
        if w["char_id"] in owned_ids:
            status = f"✅ x{owned_ids[w['char_id']]}"
        caption += f" <code>{w['char_id']}</code> | {name} | {emoji} | 🌙 {cost} | {status}\n"

    caption += "\n<i>Tap a waifu ID below to roll!</i>"

    # 🔐 Add shop owner to all callback data
    buttons, row = [], []
    for idx, w in enumerate(waifus):
        row.append(InlineKeyboardButton(str(w["char_id"]), callback_data=f"shoproll_{actual_user_id}_{w['char_id']}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔄 Refresh Shop (500 💎)", callback_data=f"shoprefresh_{actual_user_id}")])
    markup = InlineKeyboardMarkup(buttons)

    try:
        await query.edit_message_caption(
            caption=caption,
            reply_markup=markup,
            parse_mode="HTML"
        )
    except TelegramError as e:
        if "Message is not modified" in str(e):
            await query.answer("ℹ️ Shop was already up to date.")
        else:
            raise
async def shop_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    from_user_id = query.from_user.id

    if data.startswith("shoproll_"):
        parts = data.split("_", 2)
        if len(parts) < 3:
            await query.answer("⚠️ Invalid callback data.", show_alert=True)
            return

        _, owner_id, waifu_id = parts
        if str(from_user_id) != owner_id:
            await query.answer("⛔ This shop isn’t yours! Use /shop to open your own.", show_alert=True)
            return
        await handle_waifu_roll(query, waifu_id, context, shop_owner_id=int(owner_id))

    elif data.startswith("shoprefresh_"):
        _, owner_id = data.split("_", 1)
        if str(from_user_id) != owner_id:
            await query.answer("⛔ This shop isn’t yours! Use /shop to open your own.", show_alert=True)
            return

        await handle_shop_refresh(query, context, actual_user_id=int(owner_id))

    await query.answer()

async def reset_rolls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id

    if admin_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("🔁 Reply to the user you want to reset rolls for.")
        return

    target_user_id = update.message.reply_to_message.from_user.id
    record_roll(target_user_id,reset=True,waifu_id=None)

    await update.message.reply_text(f"✅ Reset rolls & refreshes for user ID `{target_user_id}`", parse_mode='Markdown')

async def setwaifu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("❗ Usage: /setwaifu <waifu_id>")
        return

    # Check limit
    usage_count = get_setwaifu_count(user_id)
    if usage_count >= 2:
        await update.message.reply_text("🚫 You can only set your waifu path 2 times per day. Try again tomorrow.")
        return

    waifu_id = context.args[0].strip()
    path_doc = get_user_path(user_id)

    # User already has a path set and it's valid
    if path_doc and path_doc.get("waifu_id"):
        waifu_id = path_doc["waifu_id"]
        pity = path_doc.get("pity", 0)
        characters = load_characters()
        waifu = characters.get(waifu_id)

        name = waifu['name']
        rarity = waifu['rarity']
        emoji = RARITY_CONFIG[rarity]['symbol']
        img_url = waifu.get('image_path', DEFAULT_BANNER)

        caption = (
            f"⚠️ <b>You already have a wish path set!</b>\n\n"
            f"🆔 <b>{waifu_id}</b>\n"
            f"👤 <b>{name}</b>\n"
            f"{emoji} <b>{rarity}</b>\n"
            f"🎲 <b>Pity: {pity}/10</b>\n\n"
            f"You must wish and win this waifu before setting a new path.\n"
            f"100 🌙 Lunar Crystals per wish"
        )

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=img_url,
            caption=caption,
            parse_mode="HTML"
        )
        return


    # Load waifu data
    characters = load_characters()
    waifu = characters.get(waifu_id)

    if not waifu:
        await update.message.reply_text("❌ Waifu not found.")
        return
    
    # Check if the waifu is of 'Bride' rarity and disallow setting it
    if waifu["rarity"] == "Bride":
        await update.message.reply_text("🚫 You cannot set a waifu with 'Bride' rarity as your wish path.")
        return

    name = waifu["name"]
    rarity = waifu["rarity"]
    emoji = RARITY_CONFIG[rarity]["symbol"]
    img_url = waifu.get("image_path", DEFAULT_BANNER)

    caption = f"🆔 <b>{waifu_id}</b>\n <b>{name}</b>\n <b>{rarity}</b> {emoji}\n\nSet this waifu as your wish path?"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data=f"setpath_confirm_{waifu_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="setpath_cancel")
        ]
    ])

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=img_url,
        caption=caption,
        parse_mode="HTML",
        reply_markup=keyboard
    )
async def setwaifu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data.startswith("setpath_confirm_"):
        waifu_id = data.split("_", 2)[2]
        try:
            set_user_path(user_id, waifu_id)
            increment_setwaifu_count(user_id)
            await query.edit_message_caption(
                caption=f"✅ Path set to <b>{waifu_id}</b>.\nUse /waifu to make your wish!\nNote:100 lunar crystals per /waifu",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"[ERROR: setwaifu_callback_handler] {e}")
            await query.edit_message_caption(
                caption="❌ An error occurred while setting path. Please try again.",
                parse_mode="HTML"
            )

WISH_GIF = "https://res.cloudinary.com/dvpz1tzam/video/upload/v1752931804/le-sserafim-le-sserafim-easy_k68zwt.mp4"  
WISH_COST = 100
async def makeawish_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    username = user.first_name or user.username or "Someone"
    path = get_user_path(user_id)

    if not path:
        await update.message.reply_text(
            "🎯 You need to /setwaifu <id> before wishing!",
            reply_to_message_id=update.message.message_id,
        )
        return

    waifu_id = path["waifu_id"]
    pity = path["pity"]

    if get_balance(user_id, "Lunar Crystals") < WISH_COST:
        await update.message.reply_text(
            "🌙 Not enough lunar crystals to make a wish!",
            reply_to_message_id=update.message.message_id,
        )
        return

    update_balance(user_id, "Lunar Crystals", -WISH_COST)
    gif_msg = await context.bot.send_animation(
        chat_id=chat_id,
        animation=WISH_GIF,
        reply_to_message_id=update.message.message_id,
    )
    
    await asyncio.sleep(1)
    await gif_msg.delete()
    won = roll_for_path_waifu(user_id, waifu_id)
    waifu = load_characters().get(waifu_id)
    name = waifu["name"]
    rarity = waifu["rarity"]
    emoji = RARITY_CONFIG[rarity]["symbol"]
    art = waifu.get("image_path", DEFAULT_BANNER)

    if won:
        update_harem(user_id, waifu_id,1,rarity=None)
        clear_user_path(user_id)
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=art,
            caption=(
                f"🎉 <b>{username}</b> successfully wished for <b>{name}</b> {emoji}!\n"
                "She is now in your harem! ❤️"
            ),
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id,
        )
    else:
        increment_pity(user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"💔 <b>{username}</b> failed to win <b>{name}</b>...\n"
                f"Pity: {pity + 1}/10\nBetter luck next time!"
            ),
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id,
        )

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.first_name

    try:
        amount = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: /convert <amount>")
        return

    primogems = get_primogems(user_id)
    mora = get_balance(user_id, "Mora")
    lunar = get_balance(user_id, "Lunar Crystals")

    caption = (
        f"🌀 Currency Converter for {username}\n\n"
        f"💠 Primogems: {primogems}\n"
        f"💰 Mora: {mora}\n"
        f"🌙 Lunar Crystals: {lunar}\n\n"

        f"🔁 {amount} Mora → {amount // 10} Primogems\n"
        f"🔁 {amount} Primogems → {amount // 10} Lunar Crystals\n"
        f"🔁 {amount} Primogems → {amount * 8} Mora\n\n"
        "Choose a conversion ↓"
    )

    keyboard = [
        [InlineKeyboardButton("💰 Mora → Primogems", callback_data=f"convert:{user_id}:mora_to_primogem:{amount}")],
        [InlineKeyboardButton("💠 Primogems → Lunar Crystals", callback_data=f"convert:{user_id}:primo_to_lunar:{amount}")],
        [InlineKeyboardButton("💠 Primogems → Mora", callback_data=f"convert:{user_id}:primo_to_mora:{amount}")],
        [InlineKeyboardButton("❌ Close", callback_data=f"convert:{user_id}:close:0")]
    ]

    await update.message.reply_text(
        caption,
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=update.message.message_id
    )


def round_down_to_multiple(amount: int, multiple: int) -> int:
    return amount - (amount % multiple)


async def convert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split(":")

    try:
        _, locked_user_id, action, raw_amount = parts
        locked_user_id = int(locked_user_id)
        amount = int(raw_amount)
    except:
        await query.answer("❌ Invalid callback data.", show_alert=True)
        return

    user_id = query.from_user.id
    username = query.from_user.first_name

    # Lock to prevent other users pressing buttons
    if user_id != locked_user_id:
        await query.answer("❌ Only the command user can use these buttons.", show_alert=True)
        return

    if action == "close":
        await query.message.delete()
        return

    primos = get_primogems(user_id)
    mora = get_balance(user_id, "Mora")
    lunar = get_balance(user_id, "Lunar Crystals")

    result = "❌ Invalid conversion."

    # === MORA → PRIMOGEMS ===
    if action == "mora_to_primogem":
        valid_amount = round_down_to_multiple(amount, 10)
        if mora >= valid_amount and valid_amount > 0:
            # deduct mora
            update_balance(user_id, "Mora", -valid_amount)
            # add primos
            update_primos(user_id, valid_amount // 10)

            result = f"✅ {username} converted {valid_amount} Mora → {valid_amount // 10} Primogems!"
        else:
            result = "❌ Not enough Mora."

    # === PRIMO → LUNAR CRYSTALS ===
    elif action == "primo_to_lunar":
        valid_amount = round_down_to_multiple(amount, 10)
        if primos >= valid_amount and valid_amount > 0:
            update_primos(user_id, -valid_amount)
            update_balance(user_id, "Lunar Crystals", valid_amount // 10)

            result = f"✅ {username} converted {valid_amount} Primogems → {valid_amount // 10} Lunar Crystals!"
        else:
            result = "❌ Not enough Primogems."

    # === PRIMOGEMS → MORA ===
    elif action == "primo_to_mora":
        if primos >= amount and amount > 0:
            update_primos(user_id, -amount)
            update_balance(user_id, "Mora", amount * 8)

            result = f"✅ {username} converted {amount} Primogems → {amount * 8} Mora!"
        else:
            result = "❌ Not enough Primogems."

    await query.edit_message_text(result)
    await query.answer()



async def inv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    user_id = update.effective_user.id

    primogems = get_balance(user_id,"Primogems")
    mora = get_balance(user_id,"Mora")
    lunar = get_balance(user_id,"Lunar Crystals")

    message = (
        f"💼 Your Inventory:\n\n"
        f"💠 Primogems: {primogems}\n"
        f"💰 Mora: {mora}\n"
        f"🌙 Lunar Crystals: {lunar}"
    )
    await update.message.reply_text(message)

ADMIN_GROUP_CHAT_ID = -1002043895840

TG_MSG_LIMIT = 4000

import random
from telegram.helpers import escape_markdown

async def airdrop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /airdrop <max_amount> [message]")
        return

    max_amount = int(context.args[0])
    if max_amount <= 0:
        await update.message.reply_text("Please specify a positive integer amount.")
        return

    msg_text = " ".join(context.args[1:]).strip()
    if not msg_text:
        await update.message.reply_text("Usage: /airdrop <max_amount> [message]")
        return
    from db import get_all_users_ids
    user_ids = get_all_users_ids
    if not user_ids:
        await update.message.reply_text("No users found to airdrop Lunar Crystals.")
        return

    results = []

    for uid in user_ids:
        amount = random.randint(0, max_amount)

        if amount > 0:
            update_balance(uid, "Lunar Crystals", amount)
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"🎉 You received <b>{amount}</b> Lunar Crystals! 🌙\n{msg_text}",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Failed to send DM to user {uid}: {e}")

        results.append((uid, amount))

    report_lines = [
        "<b>🌙 Airdrop Moment!</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "<b>🎁 Lucky Travelers received Lunar Crystals! 🎁</b>",
        ""
    ]

    for uid, amt in results:
        report_lines.append(f"✨ <code>{uid}</code> — {amt} Lunar Crystals")

    report_lines.append("")
    report_lines.append(msg_text)
    report_lines.append("━━━━━━━━━━━━━━━━━━━━")
    report_lines.append("<b>🏮 May your fortune shine bright in Teyvat! 🏮</b>")

    TG_MSG_LIMIT = 3900
    chunks = []
    current_chunk = []
    current_length = 0

    for line in report_lines:
        line_len = len(line) + 1
        if current_length + line_len > TG_MSG_LIMIT:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_length = line_len
        else:
            current_chunk.append(line)
            current_length += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    for chunk in chunks:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_CHAT_ID,
            text=chunk,
            parse_mode="HTML"
        )

    await update.message.reply_text("🎉 Airdrop completed! Report sent to the admin group.")

async def drop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /drop <amount> [message]")
        return

    amount = int(context.args[0])
    if amount <= 0:
        await update.message.reply_text("Please specify a positive integer amount.")
        return

    msg_text = " ".join(context.args[1:]).strip()
    if not msg_text:
        await update.message.reply_text("Usage: /drop <amount> [message]")
        return

    from db import get_all_users_ids
    user_ids = get_all_users_ids()
    if not user_ids:
        await update.message.reply_text("No users found to drop Lunar Crystals.")
        return

    results = []

    for uid in user_ids:
        update_balance(uid, "Lunar Crystals", amount)
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"🎉 You received <b>{amount}</b> Lunar Crystals! 🌙\n{msg_text}",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Failed to send DM to user {uid}: {e}")

        results.append((uid, amount))

    report_lines = [
        "<b>🌙 Drop Event!</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"<b>Every user received {amount} Lunar Crystals!</b>",
        ""
    ]

    for uid, amt in results:
        report_lines.append(f"✨ <code>{uid}</code> — {amt} Lunar Crystals")

    report_lines.append("")
    report_lines.append(msg_text)
    report_lines.append("━━━━━━━━━━━━━━━━━━━━")
    report_lines.append("<b>🏮 May fortune bless all Travelers! 🏮</b>")

    TG_MSG_LIMIT = 3900
    chunks = []
    current_chunk = []
    current_length = 0

    for line in report_lines:
        line_len = len(line) + 1
        if current_length + line_len > TG_MSG_LIMIT:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_length = line_len
        else:
            current_chunk.append(line)
            current_length += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    for chunk in chunks:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_CHAT_ID,
            text=chunk,
            parse_mode="HTML"
        )

    await update.message.reply_text("🎉 Drop completed! Report sent to the admin group.")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Usage: /buy <waifu_id>")
        return

    waifu_id = context.args[0].strip()
    characters = load_characters()
    waifu = characters.get(waifu_id)

    if not waifu:
        await update.message.reply_text("❌ Waifu not found.")
        return

    price = waifu.get("price", 300)
    name = waifu["name"]
    rarity = waifu["rarity"]
    emoji = RARITY_CONFIG[rarity]["symbol"]
    img_url = waifu.get("image_path", DEFAULT_BANNER)

    user_balance = get_balance(user_id, "Lunar Crystals")
    if user_balance < price:
        await update.message.reply_text(
            f"❌ Not enough Lunar Crystals.\nRequired: <b>{price}</b>\nYou have: <b>{user_balance}</b>",
            parse_mode="HTML"
        )
        return

    caption = (
        f"🆔 <b>{waifu_id}</b>\n"
        f"👤 <b>{name}</b>\n"
        f"{emoji} <b>{rarity}</b>\n"
        f"🌙 <b>Price: {price} Lunar Crystals</b>\n\n"
        f"Do you want to buy this waifu?"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Buy", callback_data=f"buy_confirm_{waifu_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="buy_cancel")
        ]
    ])

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=img_url,
        caption=caption,
        parse_mode="HTML",
        reply_markup=keyboard
    )
async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data == "buy_cancel":
        await query.edit_message_caption(
            caption="❌ Purchase cancelled.",
            parse_mode="HTML",
            reply_markup=None
        )
        return

    if data.startswith("buy_confirm_"):
        waifu_id = data.split("_", 2)[2]
        characters = load_characters()
        waifu = characters.get(waifu_id)

        if not waifu:
            await query.edit_message_caption(
                caption="❌ Waifu no longer exists.",
                parse_mode="HTML"
            )
            return

        price = waifu.get("price", 300)
        user_balance = get_balance(user_id, "Lunar Crystals")

        if user_balance < price:
            await query.edit_message_caption(
                caption="❌ Purchase failed. Not enough Lunar Crystals.",
                parse_mode="HTML",
                reply_markup=None
            )
            return

        update_balance(user_id, "Lunar Crystals", -price)
        increment_character(user_id, waifu_id)

        await query.edit_message_caption(
            caption=f"🎉 Purchase successful!\nYou bought <b>{waifu['name']}</b> ❤️",
            parse_mode="HTML",
            reply_markup=None
        )

                                     

def register_shop_handlers(application):

    application.add_handler(CommandHandler("shop", shop_command), group=0)
    application.add_handler(CallbackQueryHandler(shop_callback_handler, pattern="^shop"), group=0)
    application.add_handler(CommandHandler("resetrolls", reset_rolls_command), group=0)
    application.add_handler(CommandHandler("setwaifu", setwaifu_command))
    application.add_handler(CommandHandler("waifu", makeawish_command))
    application.add_handler(CallbackQueryHandler(setwaifu_callback_handler, pattern="^setpath_"))
    application.add_handler(CommandHandler("convert", convert_command))
    application.add_handler(CallbackQueryHandler(convert_callback, pattern=r"^convert:"))
    application.add_handler(CommandHandler("inv", inv_command))
    application.add_handler(CommandHandler("airdrop", airdrop))
    application.add_handler(CommandHandler("drop", drop))
    application.add_handler(CommandHandler("buy", buy_command))
    application.add_handler(CallbackQueryHandler(buy_callback, pattern=r"^buy_"))
    print("✅ Shop system registered.")
