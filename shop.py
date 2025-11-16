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
    get_db_connection,
    load_characters,
    get_primogem_balance,
    deduct_primogems,
    add_character_to_inventory,
    get_user_harem,
    RARITY_CONFIG,
)

from db import get_balance,update_shop,get_shop,update_balance,refresh_shop,get_harem,record_roll,increment_character

DEFAULT_BANNER = "https://res.cloudinary.com/dvpz1tzam/image/upload/v1752917631/74ca7946-ebeb-4873-b24e-f00fd1219dce_fqsepm.png"
WIN_BANNER = "https://res.cloudinary.com/dvpz1tzam/image/upload/v1752918095/01d1867d-d611-4dda-8abc-7ea78c49656f_n6rk6a.png"
LOSE_BANNER = "https://res.cloudinary.com/dvpz1tzam/image/upload/v1752918099/generated-image_1_l25yk8.png"


ADMIN_IDS = [5192424390]

def create_user_shop_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_shop (
            user_id INTEGER PRIMARY KEY,
            shop_waifus TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            daily_refreshes INTEGER DEFAULT 0,
            daily_rolls INTEGER DEFAULT 0,
            rolled_ids TEXT DEFAULT '[]'
        )
    ''')
    conn.commit()
    conn.close()
def create_user_path_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_path (
            user_id INTEGER PRIMARY KEY,
            waifu_id TEXT NOT NULL,
            pity INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
def create_waifu_tracking_table():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS waifu_set_log (
                user_id INTEGER,
                date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, date)
            )
        """)
        conn.commit()
        print("[✔] Table 'waifu_set_log' created or already exists.")
def create_currency_tables():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mora (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lunar_crystals (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        print("[✔] Table 'lunar_crystals' created or already exists.")

def reset_waifu_set_log_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS waifu_set_log")
    conn.commit()
    conn.close()



def deduct_currency(user_id: int, table_name: str, amount: int) -> bool:
    try:
        current = get_balance(user_id, table_name)
        if current >= amount:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                    f"UPDATE {table_name} SET balance = balance - ? WHERE user_id = ?",
                    (amount, user_id)
                )
            conn.commit()
            return True
    except Exception as e:
        print(f"[❌ deduct_currency ERROR] {e}")
    return False
def add_currency(user_id: int, table_name: str, amount: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    if table_name == "users":
        cursor.execute("SELECT primogems FROM users WHERE user_id = ?", (user_id,))
        current = cursor.fetchone()
        if current is None:
            cursor.execute(
                "INSERT INTO users (user_id, primogems) VALUES (?, ?)",
                (user_id, amount)
            )
        else:
            cursor.execute(
                "UPDATE users SET primogems = primogems + ? WHERE user_id = ?",
                (amount, user_id)
            )
    else:
        cursor.execute(f"SELECT balance FROM {table_name} WHERE user_id = ?", (user_id,))
        current = cursor.fetchone()
        if current is None:
            cursor.execute(
                f"INSERT INTO {table_name} (user_id, balance) VALUES (?, ?)",
                (user_id, amount)
            )
        else:
            cursor.execute(
                f"UPDATE {table_name} SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
    conn.commit()
def get_all_users_ids():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_user_path(user_id: int) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT waifu_id, pity FROM user_path WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"waifu_id": row[0], "pity": row[1]}
    return None
def set_user_path(user_id: int, waifu_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR IGNORE INTO user_path (user_id, waifu_id, pity)
        VALUES (?, ?, 0)
    ''', (user_id, waifu_id))
    
    conn.commit()
    conn.close()

