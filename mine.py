import sqlite3
import json
import random
import asyncio
import uuid
from telegram import Update
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
from telegram.ext import ContextTypes
import os

from db import get_daily,update_claim,update_inv,user_exists,get_balance,update_balance
from db import update_mines,get_user_state,get_primogems
DATABASE = "/mnt/data/quiz.db"

from config import ALL_ADMINS
ADMIN_IDS = ALL_ADMINS  
DB_PATH = "/mnt/data/quiz.db" 
from db import update_balance


CURRENCY_MAP = {
    "primogems": "Primogems",
    "mora": "Mora",
    "lunar": "Lunar Crystals",
}

CURRENCY_ICONS = {
    "primogems": "✨",
    "mora": "💰",
    "lunar": "🌙",
}

CURRENCY_DISPLAY = {
    "primogems": "Primogems",
    "mora": "Mora",
    "lunar": "Lunar Crystals",
}

DEFAULT_CURRENCY = "primogems"

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Reply to a user's message with `/send <amount> [currency]`.\n"
            "Example: `/send 1000`, `/send 2000 mora`, `/send 1500 lunar`.",
            parse_mode="Markdown"
        )
        return

    sender_id = update.effective_user.id
    recipient_user = update.message.reply_to_message.from_user
    recipient_id = recipient_user.id
    recipient_name = recipient_user.full_name

    if sender_id == recipient_id:
        await update.message.reply_text("🚫 You cannot send currency to yourself.")
        return

    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
        currency = context.args[1].lower() if len(context.args) > 1 else DEFAULT_CURRENCY
    except:
        await update.message.reply_text(
            "⚠️ Usage: `/send <positive number> [primogems|mora|lunar]`",
            parse_mode="Markdown"
        )
        return

    if currency not in CURRENCY_MAP:
        currency = DEFAULT_CURRENCY

    db_key = CURRENCY_MAP[currency] 

    if not user_exists(recipient_id):
        await update.message.reply_text("❌ Recipient is not registered.")
        return

    sender_balance = get_balance(sender_id, db_key)

    if sender_balance < amount:
        await update.message.reply_text("❌ Not enough balance.")
        return

    update_balance(sender_id, db_key, -amount)  
    update_balance(recipient_id, db_key, amount) 

    icon = CURRENCY_ICONS.get(currency, "✨")

    await update.message.reply_text(
        f"{icon} You sent *{amount}* {CURRENCY_DISPLAY[currency]} to "
        f"[{recipient_name}](tg://user?id={recipient_id})!",
        parse_mode="Markdown"
    )

    
