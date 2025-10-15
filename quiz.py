
import random
import sqlite3
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode, ChatType
from telegram.helpers import mention_html
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
import shutil
from telegram.ext import CommandHandler, MessageHandler, filters
from shop import get_balance, deduct_currency, add_currency

BOT_START_TIME = datetime.now(timezone.utc)
OWNER_ID = 5192424390  
RESET_LOG_CHAT_ID = -1002871188921 
APPROVED_CHAT_ID = -1002043895840 
# === DB INIT ===
def init_db():
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            options TEXT,
            answer TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            primogems INTEGER DEFAULT 0,
            mine_state TEXT
        )
    """)
    conn.commit()
    conn.close()
def init_clash_table():
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS clash_leaderboard (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            clashpoints INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    print("clash created")
# === CONSTANTS ===
ADD_Q_TEXT, ADD_Q_OPTIONS, ADD_Q_ANSWER = range(3)
AUTHORIZED_USERS = [5192424390]

# === UTILS ===
def get_random_question():
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1")
    question = c.fetchone()
    conn.close()
    return question

def get_primogems(user_id):
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("SELECT primogems FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def deduct_primogems(user_id, amount):
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, primogems, mine_state) VALUES (?, 0, NULL)", (user_id,))
    c.execute("UPDATE users SET primogems = primogems - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def update_score(user_id, username, points=1):
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO scores (user_id, username, points) VALUES (?, ?, 0)", (user_id, username))
    c.execute("UPDATE scores SET points = points + ?, username = ? WHERE user_id = ?", (points, username, user_id))
    conn.commit()
    conn.close()

def update_primogems(user_id, amount):
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, primogems, mine_state) VALUES (?, 0, NULL)", (user_id,))
    c.execute("UPDATE users SET primogems = primogems + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
def get_question(qid):
    conn=sqlite3.connect("/mnt/data/quiz.db")
    c=conn.cursor()
    c.execute("SELECT * FROM questions WHERE id=?", (qid,))
    qquestion=c.fetchone()
    conn.close()
    return qquestion
def update_clash_points(user_id, username):
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO clash_leaderboard (user_id, username, clashpoints) VALUES (?, ?, 0)", (user_id, username))
    c.execute("UPDATE clash_leaderboard SET clashpoints = clashpoints + 1, username = ? WHERE user_id = ?", (username, user_id))
    conn.commit()
    conn.close()
def get_clash_leaderboard():
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("SELECT user_id, username, clashpoints FROM clash_leaderboard ORDER BY clashpoints DESC LIMIT 10")
    leaderboard = c.fetchall()
    conn.close()
    return leaderboard

def get_leaderboard():
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("SELECT username, points FROM scores ORDER BY points DESC LIMIT 10")
    leaderboard = c.fetchall()
    conn.close()
    return leaderboard

import asyncio
import shutil
import os
QUIZ_DB_PATH = "/mnt/data/quiz.db"

awaiting_db_restore = {}  # user_id: True/False

async def clear_db_flag_later(user_id, delay=120):
    await asyncio.sleep(delay)
    awaiting_db_restore.pop(user_id, None)

async def backup_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("❌ You're not authorized.")
        return

    try:
        # Open and send the live DB as-is
        with open(QUIZ_DB_PATH, "rb") as f:
            await update.message.reply_document(
                document=InputFile(f, filename="quiz_backup.db"),
                caption="📦 Here is your DB backup.\n📥 Now upload your `.db` within 2 minutes to restore."
            )
        awaiting_db_restore[user_id] = True
        asyncio.create_task(clear_db_flag_later(user_id))
    except FileNotFoundError:
        await update.message.reply_text("❌ quiz.db not found.")

async def handle_uploaded_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        return

    if not awaiting_db_restore.get(user_id):
        return  # Not expecting upload

    document = update.message.document
    if not document or not document.file_name.endswith(".db"):
        return

    try:
        tg_file = await document.get_file()
        await tg_file.download_to_drive("quiz_upload.db")
        await update.message.reply_text("📥 File saved as `quiz_upload.db`. Use /restoredb to load it.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to upload DB: {e}")

    awaiting_db_restore.pop(user_id, None)

async def restore_uploaded_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("❌ You’re not authorized.")
        return

    # 1️⃣ Must be a reply to a document
    if not update.message.reply_to_message:
        await update.message.reply_text("ℹ️ Reply to the uploaded `.db` file with /restoredb.")
        return

    doc_msg = update.message.reply_to_message

    # 2️⃣ The reply must be a .db file
    if not doc_msg.document or not doc_msg.document.file_name.endswith(".db"):
        await update.message.reply_text("❌ That’s not a .db file.")
        return

    try:
        # 3️⃣ Download the uploaded file
        file = await doc_msg.document.get_file()
        await file.download_to_drive("quiz_upload.db")
    except Exception as e:
        await update.message.reply_text(f"❌ Download failed: {e}")
        return

    try:
        # 4️⃣ Copy into real path (overwrite if exists, create if not)
        os.makedirs(os.path.dirname(QUIZ_DB_PATH) or ".", exist_ok=True)
        shutil.copyfile("quiz_upload.db", QUIZ_DB_PATH)
        await update.message.reply_text("✅ quiz.db restored successfully! (new file created if none existed)")
    except Exception as e:
        await update.message.reply_text(f"❌ Restore failed: {e}")
        return

    # ✅ Clear restore flag
    awaiting_db_restore.pop(user_id, None)



# === QUIZ ===
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, ignore_auth=False):
    if not ignore_auth and update.effective_user.id not in AUTHORIZED_USERS:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🚫 You are not authorized to start the quiz.")
        return

    question = get_random_question()
    if not question:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No questions available.")
        return

    q_id, text, options_str, answer = question
    options = options_str.split("|")
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"quiz:{q_id}:{opt}")] for opt in options]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❓ {text}", reply_markup=reply_markup)

async def answer_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, q_id, selected = query.data.split(":")
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("SELECT answer FROM questions WHERE id=?", (q_id,))
    correct_answer = c.fetchone()[0]
    conn.close()

    user = query.from_user
    mention = mention_html(user.id, user.full_name)
    username = user.username or f"id_{user.id}"

    if selected == correct_answer:
        update_score(user.id, username)
        update_primogems(user.id, 200)  # Add 200 primogems
        add_currency(user.id, "lunar_crystals", 10)  # Add 10 lunar crystals
        await query.edit_message_text(
            text=f"✅ {mention}, Correct! You've been awarded 1 point, 200 primogems, and 10 lunar crystals.",
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            text=f"❌ {mention}, Wrong! Better luck next time.",
            parse_mode="HTML"
        )

# === LEADERBOARD ===
import os

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    leaderboard = get_leaderboard()
    if not leaderboard:
        await update.message.reply_text("No scores yet!")
        return

    image_path = os.path.join(os.path.dirname(__file__), "images", "Quizimage.jpg")

    message = ""
    for i, (username, points) in enumerate(leaderboard, 1):
        mention = f"<a href='https://t.me/{username}'>{username}</a>"
        message += f"<b>{i}.</b> {mention} — <i>{points} points</i>\n"

    caption = f"<b>🏆 Quiz Leaderboard</b>\n\n{message}"

    try:
        with open(image_path, "rb") as photo:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo,
                caption=caption,
                parse_mode=ParseMode.HTML
            )
    except FileNotFoundError:
        await update.message.reply_text("❌ Couldn't find the image file for the leaderboard.")

from telegram.constants import ParseMode
import os


async def clashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    leaderboard = get_clash_leaderboard()
    if not leaderboard:
        await update.message.reply_text("🏳️ No one has clashed yet!")
        return

    image_url = "https://i.postimg.cc/yd5LjQ15/clash.jpg"

    message = "<b>🏆 Clash Leaderboard</b>\n\n"
    for i, (user_id, username, points) in enumerate(leaderboard, 1):
        mention = f"<a href='tg://user?id={user_id}'>{username}</a>"
        message += f"<b>{i}.</b> {mention} — <i>{points} clash points</i>\n"

  
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=image_url,
            caption=message,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
      
        await update.message.reply_text(
            "⚠️ Failed to load leaderboard image, but here's the leaderboard:\n\n" + message,
            parse_mode=ParseMode.HTML
        )

        print(f"❌ Failed to send leaderboard image: {e}")

# === ADD QUESTION ===
async def add_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in AUTHORIZED_USERS:
        await update.message.reply_text("You're not authorized to add questions.")
        return ConversationHandler.END
    await update.message.reply_text("📝 Send the question text:")
    return ADD_Q_TEXT

async def add_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"] = update.message.text
    await update.message.reply_text("✍️ Now send 4 options separated by '|', e.g. A|B|C|D")
    return ADD_Q_OPTIONS

async def add_question_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_options"] = update.message.text
    await update.message.reply_text("✅ Now send the correct answer (must match one of the options):")
    return ADD_Q_ANSWER

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

async def add_question_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = context.user_data.get("new_question")
    options_str = context.user_data.get("new_options")
    answer = update.message.text.strip()

    options = [opt.strip() for opt in options_str.split("|")]
    if len(options) != 4 or answer not in options:
        await update.message.reply_text("⚠️ Invalid input. Make sure there are 4 options and the answer matches one.")
        return ConversationHandler.END

    context.user_data["new_answer"] = answer

    preview = (
        f"📝 *Preview Your Question:*\n\n"
        f"❓ *Question*: {question}\n"
        f"🔢 *Options*: {options_str}\n"
        f"✅ *Answer*: {answer}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm_add"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel_add")]
    ])

    await update.message.reply_text(preview, reply_markup=keyboard, parse_mode="Markdown")
    return ConversationHandler.END
import sqlite3

async def confirm_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_add":
        question = context.user_data.get("new_question")
        options_str = context.user_data.get("new_options")
        answer = context.user_data.get("new_answer")

        conn = sqlite3.connect("/mnt/data/quiz.db")
        c = conn.cursor()
        c.execute("INSERT INTO questions (question, options, answer) VALUES (?, ?, ?)",
                  (question, options_str, answer))
        conn.commit()
        conn.close()

        await query.edit_message_text("✅ Question saved to database!")

    elif query.data == "cancel_add":
        await query.edit_message_text("❌ Question discarded.")

    # Clear memory
    for key in ["new_question", "new_options", "new_answer"]:
        context.user_data.pop(key, None)


async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Question creation cancelled.")
    return ConversationHandler.END

async def questions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to view the questions.")
        return

    conn = sqlite3.connect("/mnt/data/quiz.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, question, options, answer FROM questions")
    all_questions = cursor.fetchall()
    conn.close()

    if not all_questions:
        await update.message.reply_text("❌ No questions found in the database.")
        return

    message_chunk = ""
    for q in all_questions:
        q_id, question, options, answer = q

        if not options:  
            continue

        options_list = options.split("|")
        formatted_options = "\n".join([f"{chr(65+i)}. {opt.strip()}" for i, opt in enumerate(options_list)])
        entry = (
            f"🆔 *ID:* {q_id}\n"
            f"❓ *Q:* {question}\n"
            f"{formatted_options}\n"
            f"✅ *Answer:* {answer}\n\n"
        )

        if len(message_chunk) + len(entry) > 4000:
            await update.message.reply_text(message_chunk, parse_mode="Markdown")
            message_chunk = ""

        message_chunk += entry

    if message_chunk:
        await update.message.reply_text(message_chunk, parse_mode="Markdown")


# === AUTO QUIZ ===
AUTO_MIN = 25
AUTO_MAX = 50
msg_counter = 0
current_threshold = AUTO_MAX

async def set_intervals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_MIN, AUTO_MAX, current_threshold
    if update.effective_user.id not in AUTHORIZED_USERS:
        await update.message.reply_text("⛔ You're not authorized to set intervals.")
        return
    try:
        AUTO_MIN, AUTO_MAX = map(int, context.args)
        current_threshold = AUTO_MAX
        await update.message.reply_text(f"✅ Auto quiz interval set to {AUTO_MIN}-{AUTO_MAX} messages.")
    except:
        await update.message.reply_text("⚠️ Usage: /setintervals 25 50")

async def message_tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global msg_counter, current_threshold

    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    if not hasattr(update.message, "date") or update.message.date < (BOT_START_TIME - timedelta(seconds=10)):
        return

    msg_counter += 1

    if msg_counter >= current_threshold:
        msg_counter = 0
        current_threshold = AUTO_MAX

        if update.effective_chat.id == APPROVED_CHAT_ID:
            # ✅ This is the approved group — start quiz
            await context.bot.send_message(
                chat_id=APPROVED_CHAT_ID,
                text="📢 Quiz time! Get ready 🎉"
            )
            await start_quiz(update, context, ignore_auth=True)
        else:
            # ❌ Not approved group — send warning
            text = (
                "❌ This chat is not approved to receive automatic quizzes.\n\n"
            )
            await update.message.reply_text(text, disable_web_page_preview=True)

async def lore_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to challenge them.")
        return
    
    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("Usage: /lore <amount> (must be a positive number)")
        return

    p1 = update.effective_user
    p2 = update.message.reply_to_message.from_user

    if p1.id == p2.id:
        await update.message.reply_text("You can't challenge yourself!")
        return

    context.chat_data["lore_bet"] = {
        "p1": p1.id,
        "p2": p2.id,
        "amount": amount,
        "p1_name": p1.first_name,  
        "p2_name": p2.first_name   
    }

    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"lore_accept_{p1.id}_{p2.id}_{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data="lore_reject")
        ]
    ]
    await update.message.reply_text(
        f"{p2.first_name}, you've been challenged by {p1.first_name} for 💠 {amount} primogems in a lore quiz!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def lore_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")

    p1 = int(data[2])
    p2 = int(data[3])
    amount = int(data[4])

    if query.from_user.id != p2:
        await query.answer("You're not the challenged player.", show_alert=True)
        return

    # Check both have enough primogems
    for uid in [p1, p2]:
        if get_primogems(uid) < amount:
            await query.message.edit_text("❌ One of the players doesn't have enough primogems.")
            return

    # Deduct both
    update_primogems(p1, -amount)
    update_primogems(p2, -amount)

    # Fetch a random question
    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("SELECT question, options, answer FROM questions ORDER BY RANDOM() LIMIT 1")
    row = c.fetchone()
    conn.close()

    question, opt_str, answer = row
    options = [opt.strip() for opt in opt_str.split("|")]

    # Get player names from the bet data
    bet_data = context.chat_data.get("lore_bet", {})
    
    context.chat_data["lore_game"] = {
        "players": [p1, p2],
        "answers": {},
        "correct": answer.strip().upper(),
        "question": question,
        "options": options,
        "bet": amount,
        "player_names": {
            p1: bet_data.get("p1_name", "Player 1"),
            p2: bet_data.get("p2_name", "Player 2")
        }
    }

    keyboard = [[InlineKeyboardButton(opt, callback_data=f"loreq_{i}")] for i, opt in enumerate(options)]
    await query.message.edit_text(
        f"🧠 Lore Quiz Battle:\n\n❓ {question}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def lore_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data.split("_")
    selected_idx = int(data[1])
    game = context.chat_data.get("lore_game", {})
    players = game.get("players", [])
    
    if uid not in players:
        await query.answer("You're not in this quiz!", show_alert=True)
        return
    
    if uid in game["answers"]:
        await query.answer("You've already answered.")
        return
    
    selected_option = game["options"][selected_idx].upper()
    game["answers"][uid] = selected_option
    context.chat_data["lore_game"] = game  # Update in case
    
    await query.answer("✅ Answer locked.")
    
    if len(game["answers"]) < 2:
        return  # Wait for other player
    
    # Both answered, determine result
    p1, p2 = players
    a1 = game["answers"][p1]
    a2 = game["answers"][p2]
    correct = game["correct"]
    amount = game["bet"]
    
    # Get player names from stored data
    player_names = game.get("player_names", {})
    
    if a1 == correct and a2 != correct:
        update_primogems(p1, int(amount * 2))
        winner_name = player_names.get(p1, f"Player {p1}")
        result = f"🏆 {winner_name} wins 💠 {int(amount * 2)}!"
    elif a2 == correct and a1 != correct:
        update_primogems(p2, int(amount * 2))
        winner_name = player_names.get(p2, f"Player {p2}")
        result = f"🏆 {winner_name} wins 💠 {int(amount * 2)}!"
    elif a1 == correct and a2 == correct:
        update_primogems(p1, amount)
        update_primogems(p2, amount)
        result = "🤝 Both answered correctly. Bet refunded!"
    else:
        update_primogems(p1, int(amount * 0.5))
        update_primogems(p2, int(amount * 0.5))
        result = "❌ Both failed. Half Primogems refunded!"
    
    await query.message.edit_text(
        f"🧠 Lore Quiz Complete!\n\n"
        f"{result}"
    )
    
    # Clean up
    context.chat_data.pop("lore_game", None)
    context.chat_data.pop("lore_bet", None)


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

ELEMENTS = ["Anemo", "Geo", "Electro", "Dendro", "Hydro", "Pyro"]
ELEMENT_ICONS = {
    "Anemo": "🌪️", "Geo": "🪨", "Electro": "⚡", 
    "Dendro": "🌿", "Hydro": "💧", "Pyro": "🔥"
}

async def clash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ *Reply to someone to challenge them!*\nUsage: `/clash <bet>`", parse_mode="Markdown")
        return
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❌ *Usage:* `/clash <bet>`", parse_mode="Markdown")
        return

    bet = int(context.args[0])
    user_id = update.effective_user.id
    opp_id = update.message.reply_to_message.from_user.id
    balance1 = get_primogems(user_id)
    balance2 = get_primogems(opp_id)

    if balance1 < bet:
        await update.message.reply_text("💸 You don't have enough primogems.")
        return
    if balance2 < bet:
        await update.message.reply_text("💸 Opponent doesn't have enough primogems.")
        return

    context.chat_data[f"clash_bet_{user_id}_{opp_id}"] = bet
    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"cla_Accept_{user_id}_{opp_id}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"cla_Decline_{user_id}_{opp_id}")
        ]
    ]
    await update.message.reply_text(
        f"🔥 *{update.effective_user.first_name}* has challenged *{update.message.reply_to_message.from_user.first_name}* to a duel!\n\n"
        f"💰 *Bet:* {bet} primogems\n\n"
        f"Do you accept the challenge?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def clash_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split("_")
    choice, p1, p2 = data[1], int(data[2]), int(data[3])

    if user_id != p2:
        await query.answer("❌ This challenge is not for you!", show_alert=True)
        return

    if choice == "Accept":
        context.chat_data["p1"] = p1
        context.chat_data["p2"] = p2
        keyboard = [
            [
                InlineKeyboardButton(f"{ELEMENT_ICONS[e]} {e}", callback_data=f"cla_{e}_{p1}_{p2}")
                for e in ELEMENTS[:3]
            ],
            [
                InlineKeyboardButton(f"{ELEMENT_ICONS[e]} {e}", callback_data=f"cla_{e}_{p1}_{p2}")
                for e in ELEMENTS[3:]
            ]
        ]
        await query.edit_message_text(
            "🎮 *Elemental Clash Started!*\n\n"
            "🌟 Both players, please select your elements below:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif choice == "Decline":
        await query.edit_message_text("❌ The opponent declined the clash.")

async def accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split("_")
    selected = data[1]
    p1 = int(data[2])
    p2 = int(data[3])

    if user_id not in [p1, p2]:
        await query.answer("⚠️ You're not part of this battle!", show_alert=True)
        return

    context.chat_data[f"clash_{user_id}"] = selected
    bet_key = f"clash_bet_{p1}_{p2}"
    bet = context.chat_data.get(bet_key)

    if f"clash_{p1}" in context.chat_data and f"clash_{p2}" in context.chat_data and bet is not None:
        cp1 = context.chat_data[f"clash_{p1}"]
        cp2 = context.chat_data[f"clash_{p2}"]
        outcome = result(cp1, cp2)

        user1 = await context.bot.get_chat(p1)
        user2 = await context.bot.get_chat(p2)
        name1 = user1.username or user1.first_name
        name2 = user2.username or user2.first_name

        if outcome == "🏆 You won!":
            update_primogems(p1, bet)
            deduct_primogems(p2, bet)
            update_clash_points(p1, name1)
            result_text = f"🏆 *{name1}* wins and earns *{bet} primogems*!"
        elif outcome == "💀 Opponent wins!":
            update_primogems(p2, bet)
            deduct_primogems(p1, bet)
            update_clash_points(p2, name2)
            result_text = f"🏆 *{name2}* wins and earns *{bet} primogems*!"
        else:
            result_text = f"⚖️ It's a draw between *{name1}* and *{name2}*. No primogems lost."

        final_msg = (
            f"🎊 *Elemental Clash Result*\n\n"
            f"👤 {name1} chose {ELEMENT_ICONS.get(cp1, '')} *{cp1}*\n"
            f"👤 {name2} chose {ELEMENT_ICONS.get(cp2, '')} *{cp2}*\n\n"
            f"{result_text}"
        )

        await query.edit_message_text(final_msg, parse_mode="Markdown")

        # Cleanup
        context.chat_data.pop(f"clash_{p1}", None)
        context.chat_data.pop(f"clash_{p2}", None)
        context.chat_data.pop(f"clash_bet_{p1}_{p2}", None)
    else:
        await query.answer("✅ Element saved. Waiting for the other player...", show_alert=False)

def result(choice1, choice2):
    rules = {
        "Anemo": "Pyro", "Electro": "Hydro", "Hydro": "Pyro",
        "Geo": "Electro", "Dendro": "Geo", "Pyro": "Dendro"
    }
    if choice1 == choice2:
        return "⚖️ It's a draw!"
    elif rules.get(choice1) == choice2:
        return "🏆 You won!"
    elif rules.get(choice2) == choice1:
        return "💀 Opponent wins!"
    else:
        return "❓ Unknown result."

REWARDS = [1600, 1000, 500]

async def reset_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    conn = sqlite3.connect("/mnt/data/quiz.db")
    c = conn.cursor()
    c.execute("SELECT user_id, username, points FROM scores ORDER BY points DESC LIMIT 10")
    leaderboard = c.fetchall()

    if not leaderboard:
        await update.message.reply_text("❌ No leaderboard data found.")
        conn.close()
        return

    result_msg = "🏆 <b>Leaderboard Reset & Rewards</b>\n\n"
    log_msg = "🧾 <b>Quiz Reset Log</b>\n\nTop 3 users rewarded:\n"

    
    for i, (user_id, username, points) in enumerate(leaderboard[:3]):
        reward = REWARDS[i]
        c.execute("UPDATE users SET primogems = primogems + ? WHERE user_id = ?", (reward, user_id))

        mention = f"<a href='https://t.me/{username}'>{username}</a>" if username else f"<code>{user_id}</code>"
        result_msg += f"{i+1}. {mention} — +<b>{reward}</b> primogems\n"
        log_msg += f"{i+1}. {username or user_id} ({points} pts) ➜ +{reward} primogems\n"

    
    c.execute("DELETE FROM scores")
    conn.commit()
    conn.close()

    result_msg += "\n🎉 A new quiz season has now begun!"
    await update.message.reply_text(result_msg, parse_mode=ParseMode.HTML)

    
    try:
        await context.bot.send_message(
            chat_id=RESET_LOG_CHAT_ID,
            text=log_msg,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Couldn't send log: {e}")
# === EXPORT HANDLER LIST ===
def register_quiz_handlers(application):
    # === Quiz Core Commands ===
    init_clash_table()
    application.add_handler(CommandHandler("quiz", start_quiz))
    application.add_handler(CallbackQueryHandler(answer_quiz, pattern=r"^quiz:"))
    application.add_handler(CommandHandler("leaderboard", show_leaderboard))
    application.add_handler(CommandHandler("setintervals", set_intervals))

    # === Quiz Add Question Flow ===
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("addquestion", add_question_start)],
        states={
            ADD_Q_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_text)],
            ADD_Q_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_options)],
            ADD_Q_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_answer)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add)],
    ))

    # === Quiz Message Tracker ===
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_tracker))

    # === Backup & Restore for quiz.db ===
    application.add_handler(CommandHandler("backupdb", backup_db))
    application.add_handler(CommandHandler("restoredb", restore_uploaded_db))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_uploaded_file))
    application.add_handler(CallbackQueryHandler(confirm_add_callback, pattern="^confirm_add|cancel_add$"))
    application.add_handler(CommandHandler("questions", questions_command))
    application.add_handler(CommandHandler("lore", lore_start))  
    application.add_handler(CallbackQueryHandler(lore_accept_callback, pattern=r"^lore_accept_"))  
    application.add_handler(CallbackQueryHandler(lambda u,c: u.callback_query.message.edit_text("❌ Challenge rejected."), pattern="^lore_reject$")) 
    application.add_handler(CallbackQueryHandler(lore_answer_callback, pattern=r"^loreq_\d+"))  
    application.add_handler(CommandHandler("clash", clash))
    application.add_handler(CallbackQueryHandler(clash_callback, pattern=r"^cla_(Accept|Decline)_[0-9]+_[0-9]+$"))
    application.add_handler(CallbackQueryHandler(accept_callback, pattern=r"^cla_(Anemo|Geo|Electro|Dendro|Hydro|Pyro)_[0-9]+_[0-9]+$"))
    application.add_handler(CommandHandler("resetquiz", reset_quiz_command))
    application.add_handler(CommandHandler("clashboard", clashboard))

    print("🧠 Quiz handlers and DB backup integrated successfully!")