def clear_user_path(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_path WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
def increment_pity(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE user_path SET pity = pity + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
def get_waifu_details(waifu_id: str) -> dict | None:
    characters = load_characters()
    return characters.get(waifu_id)

import random

import random

def roll_for_path_waifu(user_id: int, waifu_id: str) -> bool:
    path_data = get_user_path(user_id)
    pity = path_data["pity"] if path_data else 0  
    chance = 0.10 + (pity * 0.05)
    chance = min(chance, 1.0)
    return random.random() < chance
 

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def get_setwaifu_count(user_id: int) -> int:
    today = get_today()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT count FROM waifu_set_log WHERE user_id = ? AND date = ?", (user_id, today))
    row = cursor.fetchone()
    return row[0] if row else 0

def increment_setwaifu_count(user_id: int):
    today = get_today()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO waifu_set_log (user_id, date, count)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1
    ''', (user_id, today))
    conn.commit()
    conn.close()


from datetime import datetime


def save_user_shop(user_id: int, waifu_list: list, reset_counters=True):
    conn = get_db_connection()
    cursor = conn.cursor()
    waifus_json = json.dumps(waifu_list)
    now = datetime.now().isoformat()
    rolled_ids = json.dumps([])

    if reset_counters:
        cursor.execute('''
            INSERT OR REPLACE INTO user_shop
            (user_id, shop_waifus, last_updated, daily_refreshes, daily_rolls, rolled_ids)
            VALUES (?, ?, ?, 0, 0, ?)
        ''', (user_id, waifus_json, now, rolled_ids))
    else:
        cursor.execute('''
            UPDATE user_shop SET shop_waifus = ?, last_updated = ?, rolled_ids = ?
            WHERE user_id = ?
        ''', (waifus_json, now, rolled_ids, user_id))
    conn.commit()
    conn.close()


def record_waifu_rolled(user_id: int, waifu_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT rolled_ids FROM user_shop WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        rolled = json.loads(row[0]) if row[0] else []
        if waifu_id not in rolled:
            rolled.append(waifu_id)
            cursor.execute(
                "UPDATE user_shop SET rolled_ids = ?, daily_rolls = daily_rolls + 1 WHERE user_id = ?",
                (json.dumps(rolled), user_id))
            conn.commit()
    conn.close()


def increment_shop_counter(user_id: int, counter_type: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    if counter_type == "refresh":
        cursor.execute("UPDATE user_shop SET daily_refreshes = daily_refreshes + 1 WHERE user_id = ?", (user_id,))
    elif counter_type == "roll":
        cursor.execute("UPDATE user_shop SET daily_rolls = daily_rolls + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

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
    path = get_user_path(user_id)

    # User has already set a path, do not allow change until claimed
    if path:
        waifu_id = path['waifu_id']
        pity = path['pity']
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

    if get_balance(user_id, "lunar_crystals") < WISH_COST:
        await update.message.reply_text(
            "🌙 Not enough lunar crystals to make a wish!",
            reply_to_message_id=update.message.message_id,
        )
        return

    deduct_currency(user_id, "lunar_crystals", WISH_COST)
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
        add_character_to_inventory(user_id, waifu_id)
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

    primogems = get_primogem_balance(user_id)
    mora = get_balance(user_id, "mora")
    lunar = get_balance(user_id, "lunar_crystals")

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
    except Exception:
        await query.answer("❌ Invalid callback data.", show_alert=True)
        return

    user_id = query.from_user.id
    username = query.from_user.first_name

    # User lock check
    if user_id != locked_user_id:
        await query.answer("❌ Only the command user can use these buttons.", show_alert=True)
        return

    if action == "close":
        await query.message.delete()
        return

    primos = get_primogem_balance(user_id)
    mora = get_balance(user_id, "mora")
    lunar = get_balance(user_id, "lunar_crystals")

    result = "❌ Invalid conversion."

    if action == "mora_to_primogem":
        valid_amount = round_down_to_multiple(amount, 10)
        if mora >= valid_amount and valid_amount > 0:
            deduct_currency(user_id, "mora", valid_amount)
            add_currency(user_id, "users", valid_amount // 10)
            result = f"✅ {username} converted {valid_amount} Mora → {valid_amount // 10} Primogems!"
        else:
            result = "❌ Not enough Mora."

    elif action == "primo_to_lunar":
        valid_amount = round_down_to_multiple(amount, 10)
        if primos >= valid_amount and valid_amount > 0:
            deduct_primogems(user_id, valid_amount)
            add_currency(user_id, "lunar_crystals", valid_amount // 10)
            result = f"✅ {username} converted {valid_amount} Primogems → {valid_amount // 10} Lunar Crystals!"
        else:
            result = "❌ Not enough Primogems."

    elif action == "primo_to_mora":
        if primos >= amount and amount > 0:
            deduct_primogems(user_id, amount)
            add_currency(user_id, "mora", amount * 8)
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

def bold(text):
    return f"*{text}*"

def mono(text):
    return f"`{text}`"

def italic(text):
    return f"_{text}_"

async def airdrop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Admin lock
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    # Require at least amount; optional message follows
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

    user_ids = get_all_users_ids()
    if not user_ids:
        await update.message.reply_text("No users found to airdrop lunar crystals.")
        return

    results = []

    for uid in user_ids:
        amount = random.randint(0, max_amount)
        if amount > 0:
            add_currency(uid, "lunar_crystals", amount)
            try:
                # Send DM to each user
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"🎉 You received {bold(str(amount))} Lunar Crystals as part of an airdrop! 🌙\n"
                        f"{msg_text}"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                # Likely the user hasn't started the bot or blocked it
                print(f"Failed to send DM to user {uid}: {e}")

        results.append((uid, amount))

    report_lines = [
        bold("🌙 Airdrop Moment! 🌙"),
        "━━━━━━━━━━━━━━━━━━━━",
        "🎁 *Lucky Travelers received Lunar Crystals!* 🎁",
        "",
    ]

    for uid, amt in results:
        report_lines.append(f"✨ {mono(str(uid))} — _{amt} Lunar Crystals_ ")

    report_lines.append("")
    report_lines.append(f"{msg_text}")
    report_lines.append("━━━━━━━━━━━━━━━━━━━━")
    report_lines.append("🏮 *May your fortune shine bright in Teyvat!* 🏮")

    # Chunk to respect Telegram message limits
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
            parse_mode="Markdown"
        )

    await update.message.reply_text("🎉 Airdrop completed! Report sent to the admin group.")

                                     

def register_shop_handlers(application):
    create_user_shop_table()
    create_user_path_table()
    reset_waifu_set_log_table()
    create_waifu_tracking_table()
    create_currency_tables()
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
    print("✅ Shop system registered.")