async def view_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ You're not authorized to view transaction history.")
        return

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sender_id, recipient_id, amount, currency, timestamp
            FROM transfers ORDER BY id DESC LIMIT 10
        """)
        rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("📭 No transactions found.")
        return

    CURRENCY_ICONS = {
        'primogems': '✨',
        'mora': '💰',
        'lunar': '🌙',
    }

    msg = "📜 *Recent Transactions:*\n\n"
    for s, r, amt, currency, ts in rows:
        try:
            sender = await context.bot.get_chat(s)
            sender_name = sender.full_name
        except Exception:
            sender_name = f"User {s}"

        try:
            recipient = await context.bot.get_chat(r)
            recipient_name = recipient.full_name
        except Exception:
            recipient_name = f"User {r}"

        icon = CURRENCY_ICONS.get(currency, '') 

        msg += f"🔁 [{sender_name}](tg://user?id={s}) → [{recipient_name}](tg://user?id={r}): {icon} *{amt}* {currency}\n🕒 `{ts}`\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# === Grid Helpers ===
def render_plain_grid(grid):
    return "\n".join([" ".join(grid[i:i+5]) for i in range(0, 25, 5)])

def render_button_grid(revealed, owner_id):
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            index = i * 5 + j
            tile = revealed[index]
            callback_data = f"tile_{index}_{owner_id}"  
            row.append(InlineKeyboardButton(tile, callback_data=callback_data))
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton("💰 Cash Out", callback_data=f"cashout_{owner_id}")
    ])
    return InlineKeyboardMarkup(keyboard)


def generate_grid_message(diamonds, bet, bombs):
    base_multiplier = 1.1 + (bombs - 3) * 0.05
    multiplier = base_multiplier ** diamonds
    reward = int(bet * multiplier)
    return (
        f"💎 Diamonds: {diamonds}\n"
        f"📈 Multiplier: x{multiplier:.2f}\n"
        f"🏆 Potential Winnings: {reward} primogems"
    )

async def start_mines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    primos = get_balance(user_id, "Primogems")

    if get_user_state(user_id):
        await update.message.reply_text("❌ You already have an active mine game.")
        return

    # Args
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /mines <bet> <bombs>")
        return

    try:
        bet = int(context.args[0])
        bombs = int(context.args[1])
    except:
        await update.message.reply_text("❌ Bet and bombs must be numbers.")
        return

    if bombs < 3 or bombs > 24:
        await update.message.reply_text("❌ Bombs must be between 3 and 24.")
        return

    if bet <= 0:
        await update.message.reply_text("❌ Bet must be greater than zero.")
        return

    if primos < bet:
        await update.message.reply_text("❌ Not enough primogems.")
        return

    update_balance(user_id, "Primogems", -bet)

    tiles = ["💎"] * (25 - bombs) + ["💣"] * bombs
    random.shuffle(tiles)

    state = {
        "owner_id": user_id,
        "grid": tiles,
        "revealed": ["⬜"] * 25,
        "diamonds_found": 0,
        "bet": bet,
        "bombs": bombs
    }

    update_mines(user_id, state)

    grid_msg = generate_grid_message(0, bet, bombs)
    markup = render_button_grid(state["revealed"], user_id)

    await update.message.reply_text(f"🧨 Mines Game Started!\n\n{grid_msg}", reply_markup=markup)

async def handle_tile_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    try:
        _, idx, owner_str = query.data.split("_")
        idx = int(idx)
        owner_id = int(owner_str)
    except:
        return await query.answer("❌ Invalid tile data")

    if user_id != owner_id:
        return await query.answer("❌ Not your game!", show_alert=True)

    state = get_user_state(owner_id)
    if not state:
        return await query.message.edit_text("❌ No active mine game.")

    if state["revealed"][idx] != "⬜":
        return  

    symbol = state["grid"][idx]
    state["revealed"][idx] = symbol

    # Bomb
    if symbol == "💣":
        update_mines(owner_id, None)
        full_grid = render_plain_grid(state["grid"])
        return await query.message.edit_text(
            f"💥 You hit a bomb!\n\n💎 Found: {state['diamonds_found']}\n\n{full_grid}"
        )

    state["diamonds_found"] += 1
    update_mines(owner_id, state)

    grid_msg = generate_grid_message(state["diamonds_found"], state["bet"], state["bombs"])
    markup = render_button_grid(state["revealed"], owner_id)

    await query.message.edit_text(f"💠 Still safe!\n{grid_msg}", reply_markup=markup)

async def handle_cashout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    try:
        _, owner_str = query.data.split("_")
        owner_id = int(owner_str)
    except:
        return await query.answer("❌ Invalid data", show_alert=True)

    if user_id != owner_id:
        return await query.answer("❌ Not your game!", show_alert=True)

    state = get_user_state(user_id)
    if not state:
        return await query.answer("❌ No active game", show_alert=True)

    diamonds = state["diamonds_found"]
    bet = state["bet"]
    bombs = state["bombs"]

    if diamonds < 3:
        return await query.answer("💎 Need at least 3 diamonds to cash out!", show_alert=True)

    base = 1.1 + (bombs - 3) * 0.05
    reward = int(bet * (base ** diamonds))

    update_mines(user_id, None)
    update_balance(user_id, "Primogems", reward)

    full_grid = render_plain_grid(state["grid"])

    await query.message.edit_text(
        f"💰 Cashed out!\n\n💎 Found: {diamonds}\n🎯 Reward: {reward} primogems\n\n{full_grid}"
    )

async def stop_mine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not get_user_state(user_id):
        return await update.message.reply_text("❌ No active mine game.")

    update_mines(user_id, None)
    await update.message.reply_text("🛑 Mine game stopped.")

# === Show Primogems ===
async def primogems(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_balance(user_id,"Primogems")
    if not user:
        await update.message.reply_text("You have 0 primogems.")
        return
    await update.message.reply_text(f"You have {user} primogems.")

async def daily_primos(update, context):
    user_id = update.effective_user.id
    today = datetime.now().strftime('%Y-%m-%d')

    last_claim=get_daily(user_id)

    if last_claim==today:
        await update.message.reply_text("❌ Already claimed today.")
        return

    roll = random.randint(1, 100)
    primogems_amount = roll * 5
    mora_amount = roll * 100
    lunar_crystals_amount = roll * 1

    update_inv(user_id,primogems_amount,mora_amount,lunar_crystals_amount)
    update_claim(user_id)
    await update.message.reply_text(
        f"🎲 You rolled a {roll}!\n"
        f"✨ You received {primogems_amount} Primogems, {mora_amount} Mora, "
        f"and {lunar_crystals_amount} Lunar Crystals as your daily rewards! Come back tomorrow for another roll."
    )

VALID_CURRENCIES = {"primogems", "mora", "lunar_crystals", "crystals","lunar"}  # accepted inputs
DEFAULT_CURRENCY = "primogems"

async def add_primos_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ BAKA!! You don't have permission to use this command.")
        return
    args = context.args

    def resolve_currency(input_currency: str) -> str:
        currency_map = {
            "primogems": "primogems",
            "mora": "mora",
            "crystals": "lunar_crystals",
            "lunar_crystals": "lunar_crystals",
            "lunar":"lunar_crystals"
        }
        return currency_map.get(input_currency.lower())

    if update.message.reply_to_message:
        if len(args) < 1:
            await update.message.reply_text("❌ Usage (as reply): /add <amount> [currency]")
            return

        try:
            amount = int(args[0])
        except ValueError:
            await update.message.reply_text("❌ Amount must be a number.")
            return

        currency_input = args[1] if len(args) > 1 else DEFAULT_CURRENCY
        currency = resolve_currency(currency_input)

        if not currency:
            await update.message.reply_text(f"❌ Invalid currency '{currency_input}'. Use primogems, mora, or crystals.")
            return

        user_id = update.message.reply_to_message.from_user.id

        update_inv(
        user_id,
        primogems=amount if currency=="primogems" else 0,
        mora=amount if currency=="mora" else 0,
        lunar_crystals=amount if currency=="lunar_crystals" else 0
                   )

        await update.message.reply_text(
            f"✅ Added {amount} {currency} to <code>{user_id}</code>.",
            parse_mode="HTML",
            reply_to_message_id=update.message.reply_to_message.message_id
        )
        return

    if len(args) >= 2:
        try:
            user_id = int(args[0])
            amount = int(args[1])
        except ValueError:
            await update.message.reply_text("❌ Usage: /add <user_id> <amount> [currency]")
            return

        currency_input = args[2] if len(args) >= 3 else DEFAULT_CURRENCY
        currency = resolve_currency(currency_input)

        if not currency:
            await update.message.reply_text(f"❌ Invalid currency '{currency_input}'. Use primogems, mora, or crystals.")
            return

        update_inv(
            user_id,
            primogems=amount if currency == "primogems" else 0,
            mora=amount if currency == "mora" else 0,
            lunar_crystals=amount if currency == "lunar_crystals" else 0
        )

        await update.message.reply_text(
            f"✅ Added {amount} {currency} to <code>{user_id}</code>.",
            parse_mode="HTML"
        )
        return


    await update.message.reply_text(
        "❌ Usage:\n"
        "• Reply to a user: <code>/add &lt;amount&gt; [currency]</code>\n"
        "• Or: <code>/add &lt;user_id&gt; &lt;amount&gt; [currency]</code>\n\n"
        "Currency (optional): primogems (default), mora, crystals",
        parse_mode="HTML"
    )


async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) != 2:
        await update.message.reply_text("Usage: /dice <amount> even/odd or e/o")
        return

    try:
        bet = int(context.args[0])
        guess = context.args[1].lower()
    except:
        await update.message.reply_text("Invalid format. Use: /dice <amount> even/odd or e/o")
        return

    # ✅ Normalize guess
    if guess in ["even", "e"]:
        guess = "even"
    elif guess in ["odd", "o"]:
        guess = "odd"
    else:
        await update.message.reply_text("Guess must be 'even', 'odd', 'e' or 'o'.")
        return

    primos=get_balance(user_id,"Primogems")

    if bet <= 0:
        await update.message.reply_text("Bet must be more than 0.")
        return

    if bet > primos:
        await update.message.reply_text(f"You only have {primos} primogems!")
        return

    # 🎲 Roll the dice
    dice_msg = await update.message.reply_dice(emoji="🎲")
    await asyncio.sleep(1.5)
    result = dice_msg.dice.value
    parity = "even" if result % 2 == 0 else "odd"

    # ✅ Win/loss check
    if parity == guess:
        winnings = bet 
        update_balance(user_id,"Primogems",winnings)
        await update.message.reply_text(f"🎉 Dice landed on {result} ({parity}). You won {winnings} primogems!")
    else:
        update_balance(user_id,"Primogems",-bet)
        await update.message.reply_text(f"😢 Dice landed on {result} ({parity}). You lost {bet} primogems.")


import sqlite3
import json
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext
import random

DB_PATH = '/mnt/data/quiz.db'

# Ensure table exists
def init_tictactoe_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tictactoe_games (
        game_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_x_id INTEGER,
        user_o_id INTEGER,
        current_turn INTEGER,
        board TEXT,
        bet INTEGER DEFAULT 0,
        mode TEXT,
        last_move_ts INTEGER
    )''')
    conn.commit()
    conn.close()


def is_user_in_game(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM tictactoe_games WHERE (user_x_id = ? OR user_o_id = ?)", (user_id, user_id))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_user_primogems(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT primogems FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_primogems(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET primogems = primogems + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

async def start_tictactoe(update: Update, context: CallbackContext):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to challenge them.")
        return
    try:
        bet = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /tictactoe <bet_amount>")
        return

    challenger = update.effective_user
    receiver = update.message.reply_to_message.from_user

    if challenger.id == receiver.id:
        await update.message.reply_text("You can't challenge yourself!")
        return

    if is_user_in_game(challenger.id) or is_user_in_game(receiver.id):
        await update.message.reply_text("Either you or the opponent is already in a game.")
        return

    if get_user_primogems(challenger.id) < bet:
        await update.message.reply_text(f"{challenger.first_name} doesn't have enough primogems.")
        return
    if get_user_primogems(receiver.id) < bet:
        await update.message.reply_text(f"{receiver.first_name} doesn't have enough primogems.")
        return

    keyboard = [
        [InlineKeyboardButton("✅ Accept", callback_data=f"ttt_accept_{challenger.id}_{receiver.id}_{bet}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"ttt_reject_{challenger.id}")]
    ]
    await update.message.reply_text(f"{receiver.first_name}, you have been challenged by {challenger.first_name} for {bet} primogems. Accept?",
                              reply_markup=InlineKeyboardMarkup(keyboard))

async def tictactoe_accept_reject(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("ttt_reject_"):
        challenger_id = int(data.split("_")[2])
        await query.edit_message_text("Challenge rejected.")
        return

    if data.startswith("ttt_accept_"):
        _, _, cid, rid, bet = data.split("_")
        cid, rid, bet = int(cid), int(rid), int(bet)
        user = query.from_user
        if user.id != rid:
            await query.answer("You are not the challenged user.", show_alert=True)
            return

        board = [""] * 9
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO tictactoe_games (user_x_id, user_o_id, current_turn, board, bet, mode, last_move_ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (cid, rid, cid, json.dumps(board), bet, 'bet', int(time.time())))
        conn.commit()
        conn.close()
        await query.edit_message_text("Game started!")
        await show_tictactoe_board(cid, rid, cid, board, bet, 'bet', update, context)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup



async def show_tictactoe_board(uid1, uid2, turn_id, board, bet, mode, update, context, message_id=None, chat_id=None):
    user1 = await context.bot.get_chat(uid1)
    user2 = await context.bot.get_chat(uid2)
    turn_symbol = "❌" if turn_id == uid1 else "⭕"
    symbol_map = {
    "": "⬜",
    "X": "❌",
    "O": "⭕"
}

    text = f"🎮 Mode: {'Bet Match' if mode == 'bet' else 'Fun'}\n"
    text += f"🔁 Turn: {turn_symbol} ({(await context.bot.get_chat(turn_id)).first_name})\n"
    text += f"❌: {user1.first_name} | ⭕: {user2.first_name}\n\n"

    symbol_map = {"X": "❌", "O": "⭕", "": "⬜"}

    keyboard = []
    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            idx = i + j
            symbol = symbol_map.get(board[idx], "⬜")
            callback_data = f"ttmove_{uid1}_{uid2}_{turn_id}_{idx}" if board[idx] == "" else "ttdisabled"
            row.append(InlineKeyboardButton(symbol, callback_data=callback_data))
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if message_id and chat_id:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup
        )
    else:
        if update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=reply_markup)
            message_id = update.callback_query.message.message_id
            chat_id = update.callback_query.message.chat.id
        else:
            sent_msg = await update.message.reply_text(text, reply_markup=reply_markup)
            message_id = sent_msg.message_id
            chat_id = sent_msg.chat.id
    start_tictactoe_delete_timer(chat_id, message_id, context)


import asyncio

tictactoe_delete_tasks = {}

async def schedule_tictactoe_delete(chat_id, message_id, context, timeout=120):
    await asyncio.sleep(timeout)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass
   
    tictactoe_delete_tasks.pop((chat_id, message_id), None)

def start_tictactoe_delete_timer(chat_id, message_id, context, timeout=120):
    # Cancel existing task if any
    task_key = (chat_id, message_id)
    if task_key in tictactoe_delete_tasks:
        tictactoe_delete_tasks[task_key].cancel()

    
    tictactoe_delete_tasks[task_key] = asyncio.create_task(schedule_tictactoe_delete(chat_id, message_id, context, timeout))


async def tictactoe_move_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")

    # Unpack corrected for 5 parts, not 6
    if len(data) != 5:
        print(f"[ERROR] Unexpected callback data length: {data}")
        return
    _, uid1, uid2, turn_id, idx = data
    uid1, uid2, turn_id, idx = int(uid1), int(uid2), int(turn_id), int(idx)

    user = query.from_user
    

    if user.id != turn_id:
        print("[DEBUG] Not user's turn")
        await query.answer("Not your turn.", show_alert=True)
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT board, current_turn, bet, mode FROM tictactoe_games WHERE user_x_id = ? AND user_o_id = ?", (uid1, uid2))
    row = c.fetchone()
    if not row:
        conn.close()
        print("[DEBUG] Game not found")
        await query.answer("Game not found.", show_alert=True)
        return

    board = json.loads(row[0])
    bet = row[2]
    mode = row[3]

    if board[idx] != "":
        conn.close()
        print("[DEBUG] Tile already taken")
        await query.answer("Tile already taken.", show_alert=True)
        return

    board[idx] = "X" if user.id == uid1 else "O"
    next_turn = uid2 if user.id == uid1 else uid1
    

    winner = check_winner(board)
    now = int(time.time())

    if winner:
        symbol = "❌" if winner == "X" else "⭕"
        winner_id = uid1 if winner == "X" else uid2
        loser_id = uid2 if winner == "X" else uid1

        c.execute("DELETE FROM tictactoe_games WHERE user_x_id = ? AND user_o_id = ?", (uid1, uid2))
        conn.commit()
        conn.close()

        update_primogems(winner_id, bet)
        update_primogems(loser_id, -bet)

        first_name = (await context.bot.get_chat(winner_id)).first_name
        await query.edit_message_text(f"{symbol} {first_name} won the game and earned {bet} primogems!")
        return

    if "" not in board:
        update_primogems(uid1, bet)
        update_primogems(uid2, bet)

        c.execute("DELETE FROM tictactoe_games WHERE user_x_id = ? AND user_o_id = ?", (uid1, uid2))
        conn.commit()
        conn.close()

        await query.edit_message_text(f"🤝 Match was a draw! {bet} primogems refunded to both players.")
        return


    c.execute("UPDATE tictactoe_games SET board = ?, current_turn = ?, last_move_ts = ? WHERE user_x_id = ? AND user_o_id = ?",
              (json.dumps(board), next_turn, now, uid1, uid2))
    conn.commit()
    conn.close()

    await show_tictactoe_board(uid1, uid2, next_turn, board, bet, mode, update, context,
                               message_id=query.message.message_id, chat_id=query.message.chat.id)

def check_winner(board):
    wins = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for i, j, k in wins:
        if board[i] and board[i] == board[j] == board[k]:
            return board[i]
    return None

async def cancel_tictactoe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Find if this user is in a game
    c.execute("SELECT game_id, user_x_id, user_o_id, bet FROM tictactoe_games WHERE user_x_id = ? OR user_o_id = ?", (user_id, user_id))
    game = c.fetchone()

    if not game:
        await update.message.reply_text("❌ You are not currently in an active Tic-Tac-Toe game.")
        conn.close()
        return

    game_id, user_x_id, user_o_id, bet = game

    
    other_user_id = user_o_id if user_id == user_x_id else user_x_id

   
    if bet > 0:
        c.execute("UPDATE users SET primogems = primogems + ? WHERE user_id = ?", (bet, other_user_id))

   
    c.execute("DELETE FROM tictactoe_games WHERE game_id = ?", (game_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🛑 {user.first_name} has canceled the Tic-Tac-Toe game.\n"
        f"🎁 {bet} primogems awarded to the other player!"
    )





# --- Rock Paper Scissors Game ---

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import sqlite3
import random
rps_matches = {}  
def format_name(user):
    full_name = user.first_name
    if user.last_name:
        full_name += f" {user.last_name}"
    return full_name



def emoji_for(choice):
    return {"rock": "🪨", "paper": "📄", "scissors": "✂️"}[choice]


def get_rps_result(p1, p2):
    beats = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
    if p1 == p2:
        return 0
    elif beats[p1] == p2:
        return 1
    else:
        return 2


async def rps_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone with /rps <amount> to challenge them.")
        return

    try:
        bet = int(context.args[0])
        if bet <= 0:
            raise ValueError
    except:
        await update.message.reply_text("Usage: /rps <amount>")
        return

    challenger = update.effective_user
    opponent = update.message.reply_to_message.from_user

    if challenger.id == opponent.id:
        await update.message.reply_text("You can't challenge yourself.")
        return

    insufficient = []
    if get_primogems(challenger.id) < bet:
        insufficient.append(format_name(challenger))
    if get_primogems(opponent.id) < bet:
        insufficient.append(format_name(opponent))

    if insufficient:
        await update.message.reply_text(f"Not enough primogems for: {', '.join(insufficient)}.")
        return

    match_id = str(uuid.uuid4())
    rps_matches[match_id] = {
        "challenger": challenger,
        "opponent": opponent,
        "bet": bet,
        "choice1": None,
        "choice2": None,
        "chat_id": update.effective_chat.id,
        "msg_id": None,
    }

    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"rps_accept_{match_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rps_reject_{match_id}")
        ]
    ]

    msg = await update.message.reply_text(
        f"{format_name(opponent)}, you've been challenged by {format_name(challenger)} for {bet} primogems. Accept?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    rps_matches[match_id]["msg_id"] = msg.message_id
    rps_matches[match_id]["chat_id"] = msg.chat_id




from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def rps_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    try:
        match_id = query.data.split("_", 2)[2]
    except IndexError:
        await query.answer("Invalid match ID.", show_alert=True)
        return

    match = rps_matches.get(match_id)
    if not match:
        await query.edit_message_text("⚠️ Match expired or already accepted.")
        return

    challenger = match["challenger"]
    opponent = match["opponent"]
    bet = match["bet"]

    
    if user_id != opponent.id:
        await query.answer("Only the challenged user can accept this match.", show_alert=True)
        return

    insufficient = []
    if get_primogems(challenger.id) < bet:
        insufficient.append(format_name(challenger))
    if get_primogems(opponent.id) < bet:
        insufficient.append(format_name(opponent))

    if insufficient:
        await query.edit_message_text(f"❌ Not enough primogems for: {', '.join(insufficient)}.")
        del rps_matches[match_id]
        return

    # Deduct primogems
    update_balance(challenger.id,"Primogems", -bet)
    update_balance(opponent.id,"Primogems", -bet)

    # Set up RPS choice buttons
    caption = (
        f"🪨 Rock Paper Scissors 🎮\n\n"
        f"{format_name(challenger)}: ❓ yet to choose\n"
        f"{format_name(opponent)}: ❓ yet to choose"
    )
    buttons = [
        [
            InlineKeyboardButton("🪨 Rock", callback_data=f"rps_choice_{match_id}_rock"),
            InlineKeyboardButton("📄 Paper", callback_data=f"rps_choice_{match_id}_paper"),
            InlineKeyboardButton("✂️ Scissors", callback_data=f"rps_choice_{match_id}_scissors"),
        ]
    ]

  
    await query.edit_message_text(
        text=caption,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    match["msg_id"] = query.message.message_id
    match["chat_id"] = query.message.chat_id
    match["choice1"] = None
    match["choice2"] = None





async def rps_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data.split("_", 2)[2]
    match = rps_matches.pop(match_id, None)

    if match:
        await query.edit_message_text("Challenge rejected.")


async def rps_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    
    try:
        data = query.data[len("rps_choice_"):]  # remove prefix
        match_id, choice = data.rsplit("_", 1)
    except Exception:
        await query.answer("Invalid choice format.", show_alert=True)
        return

    match = rps_matches.get(match_id)
    if not match:
        await query.answer("Match expired or finished.", show_alert=True)
        return

    
    if user_id not in [match["challenger"].id, match["opponent"].id]:
        await query.answer("You're not part of this match.", show_alert=True)
        return

    
    if user_id == match["challenger"].id:
        if match["choice1"]:
            await query.answer("You already made your choice.", show_alert=True)
            return
        match["choice1"] = choice
    elif user_id == match["opponent"].id:
        if match["choice2"]:
            await query.answer("You already made your choice.", show_alert=True)
            return
        match["choice2"] = choice

    
    status1 = "✅ chosen" if match["choice1"] else "❓ yet to choose"
    status2 = "✅ chosen" if match["choice2"] else "❓ yet to choose"

    caption = (
        f"🪨 Rock Paper Scissors 🎮\n\n"
        f"{format_name(match['challenger'])}: {status1}\n"
        f"{format_name(match['opponent'])}: {status2}"
    )

    # Update status text
    buttons = [
        [
            InlineKeyboardButton("🪨 Rock", callback_data=f"rps_choice_{match_id}_rock"),
            InlineKeyboardButton("📄 Paper", callback_data=f"rps_choice_{match_id}_paper"),
            InlineKeyboardButton("✂️ Scissors", callback_data=f"rps_choice_{match_id}_scissors"),
        ]
    ]
    await context.bot.edit_message_text(
        chat_id=match["chat_id"],
        message_id=match["msg_id"],
        text=caption,
        reply_markup=InlineKeyboardMarkup(buttons)
)


    
    if match["choice1"] and match["choice2"]:
        p1 = match["choice1"]
        p2 = match["choice2"]
        bet = match["bet"]

        res = get_rps_result(p1, p2)

        if res == 0:
            try:
                bet = int(match["bet"])
                update_balance(match["challenger"].id,"Primogems", bet)
                update_balance(match["opponent"].id,"Primogems", bet)
                result = f"🤝 It's a tie! Both chose the same. Each refunded {bet} primos!"
            except Exception as e:
                result = "❌ Refund failed due to internal error."

                # Get readable names
                challenger_name = format_name(match["challenger"])
                opponent_name = format_name(match["opponent"])

                
                from config import BAKA_ID
                admin_id = BAKA_ID 
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        "⚠️ *RPS Refund Error*\n"
                        f"• Match ID: `{match_id}`\n"
                        f"• Challenger: {challenger_name}\n"
                        f"• Opponent: {opponent_name}\n"
                        f"• Bet: {match['bet']}\n"
                        f"• Error: `{e}`"
                    ),
                    parse_mode="Markdown"
                )

        elif res == 1:
            winner = match["challenger"]
            result = f"🏆 {format_name(winner)} wins +{int(bet) * 2} primos!"
            update_balance(winner.id,"Primogems", int(bet) * 2)
        else:
            winner = match["opponent"]
            result = f"🏆 {format_name(winner)} wins +{int(bet) * 2} primos!"
            update_balance(winner.id,"Primogems",int(bet) * 2)

        final_caption = (
            f"🪨 Rock Paper Scissors 🎮\n\n"
            f"{format_name(match['challenger'])}: {emoji_for(p1)}\n"
            f"{format_name(match['opponent'])}: {emoji_for(p2)}\n\n"
            f"{result}"
        )

        await context.bot.edit_message_text(
            chat_id=match["chat_id"],
            message_id=match["msg_id"],
            text=final_caption
        )

        del rps_matches[match_id]

import time
import random


user_last_explore = {}

# Genshin Impact-themed locations with emojis
explore_locations = [
    "Mondstadt Outskirts 🌬️",
    "Windrise 🌳",
    "Dawn Winery 🍷",
    "Stormterror's Lair 🐉",
    "Dragonspine ❄️",
    "Wolvendom 🐺",
    "Qingce Village 🏯",
    "Liyue Harbor ⚓",
    "Jueyun Karst ⛰️",
    "Wangshu Inn 🏮",
    "Huaguang Stone Forest 🔥",
    "Minlin Waterfall 💧",
    "Mt. Aocang 🌄",
    "Golden Apple Archipelago 🍎",
    "Inazuma City ⚡",
    "Kamisato Estate 🏯",
    "Narukami Island ⛩️",
    "Tatarasuna 🔥",
    "Yashiori Island 🌕",
    "Araumi Ruins 🏛️"
]
async def explore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name

    now = time.time()
    cooldown = 600  # 10 minutes cooldown
    last_time = user_last_explore.get(user_id, 0)

    if now - last_time < cooldown:
        remaining = cooldown - (now - last_time)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        await update.message.reply_text(
            f"⏳ {user_name}, please wait {minutes}m {seconds}s before exploring again!"
        )
        return

    primogems_amount = random.randint(10, 50)
    mora_amount = random.randint(100, 500)
    lunar_crystals_amount = random.randint(1, 3)
    location = random.choice(explore_locations)

    # Update user currencies
    update_balance(user_id,"Primogems", primogems_amount)
    update_balance(user_id, "Mora", mora_amount)
    update_balance(user_id, "Lunar Crystals", lunar_crystals_amount)

    user_last_explore[user_id] = now

    message = (
        f"🌟 {user_name} explored {location} and found:\n"
        f"💎 {primogems_amount} Primogems\n"
        f"🪙 {mora_amount} Mora\n"
        f"🌙 {lunar_crystals_amount} Lunar Crystals"
    )
    # Reply to the user
    await update.message.reply_text(message)

    # Notify admins about user exploration
    admin_message = (
        f"🔔 Exploration Alert!\n"
        f"User: {user_name} (ID: {user_id})\n"
        f"Location: {location}\n"
        f"Found:\n"
        f" - 💎 Primogems: {primogems_amount}\n"
        f" - 🪙 Mora: {mora_amount}\n"
        f" - 🌙 Lunar Crystals: {lunar_crystals_amount}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_message)
        except Exception as e:
            # Optionally log the error, e.g.:
            print(f"Failed to send admin message to {admin_id}: {e}")


def register_game_handlers(application):

    # === Mines Feature ===
    application.add_handler(CommandHandler("mines", start_mines))
    application.add_handler(CommandHandler("stopmine", stop_mine))
    application.add_handler(CommandHandler("primogems", primogems))
    application.add_handler(CommandHandler("daily", daily_primos))
    application.add_handler(CommandHandler("send", send_command))
    application.add_handler(CommandHandler("tran", view_transactions))
    application.add_handler(CommandHandler("add", add_primos_admin))
    application.add_handler(CallbackQueryHandler(handle_tile_click, pattern=r"^tile_\d+_\d+$"))
    application.add_handler(CallbackQueryHandler(handle_cashout, pattern=r"^cashout_\d+$"))
    application.add_handler(CommandHandler("explore", explore))  
    # === TicTacToe Feature ===
    application.add_handler(CommandHandler("tic", start_tictactoe))
    application.add_handler(CommandHandler("tc", cancel_tictactoe))
    application.add_handler(CallbackQueryHandler(tictactoe_accept_reject, pattern=r"^ttt_(accept|reject)_\d+"))
    application.add_handler(CallbackQueryHandler(tictactoe_move_handler, pattern=r"^ttmove_"))
    application.job_queue.run_repeating(check_tictactoe_timeouts, interval=120)

    # === Rock Paper Scissors (RPS) Feature ===
    application.add_handler(CommandHandler("rps", rps_command))
    application.add_handler(CallbackQueryHandler(rps_accept_callback, pattern=r"^rps_accept_"))
    application.add_handler(CallbackQueryHandler(rps_reject_callback, pattern=r"^rps_reject_"))
    application.add_handler(CallbackQueryHandler(rps_choice_callback, pattern=r"^rps_choice_"))
    application.add_handler(CommandHandler("dice", dice_game))
    application.add_handler(CommandHandler("list", list))
    print("✅ Mines, TicTacToe, RPS, and Backup handlers registered!")
