# --- Updated quiz handlers using MongoDB ---
import random
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatType
from telegram.helpers import mention_html
from telegram.ext import (
    CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)
import os, shutil, asyncio

# your existing db module (assumes you pasted helper funcs above into db.py)
from db import (
    get_random_question, insert_question_doc, get_all_questions, delete_question_by_id,
    update_score_db, get_leaderboard_db, reset_scores_and_reward_top,
    get_clash_leaderboard_db, update_clash_points_db,
    get_primogems, update_primos, update_balance,get_question_by_id
)
from db import is_authorized, get_authorized_users

AUTHORIZED_USERS = [5192424390]

# constants you already had
BOT_START_TIME = datetime.now(timezone.utc)
OWNER_ID = 5192424390
RESET_LOG_CHAT_ID = -1002871188921
APPROVED_CHAT_ID = -1002120721604

# conversation states you used earlier
ADD_Q_TEXT = 1
ADD_Q_OPTIONS = 2
ADD_Q_ANSWER = 3

# --- QUIZ START ---
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, ignore_auth=False):

    if not ignore_auth:
        if not is_authorized(update.effective_user.id):
            await update.message.reply_text("🚫 You are not authorized to start quizzes.")
            return

    q = get_random_question()
    if not q:
        await update.message.reply_text("❌ No questions in database.")
        return

    q_id, text, options_str, answer = q
    options = [opt.strip() for opt in options_str.split("|")]

    keyboard = [
        [InlineKeyboardButton(opt, callback_data=f"quiz:{q_id}:{opt}")]
        for opt in options
    ]

    await update.message.reply_text(
        f"❓ {text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# --- ANSWER HANDLER ---
async def answer_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, qid, selected = query.data.split(":")

    qdoc = get_question_by_id(qid)
    if not qdoc:
        await query.edit_message_text("❌ Question not found.")
        return

    correct = qdoc["answer"]
    user = query.from_user

    if selected == correct:
        update_score_db(user.id, user.username or f"id_{user.id}", 1)
        update_primos(user.id, 200)
        update_balance(user.id, "Lunar Crystals", 10)

        await query.edit_message_text(
            f"✅ Correct!\n+1 point\n+200 primogems\n+10 lunar crystals",
            parse_mode="HTML"
        )

    else:
        await query.edit_message_text("❌ Wrong.")


# --- LEADERBOARD ---
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lb = get_leaderboard_db()
    if not lb:
        await update.message.reply_text("No scores yet!")
        return

    image_path = os.path.join(os.path.dirname(__file__), "images", "Quizimage.jpg")
    message = ""
    for i, (username, points, uid) in enumerate(lb, 1):
        mention = f"<a href='https://t.me/{username}'>{username}</a>" if not username.startswith("id_") else f"<code>{uid}</code>"
        message += f"<b>{i}.</b> {mention} — <i>{points} points</i>\n"

    caption = f"<b>🏆 Quiz Leaderboard</b>\n\n{message}"
    try:
        with open(image_path, "rb") as photo:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo, caption=caption, parse_mode=ParseMode.HTML)
    except FileNotFoundError:
        await update.message.reply_text(caption, parse_mode=ParseMode.HTML)

# --- CLASH BOARD (uses quiz_clash collection) ---
async def clashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    leaderboard = get_clash_leaderboard_db()
    if not leaderboard:
        await update.message.reply_text("🏳️ No one has clashed yet!")
        return

    image_url = "https://i.postimg.cc/yd5LjQ15/clash.jpg"
    message = "<b>🏆 Clash Leaderboard</b>\n\n"
    for i, (user_id, username, points) in enumerate(leaderboard, 1):
        mention = f"<a href='tg://user?id={user_id}'>{username}</a>"
        message += f"<b>{i}.</b> {mention} — <i>{points} clash points</i>\n"

    try:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_url, caption=message, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text("⚠️ Failed to load leaderboard image, but here's the leaderboard:\n\n" + message, parse_mode=ParseMode.HTML)
        print(f"❌ Failed to send leaderboard image: {e}")

# --- ADD QUESTION flow ---
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

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Confirm", callback_data="confirm_add"),
                                     InlineKeyboardButton("❌ Cancel", callback_data="cancel_add")]])
    await update.message.reply_text(preview, reply_markup=keyboard, parse_mode="Markdown")
    return

async def confirm_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_add":
        question = context.user_data.get("new_question")
        options_str = context.user_data.get("new_options")
        answer = context.user_data.get("new_answer")
        insert_question_doc(question, options_str, answer)
        await query.edit_message_text("✅ Question saved to database!")
    else:
        await query.edit_message_text("❌ Question discarded.")
    for key in ["new_question", "new_options", "new_answer"]:
        context.user_data.pop(key, None)

async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Question creation cancelled.")
    return ConversationHandler.END

async def questions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Not authorized.")
        return
    #To fix bc pata nhai kya uva h kal dekhte 
    # docs = list(quiz_questions.find())
    docs=0
    if not docs:
        await update.message.reply_text("No questions stored.")
        return

    msg = ""

    for q in docs:
        opts = q["options"].split("|")
        formatted = "\n".join([f"• {opt}" for opt in opts])

        block = (
            f"🆔 {q['_id']}\n"
            f"❓ {q['question']}\n"
            f"{formatted}\n"
            f"✅ {q['answer']}\n\n"
        )

        if len(msg) + len(block) > 3800:
            await update.message.reply_text(msg)
            msg = ""

        msg += block

    if msg:
        await update.message.reply_text(msg)

# --- AUTO QUIZ (unchanged logic) ---
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
            await context.bot.send_message(chat_id=APPROVED_CHAT_ID, text="📢 Quiz time! Get ready 🎉")
            await start_quiz(update, context, ignore_auth=True)
        else:
            text = "❌ This chat is not approved to receive automatic quizzes.\n\n"
            await update.message.reply_text(text, disable_web_page_preview=True)
from bson import ObjectId

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

    # Check both have primos
    for uid in [p1, p2]:
        if get_primogems(uid) < amount:
            await query.message.edit_text("❌ One of the players doesn't have enough primogems.")
            return

    update_primos(p1, -amount)
    update_primos(p2, -amount)

    qid, question, opt_str, answer = get_random_question()
    options = [opt.strip() for opt in opt_str.split("|")]

    bet_data = context.chat_data.get("lore_bet", {})

    context.chat_data["lore_game"] = {
        "players": [p1, p2],
        "answers": {},
        "correct": answer.strip(),
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

    selected_opt = game["options"][selected_idx]
    game["answers"][uid] = selected_opt
    context.chat_data["lore_game"] = game

    await query.answer("✅ Answer locked.")

    if len(game["answers"]) < 2:
        return

    p1, p2 = players
    a1 = game["answers"][p1]
    a2 = game["answers"][p2]
    correct = game["correct"]
    bet = game["bet"]

    names = game["player_names"]

    if a1 == correct and a2 != correct:
        update_primos(p1, bet * 2)
        text = f"🏆 {names[p1]} wins and earns 💠 {bet*2}!"

    elif a2 == correct and a1 != correct:
        update_primos(p2, bet * 2)
        text = f"🏆 {names[p2]} wins and earns 💠 {bet*2}!"

    elif a1 == correct and a2 == correct:
        update_primos(p1, bet)
        update_primos(p2, bet)
        text = "🤝 Both answered correctly! Bet refunded."

    else:
        update_primos(p1, bet // 2)
        update_primos(p2, bet // 2)
        text = "❌ Both failed! Half refunded."

    await query.message.edit_text(
        f"🧠 Lore Quiz Complete!\n\n{text}"
    )

    context.chat_data.pop("lore_game", None)
    context.chat_data.pop("lore_bet", None)
ELEMENTS = ["Anemo", "Geo", "Electro", "Dendro", "Hydro", "Pyro"]
ELEMENT_ICONS = {
    "Anemo": "🌪️", "Geo": "🪨", "Electro": "⚡",
    "Dendro": "🌿", "Hydro": "💧", "Pyro": "🔥"
}

async def clash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Reply to someone.\nUsage: /clash <bet>")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❌ Usage: /clash <bet>")
        return

    bet = int(context.args[0])
    p1 = update.effective_user.id
    p2 = update.message.reply_to_message.from_user.id

    if get_primogems(p1) < bet:
        await update.message.reply_text("❌ You don't have enough primogems.")
        return
    if get_primogems(p2) < bet:
        await update.message.reply_text("❌ Opponent doesn't have enough primogems.")
        return

    context.chat_data[f"clash_bet_{p1}_{p2}"] = bet

    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"cla_Accept_{p1}_{p2}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"cla_Decline_{p1}_{p2}")
        ]
    ]

    await update.message.reply_text(
        f"🔥 Clash Challenge!\n\n"
        f"{update.effective_user.first_name} challenged {update.message.reply_to_message.from_user.first_name}\n"
        f"💠 Bet: {bet}\n\nAccept?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
async def clash_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")

    action, p1, p2 = data[1], int(data[2]), int(data[3])
    uid = query.from_user.id

    if uid != p2:
        await query.answer("Not your challenge.", show_alert=True)
        return

    if action == "Decline":
        await query.edit_message_text("❌ Opponent declined the clash.")
        return

    # Show element choices
    keyboard = [
        [InlineKeyboardButton(f"{ELEMENT_ICONS[e]} {e}", callback_data=f"choose_{e}_{p1}_{p2}")]
        for e in ELEMENTS
    ]

    await query.edit_message_text(
        "🎮 Elemental Clash Started!\nPick your element:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
async def accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")

    element = data[1]
    p1 = int(data[2])
    p2 = int(data[3])

    uid = query.from_user.id

    if uid not in [p1, p2]:
        await query.answer("Not your battle.", show_alert=True)
        return

    context.chat_data[f"clash_pick_{uid}"] = element
    bet = context.chat_data.get(f"clash_bet_{p1}_{p2}")

    # wait for both players
    if f"clash_pick_{p1}" not in context.chat_data or f"clash_pick_{p2}" not in context.chat_data:
        await query.answer("Element locked. Waiting for other player.")
        return

    e1 = context.chat_data[f"clash_pick_{p1}"]
    e2 = context.chat_data[f"clash_pick_{p2}"]

    winner = clash_result(e1, e2)

    user1 = await context.bot.get_chat(p1)
    user2 = await context.bot.get_chat(p2)
    name1 = user1.first_name
    name2 = user2.first_name

    if winner == 1:
        update_primos(p1, bet)
        update_primos(p2, -bet)
        update_clash_points_db(p1, name1, 1)
        result = f"🏆 {name1} wins +{bet}!"
    elif winner == 2:
        update_primos(p2, bet)
        update_primos(p1, -bet)
        update_clash_points_db(p2, name2, 1)

async def accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")

    element = data[1]
    p1 = int(data[2])
    p2 = int(data[3])

    uid = query.from_user.id

    if uid not in [p1, p2]:
        await query.answer("Not your battle.", show_alert=True)
        return

    context.chat_data[f"clash_pick_{uid}"] = element
    bet = context.chat_data.get(f"clash_bet_{p1}_{p2}")

    # wait for both players
    if f"clash_pick_{p1}" not in context.chat_data or f"clash_pick_{p2}" not in context.chat_data:
        await query.answer("Element locked. Waiting for other player.")
        return

    e1 = context.chat_data[f"clash_pick_{p1}"]
    e2 = context.chat_data[f"clash_pick_{p2}"]

    winner = clash_result(e1, e2)

    user1 = await context.bot.get_chat(p1)
    user2 = await context.bot.get_chat(p2)
    name1 = user1.first_name
    name2 = user2.first_name

    if winner == 1:
        update_primos(p1, bet)
        update_primos(p2, -bet)
        update_clash_points_db(p1, name1, 1)
        result = f"🏆 {name1} wins +{bet}!"
    elif winner == 2:
        update_primos(p2, bet)
        update_primos(p1, -bet)
        update_clash_points_db(p2, name2, 1)
        result = f"🏆 {name2} wins +{bet}!"
    else:
        result = "⚖️ Draw! No primogems lost."

    final_msg = (
        f"🎊 Elemental Clash Result\n\n"
        f"{name1} chose {ELEMENT_ICONS[e1]} *{e1}*\n"
        f"{name2} chose {ELEMENT_ICONS[e2]} *{e2}*\n\n"
        f"{result}"
    )

    await query.edit_message_text(final_msg, parse_mode="Markdown")

    # clean up
    context.chat_data.pop(f"clash_pick_{p1}", None)
    context.chat_data.pop(f"clash_pick_{p2}", None)
    context.chat_data.pop(f"clash_bet_{p1}_{p2}", None)
def clash_result(c1, c2):
    rules = {
        "Anemo": "Pyro",
        "Electro": "Hydro",
        "Hydro": "Pyro",
        "Geo": "Electro",
        "Dendro": "Geo",
        "Pyro": "Dendro"
    }
    if c1 == c2:
        return 0  # draw
    if rules.get(c1) == c2:
        return 1  # p1 wins
    if rules.get(c2) == c1:
        return 2  # p2 wins
    return 0



# --- RESET QUIZ command (rewards top users) ---
REWARDS = [1600, 1000, 500]

async def reset_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    # find top 10 before wiping
    top = get_leaderboard_db(limit=10)
    if not top:
        await update.message.reply_text("❌ No leaderboard data found.")
        return

    # Reward top 3
    rewarded = reset_scores_and_reward_top(rewards=REWARDS)
    result_msg = "🏆 <b>Leaderboard Reset & Rewards</b>\n\n"
    log_msg = "🧾 <b>Quiz Reset Log</b>\n\nTop rewarded:\n"
    for i, (username, points, uid) in enumerate(top[:3]):
        reward = REWARDS[i]
        mention = f"<a href='https://t.me/{username}'>{username}</a>" if not username.startswith("id_") else f"<code>{uid}</code>"
        result_msg += f"{i+1}. {mention} — +<b>{reward}</b> primogems\n"
        log_msg += f"{i+1}. {username or uid} ({points} pts) ➜ +{reward} primogems\n"

    await update.message.reply_text(result_msg, parse_mode=ParseMode.HTML)
    try:
        await context.bot.send_message(chat_id=RESET_LOG_CHAT_ID, text=log_msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Couldn't send log: {e}")

# --- REGISTER HANDLERS (same as before, keep your register function but import updated handlers) ---
def register_quiz_handlers(application):
    application.add_handler(CommandHandler("quiz", start_quiz))
    application.add_handler(CallbackQueryHandler(answer_quiz, pattern=r"^quiz:"))
    application.add_handler(CommandHandler("leaderboard", show_leaderboard))
    application.add_handler(CommandHandler("setintervals", set_intervals))

    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("addquestion", add_question_start)],
        states={
            ADD_Q_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_text)],
            ADD_Q_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_options)],
            ADD_Q_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_answer)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add)],
    ))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_tracker))
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
