# pvp.py
import sqlite3
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import random
import asyncio
from datetime import date
from datetime import datetime
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
from copy import deepcopy
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from html import escape as html_escape
from telegram.constants import ParseMode
import telegram

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from db import ensure_bank,get_bank,get_primogems,update_primos,update_bank,ensure_bank,get_balance,update_balance,update_paimon_box,user_exists,get_user_party,save_user_party
from db import get_steal_doc,unlock_steal_mode,lock_steal_mode,set_steal_mode,get_user_characters,get_defeats_today,increment_monster_kill,set_defeats_today,get_monsterboard_top,get_user_monster_kills,reset_monster_season
DB_PATH = "/mnt/data/quiz.db"
ADMIN_ID = 5192424390


def resolve_party_stats(user_id, party_list):
    chars = get_user_characters(user_id)
    final = []

    for name in party_list:
        if name in chars:
            data = chars[name]
            final.append((
                name,
                data["power"],
                data["constellation"]
            ))

    return final

async def party_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data["party_owner_id"] = user_id 
    
    party = get_user_party(user_id)

    if party:
        total_power = sum(p for _, p, _ in party)
        msg = "👥 *Your Current Party*\n"
        msg += f"⚔️ *Total Power:* {total_power}\n\n"
        for name, power, const in party:
            msg += f"• {name}" + (f" (C{const})" if const > 0 else "") + f" — ⚔️ {power}\n"

        keyboard = [
            [InlineKeyboardButton("✏️ Edit Party", callback_data="party_edit")],
            [InlineKeyboardButton("🗑️ Delete Party", callback_data="party_delete")]
        ]
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        context.user_data["star_mode"] = "5"
        context.user_data["party_selection"] = []
        await send_party_selection(update, context, user_id)

async def send_party_selection(update, context, user_id):
    # Fetch characters using your existing helper
    characters = get_user_characters(user_id)  # {name: {rarity, power, constellation}}

    # Convert dict → list of tuples
    char_data = [
        (name, data.get("rarity", 4), data.get("power", 0), data.get("constellation", 0))
        for name, data in characters.items()
    ]

    selected = context.user_data.get("party_selection", [])
    mode = context.user_data.get("star_mode", "5")

    buttons = []

    if mode == "5":
        filtered = [(n, r, p, c) for n, r, p, c in char_data if r == 5]
        toggle_button = InlineKeyboardButton("⭐ Show 4★ Characters", callback_data=f"party_toggle_4_{user_id}")
    else:
        filtered = [(n, r, p, c) for n, r, p, c in char_data if r == 4]
        toggle_button = InlineKeyboardButton("🌟 Show 5★ Characters", callback_data=f"party_toggle_5_{user_id}")

    for name, rarity, power, const in sorted(filtered):
        prefix = "✅" if name in selected else "❌"
        bonus = const * (10 if rarity == 5 else 5)
        total = power + bonus

        buttons.append([
            InlineKeyboardButton(
                f"{prefix} {name} (C{const}, ⚔️ {total})",
                callback_data=f"party_{name}_{user_id}"
            )
        ])

    buttons.append([toggle_button])
    buttons.append([InlineKeyboardButton("💾 Save Party", callback_data=f"party_save_{user_id}")])

    text = "Select up to 4 characters for your party:"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))



async def party_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_id = query.from_user.id
    data = query.data
    await query.answer()

    parts = data.split("_")


    if parts[-1].isdigit():
        target_id = int(parts[-1])
        action = "_".join(parts[:-1])
    else:

        target_id = clicker_id
        action = data


    if clicker_id != target_id:
        await query.answer("❌ You cannot edit someone else's party!", show_alert=True)
        return

    # Handle different actions
    if action == "party_edit":
        party = get_user_party(target_id)
        context.user_data["star_mode"] = "5"
        context.user_data["party_selection"] = [name for name, _, _ in party]
        await send_party_selection(update, context, target_id)
        return

    if action == "party_delete":
        save_user_party(target_id, [])
        context.user_data["party_selection"] = []
        context.user_data["star_mode"] = "5"
        await query.edit_message_text("🗑️ Your party has been deleted. Select a new party:")
        await send_party_selection(update, context, target_id)
        return

    if action == "party_toggle_4":
        context.user_data["star_mode"] = "4"
        await send_party_selection(update, context, target_id)
        return

    if action == "party_toggle_5":
        context.user_data["star_mode"] = "5"
        await send_party_selection(update, context, target_id)
        return

    if action == "party_save":
        selected = context.user_data.get("party_selection", [])[:4]
        save_user_party(target_id, selected)
        await query.edit_message_text(f"✅ Party saved!\n📜 Selected: {', '.join(selected) if selected else 'No characters'}")
        return

    if action.startswith("party"):
        char_name = action.replace("party_", "")
        current = context.user_data.get("party_selection", [])

        if char_name in current:
            current.remove(char_name)
        else:
            if len(current) >= 4:
                await query.answer("⚠️ You can only select up to 4 characters.", show_alert=True)
                return
            current.append(char_name)

        context.user_data["party_selection"] = current
        await send_party_selection(update, context, target_id)

DB_PATH = "/mnt/data/quiz.db"

# 🔹 Monster Types
MONSTERS = {
    "slime": {"name": "Electro Slime", "hp": 120, "reward_primos": 20, "lose_primos": 10, "emoji": "🟦", "lose_message": "Don’t worry, even heroes need a nap sometimes."},  # [execute_python:1]
    "hilichurl": {"name": "Hilichurl Warrior", "hp": 180, "reward_primos": 25, "lose_primos": 15, "emoji": "🟫", "lose_message": "Maybe it’s time to train your party... just saying."},  # [execute_python:1]
    "abyss_mage": {"name": "Pyro Abyss Mage", "hp": 250, "reward_primos": 15, "lose_primos": 10, "emoji": "🔴", "lose_message": "RIP. But hey, those primogems weren’t gonna last forever."},  # [execute_python:1]
    "ruin_guard": {"name": "Ruin Guard", "hp": 350, "reward_primos": 30, "lose_primos": 20, "emoji": "⚙️", "lose_message": "You lose. But hey, at least you tried!"},  # [execute_python:1]
    "Stormterror": {"name": "Stormterror Dvalin", "hp": 800, "reward_primos": 80, "lose_primos": 50, "emoji": "🐉", "lose_message": "The winds weren’t in your favor today."},  # [execute_python:1]
    "Andrius": {"name": "Lupus Boreas", "hp": 850, "reward_primos": 80, "lose_primos": 50, "emoji": "🐺", "lose_message": "Even the snow pities your defeat."},  # [execute_python:1]
    "Tartaglia": {"name": "Childe", "hp": 700, "reward_primos": 80, "lose_primos": 50, "emoji": "🏹", "lose_message": "He went full Foul Legacy on you."},  # [execute_python:1]
    "Azhdaha": {"name": "Azhdaha", "hp": 800, "reward_primos": 80, "lose_primos": 50, "emoji": "🪨", "lose_message": "You were buried under his wrath."},  # [execute_python:1]
    "LaSignora": {"name": "La Signora", "hp": 800, "reward_primos": 80, "lose_primos": 50, "emoji": "❄️🔥", "lose_message": "She burned you, then froze your dreams."},  # [execute_python:1]
    "RaidenBoss": {"name": "Raiden Shogun Puppet", "hp": 850, "reward_primos": 80, "lose_primos": 50, "emoji": "⚡", "lose_message": "You dared defy eternity and lost."},  # [execute_python:1]
    "Scaramouche": {"name": "Shouki no Kami", "hp": 700, "reward_primos": 80, "lose_primos": 50, "emoji": "🧠", "lose_message": "The Balladeer danced on your pride."},  # [execute_python:1]
    "Apep": {"name": "Guardian of Apep's Oasis", "hp": 800, "reward_primos": 80, "lose_primos": 50, "emoji": "🌿", "lose_message": "The Dendro dragon turned you to mulch."},  # [execute_python:1]
    "Arlecchino": {"name": "Arlecchino", "hp": 850, "reward_primos": 80, "lose_primos": 50, "emoji": "🔥", "lose_message": "She smiled... then you vanished."},  # [execute_python:1]
    "Whale": {"name": "whale", "hp": 800, "reward_primos": 80, "lose_primos": 50, "emoji": "🗡️", "lose_message": "Now! OPEN U R WALLET MY N....."},  # [execute_python:1]
    "CallamusRex": {"name": "Callamus Rex", "hp": 800, "reward_primos": 80, "lose_primos": 50, "emoji": "🐲", "lose_message": "Natlan’s flames judged you unworthy."},  # [execute_python:1]
    "cryo_lector": {"name": "Abyss Lector: Frostforged", "hp": 580, "reward_primos": 60, "lose_primos": 45, "emoji": "❄️", "lose_message": "Frozen in time and regrets."},  # [execute_python:1]
    "eremite_duelist": {"name": "Eremite Sword Dancer", "hp": 420, "reward_primos": 50, "lose_primos": 30, "emoji": "⚔️", "lose_message": "Outdanced in the desert heat."},  # [execute_python:1]
    "spectral_scout": {"name": "Spectral Scout", "hp": 360, "reward_primos": 40, "lose_primos": 25, "emoji": "👻", "lose_message": "Boo! You vanished instead."},  # [execute_python:1]
    "ruin_serpentling": {"name": "Ruin Serpentling", "hp": 520, "reward_primos": 60, "lose_primos": 40, "emoji": "🌀", "lose_message": "Buried under its coils."},  # [execute_python:1]
    "primal_construct": {"name": "Primal Construct: Repulsor", "hp": 400, "reward_primos": 95, "lose_primos": 48, "emoji": "🧿", "lose_message": "Got deleted by ancient code."},  # [execute_python:1]
    "fungus_gunner": {"name": "Spore Shooter", "hp": 370, "reward_primos": 35, "lose_primos": 22, "emoji": "🌫️", "lose_message": "Shot down by a puffball."},  # [execute_python:1]
    "slate_warden": {"name": "Slate Warden", "hp": 590, "reward_primos": 49, "lose_primos": 50, "emoji": "🪨", "lose_message": "Stone cold defeat."},  # [execute_python:1]
    "cryoshroom_guardian": {"name": "Frostshroom Sentinel", "hp": 310, "reward_primos": 70, "lose_primos": 30, "emoji": "🍄", "lose_message": "Froze your ambition in a single spore."},  # [execute_python:1]
    "hilichurl_berserker": {"name": "Hilichurl Berserker", "hp": 300, "reward_primos": 55, "lose_primos": 20, "emoji": "🪓", "lose_message": "He bonked you back to Mondstadt."},  # [execute_python:1]
    "electro_slime": {"name": "Electro Slime XL", "hp": 350, "reward_primos": 30, "lose_primos": 20, "emoji": "🟣", "lose_message": "Shocked into submission."},  # [execute_python:1]
    "mirror_maiden": {"name": "Mirror Maiden", "hp": 600, "reward_primos": 65, "lose_primos": 45, "emoji": "🪞", "lose_message": "Lost in the mirror dimension."},  # [execute_python:1]
    "ruin_scout": {"name": "Ruin Scout", "hp": 500, "reward_primos": 50, "lose_primos": 40, "emoji": "🤖", "lose_message": "Mechanical punch to the pride."},  # [execute_python:1]
    "fatui_skirmisher": {"name": "Fatui Skirmisher", "hp": 450, "reward_primos": 40, "lose_primos": 30, "emoji": "🛡️", "lose_message": "Outplayed by a soldier in a tracksuit."},  # [execute_python:1]
    "fungal_beast": {"name": "Fungal Beast", "hp": 380, "reward_primos": 40, "lose_primos": 25, "emoji": "🍄", "lose_message": "The shroom stomped your dreams."},  # [execute_python:1]
    "clockwork_mech": {"name": "Clockwork Mech", "hp": 580, "reward_primos": 60, "lose_primos": 50, "emoji": "⚙️", "lose_message": "You became spare parts."}  # [execute_python:1]
}




active_battles = {}


message_count = 0
SPAWN_INTERVAL = 50 


async def track_message_for_spawn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track messages and spawn monster every 50 messages"""
    global message_count
    

    if update.effective_chat.type in ['group', 'supergroup']:
        message_count += 1
        
        if message_count >= SPAWN_INTERVAL :
            message_count = 0  # Reset counter
            await spawn_monster_in_chat(update.effective_chat.id, context)



from copy import deepcopy
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import random

async def spawn_monster_in_chat(chat_id, context):
    """Spawn a single-player monster in chat."""

    monster_type = random.choice(list(MONSTERS.keys()))
    monster = deepcopy(MONSTERS[monster_type])
    monster["type"] = monster_type
    monster["max_hp"] = monster["hp"]


    battle_id = f"battle_{random.randint(1000, 9999)}"


    active_battles[battle_id] = {
        "monster": monster,
        "locked_by": None
    }


    msg = (
        f"🚨 **MONSTER APPEARED!**\n\n"
        f"{monster['emoji']} **{monster['name']}**\n"
        f"❤️ HP: {monster['hp']}\n"
        f"💎 Reward: {monster['reward_primos']} primogems\n"
        f"⚠️ Penalty: -{monster['lose_primos']} primogems\n\n"
        f"⏰ *Battle will expire in 3 minutes!*"
    )

    keyboard = [[InlineKeyboardButton("⚔️ FIGHT!", callback_data=f"fight_{battle_id}")]]
    await context.bot.send_message(
        chat_id=chat_id,
        text=msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


    def remove_battle():
        if battle_id in active_battles:
            del active_battles[battle_id]

    context.job_queue.run_once(lambda ctx: remove_battle(), 180)

MAX_DEFEATS_PER_DAY = 10

async def fight_monster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    username = query.from_user.first_name or "Fighter"

    battle_id = query.data.replace("fight_", "")
    battle = active_battles.get(battle_id)

    if not battle or "monster" not in battle:
        await query.answer("⚠️ This battle has expired!", show_alert=True)
        return

    if battle["locked_by"] and battle["locked_by"] != user_id:
        await query.answer("❌ Someone else already started this battle!", show_alert=True)
        return

    party_names = get_user_party(user_id)
    party = resolve_party_stats(user_id, party_names)

    if not party:
        await query.answer("❌ You need to set up a party first! Use /party", show_alert=True)
        return
    if len(party) == 0:
        await query.answer("❌ Your party is empty! Add characters with /party", show_alert=True)
        return

    # --- MONGO REPLACEMENT ---
    primogems = get_primogems(user_id)
    defeats_today = get_defeats_today(user_id)
    lose_primos = battle["monster"].get("lose_primos", 500)

    if primogems < lose_primos:
        await query.answer(f"💎 You need at least {lose_primos} primogems to fight!", show_alert=True)
        return

    if defeats_today >= MAX_DEFEATS_PER_DAY:
        await query.answer(
            f"🚫 You've reached your daily monster defeat limit ({defeats_today}/{MAX_DEFEATS_PER_DAY}). "
            "Try again tomorrow!",
            show_alert=True
        )
        return

    battle["locked_by"] = user_id
    await query.answer("⚔️ Battle begins!")

    monster = battle["monster"]
    await battle_sequence(update, context, user_id, username, party, monster, battle_id)


async def battle_sequence(update, context, user_id, username, party, monster, battle_id):
    # Store battle state
    battle_state = {
        "user_id": user_id,
        "username": username,
        "party": party,
        "monster": monster.copy(),
        "turn": 0,
        "accumulated_buff": 0,
        "battle_log": "",
        "used_characters": []
    }
    

    active_battles[battle_id] = battle_state
    

    await show_battle_screen(update, context, battle_id)

async def show_battle_screen(update, context, battle_id):
    battle_state = active_battles[battle_id]
    monster = battle_state["monster"]
    party = battle_state["party"]
    used_chars = battle_state["used_characters"]

    msg = f"⚔️ **{battle_state['username']} VS {monster['name']}**\n"
    msg += f"❤️ Monster HP: {monster['hp']}/{monster['max_hp']}\n"
    msg += f"🔄 Turn: {battle_state['turn'] + 1}/4\n\n"
    
    if battle_state["accumulated_buff"] > 0:
        msg += f"✨ **Current Buff:** +{battle_state['accumulated_buff']} damage\n\n"
    
    msg += f"🎯 **Choose your character to attack:**\n"

    if battle_state["battle_log"]:
        msg += f"\n📝 **Battle Log:**\n{battle_state['battle_log']}"
    

    buttons = []
    for char_name, char_power, const in party:
        if char_name not in used_chars:
            button_text = f"⚔️ {char_name} (C{const}, ⚔️ {char_power})"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"attack_{battle_id}_{char_name}")])

    

    buttons.append([InlineKeyboardButton("🏃‍♂️ Retreat", callback_data=f"retreat_{battle_id}")])
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            msg, 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await update.message.reply_text(
            msg, 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup(buttons)
        )


async def handle_character_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    

    callback_data = query.data

    

    data_without_prefix = callback_data[7:]

    

    last_underscore_pos = data_without_prefix.rfind("_")
    
    if last_underscore_pos == -1:
        await query.answer("❌ Invalid attack data format!", show_alert=True)
        return
    

    battle_id = data_without_prefix[:last_underscore_pos]
    char_name = data_without_prefix[last_underscore_pos + 1:]
    

    
    if battle_id not in active_battles:
        await query.answer("⚠️ This battle has expired!", show_alert=True)
        print(f"Available battles: {list(active_battles.keys())}")
        return
    
    battle_state = active_battles[battle_id]
    

    if query.from_user.id != battle_state["user_id"]:
        await query.answer("❌ This is not your battle!", show_alert=True)
        return
    

    await execute_attack(update, context, battle_id, char_name)



async def execute_attack(update, context, battle_id, char_name):
    battle_state = active_battles[battle_id]
    monster = battle_state["monster"]
    party = battle_state["party"]

    char_power = 0
    for name, power, const in party:
        if name == char_name:
            char_power = power
            break

    # Get buff for this character (default 0)
    char_buff = battle_state.get("buffs", {}).get(char_name, 0)
    total_damage = char_power + char_buff
    crit_hit = False

    is_last_attack = (battle_state["turn"] == 3) or (len(battle_state["used_characters"]) == len(party) - 1)
    if is_last_attack:
        crit_chance = random.randint(30, 70)
        if random.randint(1, 100) <= crit_chance:
            crit_hit = True
            total_damage *= 2

    monster["hp"] -= total_damage

    turn_num = battle_state["turn"] + 1
    log_entry = f"**Turn {turn_num}:** {char_name} attacks!\n"
    base = f"⚔️ Damage: {char_power}"
    if char_buff > 0:
        base += f" + {char_buff} (buff)"
    base += f" = {total_damage}"
    if crit_hit:
        base += " 💥 **CRIT HIT! x2**"
    log_entry += base + "\n"

    log_entry += f"❤️ Monster HP: {max(0, monster['hp'])}/{monster['max_hp']}\n"

    # Remove buff after using it
    battle_state.setdefault("buffs", {}).pop(char_name, None)

    # Buff next allies with 30-70% chance
    if battle_state["turn"] < 3:
        buff_chance = random.randint(30, 70)
        if random.randint(1, 100) <= buff_chance:
            buffed_allies = []
            for name, _, _ in party:
                if name not in battle_state["used_characters"] and name != char_name:
                    # Add per-character buff
                    battle_state["buffs"][name] = battle_state["buffs"].get(name, 0) + char_power
                    buffed_allies.append(name)
            if buffed_allies:
                allies_str = ", ".join(buffed_allies)
                log_entry += f"✨ {char_name} buffs {allies_str} (+{char_power} damage)\n"

    log_entry += "\n"
    battle_state["battle_log"] += log_entry
    battle_state["used_characters"].append(char_name)
    battle_state["turn"] += 1

    if monster["hp"] <= 0:
        await battle_victory(update, context, battle_id)
    elif battle_state["turn"] >= 4 or len(battle_state["used_characters"]) >= len(party):
        await battle_defeat(update, context, battle_id)
    else:
        await show_battle_screen(update, context, battle_id)


async def battle_victory(update, context, battle_id):
    battle_state = active_battles[battle_id]
    monster = battle_state["monster"]
    user_id = battle_state["user_id"]
    monster_name = monster["type"]

    user = await context.bot.get_chat(user_id)
    name = user.first_name or "Unknown"

    reward = MONSTERS[monster_name]["reward_primos"]

    # Prepare safe HTML text
    raw_log = battle_state.get("battle_log", "") or ""
    safe_log = html_escape(raw_log)
    safe_name = html_escape(name)
    safe_monster = html_escape(monster_name)
    safe_reward = html_escape(str(reward))

    msg = ""
    if safe_log:
        msg += f"<pre>{safe_log}</pre>\n\n"
    msg += f"🎉 <b>{safe_name}</b> is VICTORIOUS against <b>{safe_monster}</b>!\n"
    msg += f"💎 +<b>{safe_reward}</b> primogems earned!"

    # --- MONGO updates ---
    update_primos(user_id, reward)
    increment_monster_kill(user_id, monster_name)
    current_defeats = get_defeats_today(user_id)
    set_defeats_today(user_id, current_defeats + 1)

    # Clean up
    del active_battles[battle_id]

    # send edit with HTML and guard against "message not modified"
    try:
        await update.callback_query.edit_message_text(
            text=msg,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except telegram.error.BadRequest as e:
        # If message not modified or can't parse, try sending plain text fallback
        if "Message is not modified" in str(e):
            try:
                await update.callback_query.answer()  # acknowledge quietly
            except:
                pass
        else:
            try:
                await update.callback_query.edit_message_text(
                    text=f"{html_escape(safe_name)} defeated {html_escape(safe_monster)}! +{safe_reward} primogems",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                # last resort: send as new message
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"{safe_name} defeated {safe_monster}! +{safe_reward} primogems"
                )


async def battle_defeat(update, context, battle_id):
    battle_state = active_battles[battle_id]
    monster = battle_state["monster"]
    user_id = battle_state["user_id"]

    penalty = MONSTERS[monster["type"]]["lose_primos"]
    lose_quote = MONSTERS[monster["type"]].get("lose_message")

    raw_log = battle_state.get("battle_log", "") or ""
    safe_log = html_escape(raw_log)
    user_name = html_escape(update.effective_user.first_name or "Unknown")
    monster_name = html_escape(monster["type"])
    hp = html_escape(str(monster["hp"]))
    primos_lost = html_escape(str(penalty))

    msg = ""
    if safe_log:
        msg += f"<pre>{safe_log}</pre>\n\n"

    msg += f"💀 <b>DEFEAT!</b>\n"
    msg += f"<b>{user_name}</b> lost to <b>{monster_name}</b> with <b>{hp} HP</b> remaining.\n"
    msg += f"💸 <b>-{primos_lost}</b> primogems lost!\n"

    if lose_quote:
        msg += f"\n❝<i>{html_escape(lose_quote)}</i>❞\n"

    # --- MONGO updates ---
    update_primos(user_id, -penalty)
    if get_primogems(user_id) < 0:
        update_primos(user_id, -get_primogems(user_id))

    del active_battles[battle_id]

    # edit message with HTML and guard against parse errors/message-not-modified
    try:
        await update.callback_query.edit_message_text(
            text=msg,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except telegram.error.BadRequest as e:
        if "Message is not modified" in str(e):
            try:
                await update.callback_query.answer()
            except:
                pass
        else:
            # fallback: try simpler message
            try:
                await update.callback_query.edit_message_text(
                    text=f"{user_name} lost to {monster_name}. -{primos_lost} primogems",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"{user_name} lost to {monster_name}. -{primos_lost} primogems"
                )

async def handle_retreat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    battle_id = query.data.replace("retreat_", "")

    if battle_id not in active_battles:
        await query.answer("⚠️ Battle already ended!", show_alert=True)
        return

    battle_state = active_battles[battle_id]

    if query.from_user.id != battle_state["user_id"]:
        await query.answer("❌ This is not your battle!", show_alert=True)
        return

    user_id = battle_state["user_id"]
    monster_name = battle_state["monster"]["type"]

    user = await context.bot.get_chat(user_id)
    name = user.first_name

    retreat_penalty = 100

    # --- MONGO REPLACEMENT ---
    update_primos(user_id, -retreat_penalty)
    if get_primogems(user_id) < 0:
        update_primos(user_id, -get_primogems(user_id))

    del active_battles[battle_id]

    await query.edit_message_text(
        f"🏃‍♂️ **{name} retreated from battle with {monster_name}!**\n💸 -{retreat_penalty} primogems penalty."
    )
    await query.answer("Retreated with penalty!")




async def monster_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /monster - Spawn monster manually"""
    ADMIN_IDS = [5192424390]  
    
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    

    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("⚠️ This command only works in group chats!")
        return
        
    await spawn_monster_in_chat(update.effective_chat.id, context)
    await update.message.reply_text("✅ Monster spawned!")


async def msgcount_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /msgcount - Check current message count"""     
    global message_count
    remaining = SPAWN_INTERVAL - message_count
    
    msg = f"📊 **Message Counter Status**\n"
    msg += f"💬 Messages: {message_count}/{SPAWN_INTERVAL}\n"
    msg += f"⏳ Remaining: {remaining} messages until next spawn"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def reset_defeats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("🚫 Only admins can use this.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET defeats_today = 0")
        conn.commit()

    await update.message.reply_text("✅ Daily monster defeat counters have been reset.")

async def monsterboard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    leaderboard = get_monsterboard_top()

    if not leaderboard:
        await update.message.reply_text("📊 No monster defeats recorded yet!")
        return

    msg = "🏆 *Monster Defeat Leaderboard*\n"

    for user_id, name, total in leaderboard:
        esc_name = escape_markdown(name, version=2)
        msg += f"\n👤 *{esc_name}* ({total} total):\n"

        # Get monster breakdown
        kills = get_user_monster_kills(user_id)
        for row in kills:
            monster = escape_markdown(row['monster'], 2)
            count = row['count']
            msg += f"• {monster}: {count}x\n"

    await update.message.reply_text(msg, parse_mode="MarkdownV2")

    
async def resetmonster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ADMIN_IDS = [5192424390]

    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ You don't have permission.")
        return

    leaderboard = get_monsterboard_top(9999)

    if not leaderboard:
        await update.message.reply_text("📊 No monster defeats recorded yet!")
        return

    rewards = [1600, 1000, 500]

    # Distribute rewards
    for i, (user_id, name, total) in enumerate(leaderboard[:3]):
        update_primos(user_id, rewards[i])

    # Prepare message
    msg = "🏆 <b>Monster Defeat Season Ended!</b>\n\n"

    msg += "<b>Top 3 Rewards:</b>\n"
    for i, (user_id, name, total) in enumerate(leaderboard[:3]):
        msg += f"{['🥇','🥈','🥉'][i]} {name} — {total} defeats — +{rewards[i]} 💎\n"

    msg += "\n<b>Full Leaderboard:</b>\n"
    for rank, (user_id, name, total) in enumerate(leaderboard, 1):
        msg += f"#{rank} {name} — {total}\n"

    # Clear season data
    reset_monster_season()

    await update.message.reply_text(msg, parse_mode="HTML")


async def paimonbox(update, context):
    user = update.effective_user
    user_id = user.id

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /paimonbox <bet_amount>")
        return

    bet = int(context.args[0])
    if bet <= 0:
        await update.message.reply_text("Bet must be a positive number.")
        return


    row=get_balance(user_id,"Primogems")

    if not row or row < bet:
        await update.message.reply_text("You don't have enough primogems.")
        return
    
    plays = update_paimon_box(user_id)

    if plays >= 3:
        await update.message.reply_text("You've already played Paimon's Bargain 3 times today!")
        return


    context.user_data["paimon_bet"] = bet
    context.user_data["paimon_outcomes"] = random.sample(["x1", "nothing", "lose"], k=3)

    photo_url = "https://i.postimg.cc/YqprqYGj/4e383f50-3dfe-11ed-b7c7-c290fb5b71df.jpg"

    keyboard = [
        [InlineKeyboardButton("📦 Box A", callback_data="paimonbox_0"),
         InlineKeyboardButton("📦 Box B", callback_data="paimonbox_1"),
         InlineKeyboardButton("📦 Box C", callback_data="paimonbox_2")]
    ]

    await update.message.reply_photo(
        photo=photo_url,
        caption=f"🎁 *Paimon’s Bargain Begins!*\n\nPick one of the boxes below... she’s watching. 👀\n\n🔹 *Bet:* {bet} primogems\n🔄 *Plays Left Today:* {3 - plays}\n\nChoose wisely...",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_paimonbox_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if "paimon_bet" not in context.user_data or "paimon_outcomes" not in context.user_data:
        await query.edit_message_caption(caption="This session expired. Please use /paimonbox again.")
        return

    choice_index = int(query.data.split("_")[1])
    outcome = context.user_data["paimon_outcomes"][choice_index]
    bet = context.user_data["paimon_bet"]



    if outcome == "x1":
        update_balance(user_id,"Primogems",bet)
        result_msg = f"🎉 You opened Box {chr(65 + choice_index)}...\n\n✨ You found *double primogems*! (+{bet * 1})\n💎 New Balance: "
    elif outcome == "nothing":
        result_msg = f"😐 You opened Box {chr(65 + choice_index)}...\n\nThere's nothing inside. Just... air.\n💎 Balance: "
    else: 
        update_balance(user_id,"Primogems",-bet)
        result_msg = f"😈 You opened Box {chr(65 + choice_index)}...\n\n*Evil Paimon* jumps out and steals your {bet} primogems!\n💎 New Balance: "
    update_paimon_box(user_id,update=True)
    new_balance = get_balance(user_id,"Primogems")

    plays_today = update_paimon_box(user_id)
    plays_left = max(0, 3 - plays_today)

    result_msg += f"{new_balance} primogems\n🔁 Plays Left Today: {plays_left}"


    context.user_data.pop("paimon_bet", None)
    context.user_data.pop("paimon_outcomes", None)

    await query.edit_message_caption(
        caption=result_msg,
        parse_mode="Markdown"
    )




ADMINS = [5192424390] 

from datetime import date

async def reset_paimon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    if admin_id not in ADMINS:
        await update.message.reply_text("🚫 You don't have permission to use this command.")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Reply to the user's message with /resetpaimon.")
        return

    target_user = update.message.reply_to_message.from_user
    target_user_id = target_user.id
    today = date.today().isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM paimonbox WHERE user_id = ? AND date = ?",
            (target_user_id, today)
        )
        conn.commit()

    await update.message.reply_text(
        f"✅ Reset PaimonBox attempts for *{target_user.first_name}* (`{target_user_id}`) for today.",
        parse_mode="Markdown"
    )

async def toss_game(update:Update,context:ContextTypes.DEFAULT_TYPE):
    user_id=update.effective_user.id
    if len(context.args)!=2:
        await update.message.reply_text("Usage :/flip <amount> h/t or heads/tails")
        return
    try:
        bet=int(context.args[0])
        guess=context.args[1].lower()
    except:
        await update.message.reply_text("Invalid format bruh :/flip <amount> h/t or heads/tails")
        return
    if guess in ["heads","h"]:
        guess="heads"
    elif guess in["tails","t"]:
        guess="tails"
    else:
        await update.message.reply_text("guess must be 'heads','h','tails','t'")
        return

    primos = get_balance(user_id,"Primogems")

    if bet <= 0:
        await update.message.reply_text("Bet must be more than 0.")
        return

    if not primos or bet > primos:
        await update.message.reply_text(f"You only have {primos} primogems!")
        return

    toss_msg = await update.message.reply_text(
        "<b>Flipping the coin...</b>\n<i>Let fate decide 🪙</i>",
        parse_mode="HTML"
    )

    await asyncio.sleep(1.5)

    try:
        await toss_msg.delete()  
    except:
        pass  

    result = random.choice(["heads", "tails"])


    if result == guess:
        winnings=bet
        update_balance(user_id,"Primogems",winnings)
        await update.message.reply_text(
        f"🎉 <b>Coin landed on</b> <i>{result}</i>!\n"
        f"🏆 You won <b>{winnings}</b> primogems!",
        parse_mode="HTML"
        )
    else:
        winnings=bet
        update_balance(user_id,"Primogems",-winnings)
        await update.message.reply_text(
        f"😢 <b>Coin landed on</b> <i>{result}</i>.\n"
        f"💸 You lost <b>{bet}</b> primogems.",
        parse_mode="HTML"
        )



async def dart_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /dart <bet amount>")
        return

    bet = int(context.args[0])
    if bet <= 0:
        await update.message.reply_text("Bet must be more than 0.")
        return

    primos = get_balance(user_id,"Primogems")

    if not primos or bet > primos:
        await update.message.reply_text(f"You only have {primos} primogems!")
        return
    update_balance(user_id,"Primogems",-bet)
    # Send dart emoji
    dart_msg = await update.message.reply_dice(emoji="🎯")
    await asyncio.sleep(2.75)
    result = dart_msg.dice.value

    if result == 1:
        penalty = int(bet * 0.5)
        update_balance(user_id,"Primogems",-penalty)
        text = f"💥 Complete miss! Paimon charges a penalty!\n💸 You lost *{bet + penalty}* primogems!"


    elif result in [2, 3]:
        text = f"😢 You missed the target.\nYou lost *{bet}* primogems."

    elif result == 4:
        update_balance(user_id,"Primogems",int(bet*1.5))
        text = f"🎯 Hit the board!\nYou won *{int(bet*1.5)}* primogems!"

    elif result == 5:
        update_balance(user_id,"Primogems",int(bet*2))
        text = f"✅ Almost bullseye!\nYou won *{int(bet*2)}* primogems!"

    elif result == 6:
        update_balance(user_id,"Primogems",int(bet*2.5))
        text = f"🏆 BULLSEYE!!\nYou won *{int(bet*2.5)}* primogems!"

    await update.message.reply_text(text, parse_mode="Markdown")



import time
from telegram import constants
import time
import sqlite3

async def toggle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) != 1 or context.args[0].lower() not in ["on", "off"]:
        await update.message.reply_text("Usage: /mode on | /mode off")
        return

    req = context.args[0].lower()
    now = int(time.time())

    if not user_exists(user_id):
        await update.message.reply_text("⚠️ You are not registered.")
        return

    doc = get_steal_doc(user_id)
    mode = doc["Mode"]
    locked = doc["Locked"]
    unlock = doc["Unlock"]

    if req == "on":
        if mode == "On":
            await update.message.reply_text("ℹ️ Mode already ON.")
            return

        if locked and now < unlock:
            mins = (unlock - now) // 60
            await update.message.reply_text(f"⏳ Cannot enable ON yet. Wait {mins} minutes.")
            return

        unlock_steal_mode(user_id)
        await update.message.reply_text("✅ Mode turned ON.")
        return

    if req == "off":
        if locked:
            mins = (unlock - now) // 60
            await update.message.reply_text(f"⏳ Mode is locked OFF for {mins} more minutes.")
            return

        set_steal_mode(user_id, "Off")
        await update.message.reply_text("⏸️ Mode turned OFF (manual).")
        return


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ADMIN_ID = 5192424390  # <-- Set to your Telegram User ID
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Only the admin can use this command!")
        return

    import sqlite3
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("SELECT user_id FROM users WHERE steal_mode='off'")
        users = [row[0] for row in c.fetchall()]
        c.execute("UPDATE users SET steal_mode='on', mode_lock_until=0 WHERE steal_mode='off'")
        conn.commit()

    count = len(users)
    if count:
        await update.message.reply_text(f"✅ {count} users had their steal mode set to ON immediately!")
    else:
        await update.message.reply_text("ℹ️ All user modes were already ON.")

    if count:
        msg = "🛠 <b>TEST OVERRIDE</b>: All affected users set to <b>ON</b> instantly:\n\n"
        for uid in users:
            try:
                user = await context.bot.get_chat(uid)
                name = user.full_name or f"User {uid}"
            except Exception:
                name = f"User {uid}"
            msg += f"• {name} (<code>{uid}</code>)\n"
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=msg,
                parse_mode="HTML"
            )
        except Exception as e:
            print("[/test] Failed to send admin DM", e)



DB_PATH = "/mnt/data/quiz.db"  

async def steal_cmmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    user_mention = f"[{user_name}](tg://user?id={user_id})"

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Reply to someone to steal.")
        return

    target = update.message.reply_to_message.from_user
    target_id = target.id
    target_name = target.first_name
    target_mention = f"[{target_name}](tg://user?id={target_id})"

    if user_id == target_id:
        await update.message.reply_text("❌ You can't steal from yourself.")
        return

    if not user_exists(user_id) or not user_exists(target_id):
        await update.message.reply_text("⚠️ Both users must have accounts.")
        return

    now = int(time.time())

    user_doc = get_steal_doc(user_id)
    target_doc = get_steal_doc(target_id)

    if user_doc["Mode"] != "On" or target_doc["Mode"] != "On":
        text = "🔒 Cannot steal:\n"
        if user_doc["Mode"] != "On":
            text += f"🧍 {user_name}'s mode is OFF.\n"
        if target_doc["Mode"] != "On":
            text += f"👤 {target_name}'s mode is OFF."
        await update.message.reply_text(text)
        return

    if now < user_doc["Unlock"] or now < target_doc["Unlock"]:
        reminder = "⏳ Cooldown:\n"
        if now < user_doc["Unlock"]:
            reminder += f"🧍 {user_name}: {(user_doc['Unlock'] - now)//60} min\n"
        if now < target_doc["Unlock"]:
            reminder += f"👤 {target_name}: {(target_doc['Unlock'] - now)//60} min"
        await update.message.reply_text(reminder)
        return

    lock_steal_mode(user_id)
    lock_steal_mode(target_id)

    # Determine outcome
    win = random.choice([True, False])
    percent = random.randint(30, 50)

    target_primos = get_primogems(target_id)
    user_primos = get_primogems(user_id)

    stolen = int((target_primos if win else user_primos) * percent / 100)

    if win and stolen > 0:
        update_balance(user_id, "Primogems", stolen)
        update_balance(target_id, "Primogems", -stolen)
        await update.message.reply_text(
            f"🕵️ {user_mention} stole {stolen} primogems ({percent}%) from {target_mention}!",
            parse_mode="Markdown"
        )
        return

    if win:
        await update.message.reply_text(
            f"😐 {user_mention} won but {target_mention} had nothing to steal.",
            parse_mode="Markdown"
        )
        return

    if stolen > 0:
        update_balance(user_id, "Primogems", -stolen)
        update_balance(target_id, "Primogems", stolen)
        await update.message.reply_text(
            f"😵 {user_mention} failed and lost {stolen} primogems to {target_mention}!",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        f"😮 {user_mention} failed but had nothing to lose.",
        parse_mode="Markdown"
    )
async def lunarsteal_cmmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    user_mention = f"[{user_name}](tg://user?id={user_id})"

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Reply to someone to steal.")
        return

    target = update.message.reply_to_message.from_user
    target_id = target.id
    target_name = target.first_name
    target_mention = f"[{target_name}](tg://user?id={target_id})"

    if user_id == target_id:
        await update.message.reply_text("❌ You can't steal from yourself.")
        return

    if not user_exists(user_id) or not user_exists(target_id):
        await update.message.reply_text("⚠️ Both users must have accounts.")
        return

    now = int(time.time())

    user_lunars = get_balance(user_id, "Lunar Crystals")
    target_lunars = get_balance(target_id, "Lunar Crystals")

    if user_lunars < 1000 or target_lunars < 1000:
        await update.message.reply_text(
            "🌙 Both users must have **at least 1000 Lunar Crystals** to use /lunarsteal."
        )
        return

    user_doc = get_steal_doc(user_id)
    target_doc = get_steal_doc(target_id)

    if user_doc["Mode"] != "On" or target_doc["Mode"] != "On":
        text = "🔒 Cannot steal:\n"
        if user_doc["Mode"] != "On":
            text += f"🧍 {user_name}'s mode is OFF.\n"
        if target_doc["Mode"] != "On":
            text += f"👤 {target_name}'s mode is OFF."
        await update.message.reply_text(text)
        return

    if now < user_doc["Unlock"] or now < target_doc["Unlock"]:
        reminder = "⏳ Cooldown:\n"
        if now < user_doc["Unlock"]:
            reminder += f"🧍 {user_name}: {(user_doc['Unlock'] - now)//60} min\n"
        if now < target_doc["Unlock"]:
            reminder += f"👤 {target_name}: {(target_doc['Unlock'] - now)//60} min"
        await update.message.reply_text(reminder)
        return

    lock_steal_mode(user_id)
    lock_steal_mode(target_id)

    win = random.choice([True, False])
    percent = random.randint(30, 50)

    stolen = int((target_lunars if win else user_lunars) * percent / 100)

    if win and stolen > 0:
        update_balance(user_id, "Lunar Crystals", stolen)
        update_balance(target_id, "Lunar Crystals", -stolen)
        await update.message.reply_text(
            f"🌙🕵️ {user_mention} stole {stolen} Lunar Crystals ({percent}%) from {target_mention}!",
            parse_mode="Markdown"
        )
        return

    if win:
        await update.message.reply_text(
            f"😐 {user_mention} won but {target_mention} had nothing to steal.",
            parse_mode="Markdown"
        )
        return

    if stolen > 0:
        update_balance(user_id, "Lunar Crystals", -stolen)
        update_balance(target_id, "Lunar Crystals", stolen)
        await update.message.reply_text(
            f"🌙😵 {user_mention} failed and lost {stolen} Lunar Crystals to {target_mention}!",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        f"😮 {user_mention} failed to steal, but had nothing to lose.",
        parse_mode="Markdown"
    )



async def rlock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    target_msg = update.message.reply_to_message


    allowed_admins = [5192424390]  

    if admin_id not in allowed_admins:
        await update.message.reply_text("❌ Only admins can use this command.")
        return

    if not target_msg:
        await update.message.reply_text("⚠️ Reply to a user's message to reset their cooldowns.")
        return

    target_id = target_msg.from_user.id

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET steal_cooldown = 0, mode_lock_until = 0 WHERE user_id = ?",
            (target_id,)
        )
        conn.commit()

    await update.message.reply_text(f"✅ Cooldowns for user `{target_id}` have been reset.", parse_mode="Markdown")


async def hinterval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SPAWN_INTERVAL
    user_id = update.effective_user.id


    if user_id not in ADMINS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return


    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ Usage: /hinterval <positive number>\nExample: /hinterval 100")
        return

    new_interval = int(context.args[0])
    if new_interval <= 0:
        await update.message.reply_text("⚠️ Interval must be a positive number.")
        return

    SPAWN_INTERVAL = new_interval
    await update.message.reply_text(f"✅ Monster spawn interval set to every {SPAWN_INTERVAL} messages.")

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id=update.effective_user.id
    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Usage: /deposit <positive number>")
        return

    primos=get_primogems(user_id)

    if primos < amount:
        await update.message.reply_text("❌ You don't have enough primogems in your balance.")
        return

    update_primos(user_id,-amount)
    update_bank(user_id,amount)

    await update.message.reply_text(f"✅ Deposited {amount} primogems into the bank.\n"
                                    f"May the Zhongli 🪙 watch over your balance.")


async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Usage: /withdraw <positive number>")
        return
    
    bank=get_bank(user_id)

    if amount > bank:
        await update.message.reply_text("❌ You don’t have enough in the bank.")
        return

    update_primos(user_id,amount)
    update_bank(user_id,-amount)

    await update.message.reply_text(f"💸 Withdrawn {amount} primogems from the bank.")

async def bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_bank(user_id)

    wallet=get_primogems(user_id)
    balance=get_bank(user_id)
    await update.message.reply_text(
        f"💼 Wallet: {wallet} primogems\n"
        f"🏦 Bank: {balance} primogems\n"
        f"📈 Interest: +5% added daily 💹"
    )

ADMIN_ID = 5192424390
MAX_MESSAGE_LENGTH = 4000  

async def reset_defeats_today(application):
    """Reset users' defeats_today and DM fight stats in safe chunks."""
    rows = []
    message_lines = ["🧾 <b>Daily Monster Fight Summary</b>\n"]

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()


        c.execute("SELECT user_id, defeats_today FROM users WHERE defeats_today > 0")
        rows = c.fetchall()

        if not rows:
            message_lines.append("📭 No users fought any monsters today.")
        else:
            for user_id, count in rows:
                try:
                    user = await application.bot.get_chat(user_id)
                    name = user.first_name or f"User {user_id}"
                    line = f"👤 <a href='tg://user?id={user_id}'>{name}</a> — {count}/10 fights used"
                except:
                    line = f"👤 User {user_id} — {count}/10 fights used"
                message_lines.append(line)


        c.execute("UPDATE users SET defeats_today = 0")
        conn.commit()


    footer = f"\n\n🗓️ Reset Time: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"


    full_report = "\n".join(message_lines) + footer
    chunks = []

    while len(full_report) > MAX_MESSAGE_LENGTH:

        split_index = full_report.rfind("\n", 0, MAX_MESSAGE_LENGTH)
        if split_index == -1:
            split_index = MAX_MESSAGE_LENGTH
        chunks.append(full_report[:split_index])
        full_report = full_report[split_index:].lstrip()

    if full_report:
        chunks.append(full_report)


    for chunk in chunks:
        try:
            await application.bot.send_message(
                chat_id=ADMIN_ID,
                text=chunk,
                parse_mode=constants.ParseMode.HTML
            )
        except Exception as e:
            print(f"❌ Error sending chunk: {e}")

    print("✅ defeats_today reset and fight summary sent.")

async def apply_daily_interest(application, is_manual=False):
    """Apply daily interest and send report to admin"""
    try:
        from datetime import datetime
        import pytz
        
        conn = sqlite3.connect("/mnt/data/quiz.db")
        cursor = conn.cursor()

        # Get users with positive bank balance
        cursor.execute("SELECT user_id, bank, primogems FROM users WHERE bank > 0")
        rows = cursor.fetchall()

        interest_data = []
        wealth_cap_data = []
        
        for user_id, bank, primogems in rows:
            # Calculate interest
            interest = int(bank * 0.05)
            new_bank = bank + interest if interest > 0 else bank
            new_primogems = primogems
            
            # Check wealth cap (10k each for bank and wallet)
            bank_capped = False
            wallet_capped = False
            original_bank = new_bank
            original_primogems = new_primogems
            
            if new_bank > 10000:
                new_bank = 10000
                bank_capped = True
                
            if new_primogems > 10000:
                new_primogems = 10000
                wallet_capped = True
            
            # Update database
            cursor.execute("UPDATE users SET bank = ?, primogems = ? WHERE user_id = ?", 
                         (new_bank, new_primogems, user_id))
            
            # Track changes
            if interest > 0:
                interest_data.append((user_id, bank, interest, new_bank))
                
            if bank_capped or wallet_capped:
                wealth_cap_data.append((user_id, bank_capped, wallet_capped, original_bank, new_bank, original_primogems, new_primogems))

        conn.commit()
        conn.close()

        # Send report to admin
        if interest_data or wealth_cap_data:
            ist = pytz.timezone('Asia/Kolkata')
            current_time = datetime.now(ist)
            
            if is_manual:
                title = "📈 *Manual Bank Interest Report \\(5%\\)*"
                time_text = f"🕛 _Applied manually at {current_time.strftime('%H:%M:%S')} IST_"
            else:
                title = "📈 *Daily Bank Interest Report \\(5%\\)*"
                time_text = "🕛 _Applied at 12:00 AM IST_"
            
            message = f"{title}\n\n"
            bot = application.bot

            # Interest applied section
            if interest_data:
                message += "💰 *Interest Applied:*\n"
                for uid, prev_bank, interest, new_bank in interest_data:
                    try:
                        user = await bot.get_chat(uid)
                        name = escape_markdown(user.first_name, version=2)
                    except:
                        name = f"User {uid}"

                    message += (
                        f"👤 *{name}* \\(`{uid}`\\)\n"
                        f"  ├ Previous: {prev_bank}\n"
                        f"  └ New Total: {new_bank} \\+{interest}\n\n"
                    )

            # Wealth cap section
            if wealth_cap_data:
                message += "⚠️ *Wealth Cap Applied \\(10k limit\\):*\n"
                for uid, bank_capped, wallet_capped, old_bank, new_bank, old_primogems, new_primogems in wealth_cap_data:
                    try:
                        user = await bot.get_chat(uid)
                        name = escape_markdown(user.first_name, version=2)
                    except:
                        name = f"User {uid}"

                    caps = []
                    if bank_capped:
                        caps.append(f"🏦 Bank \\({old_bank}→{new_bank}\\)")
                    if wallet_capped:
                        caps.append(f"💼 Wallet \\({old_primogems}→{new_primogems}\\)")
                    
                    join_str = r" \& "
                    message += f"👤 *{name}* \\(`{uid}`\\): {join_str.join(caps)}"



            message += f"\n{time_text}"
            
            try:
                await bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode="MarkdownV2")
                print("✅ Daily interest applied and report sent to admin")
                
                result_parts = []
                if interest_data:
                    result_parts.append(f"Applied interest to {len(interest_data)} users")
                if wealth_cap_data:
                    result_parts.append(f"Applied wealth cap to {len(wealth_cap_data)} users")
                
                return f"✅ {', '.join(result_parts)}"
                
            except Exception as e:
                print("❌ Failed to send interest report to admin:", e)
                return f"❌ Failed to send report: {e}"
        else:
            print("ℹ️ No users with positive bank balance found")
            return "ℹ️ No users with positive bank balance found"
            
    except Exception as e:
        print(f"❌ Error in apply_daily_interest: {e}")
        return f"❌ Error: {e}"
async def auto_unlock_modes(application):
    ADMIN_ID = 5192424390

    from db import unlock_expired_modes  

    unlocked = unlock_expired_modes()

    if not unlocked:
        print("[auto_unlock_modes] Nothing to unlock this round.")
        return

    bot = application.bot

    msg = "🔓 <b>Auto unlock report:</b>\n\n"

    for uid in unlocked:
        try:
            user = await bot.get_chat(uid)
            name = user.full_name or f"User {uid}"
        except:
            name = f"User {uid}"
        msg += f"• {name} (<code>{uid}</code>) is now <b>ON</b>\n"

    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=msg,
            parse_mode="HTML"
        )
    except Exception as e:
        print("[auto_unlock_modes] Failed to send report:", e)

    print("[auto_unlock_modes] Unlocked:", unlocked)


async def trigger_interest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual trigger for daily interest (Admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command")
        return
    
    await update.message.reply_text("🔄 Applying daily interest manually...")
    
    result = await apply_daily_interest(context.application, is_manual=True)
    await update.message.reply_text(result)
async def bank_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bank statistics (Admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command")
        return
    
    try:
        conn = sqlite3.connect("/mnt/data/quiz.db")
        cursor = conn.cursor()


        cursor.execute("SELECT COUNT(*) FROM users WHERE bank > 0")
        users_with_money = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(bank) FROM users WHERE bank > 0")
        total_money = cursor.fetchone()[0] or 0

        cursor.execute("SELECT AVG(bank) FROM users WHERE bank > 0")
        avg_money = cursor.fetchone()[0] or 0

        cursor.execute("SELECT user_id, bank FROM users WHERE bank > 0 ORDER BY bank DESC LIMIT 1")
        max_user = cursor.fetchone()
        max_user_id, max_money = max_user if max_user else (None, 0)

 
        cursor.execute("SELECT user_id, bank FROM users WHERE bank > 0 ORDER BY bank ASC LIMIT 1")
        min_user = cursor.fetchone()
        min_user_id, min_money = min_user if min_user else (None, 0)


        cursor.execute("SELECT SUM(CAST(bank * 0.05 AS INTEGER)) FROM users WHERE bank > 0")
        daily_interest = cursor.fetchone()[0] or 0

        conn.close()

        max_name = (await context.bot.get_chat(max_user_id)).first_name if max_user_id else "Unknown"
        min_name = (await context.bot.get_chat(min_user_id)).first_name if min_user_id else "Unknown"


        max_user_link = f"[{max_name}](tg://user?id={max_user_id})"
        min_user_link = f"[{min_name}](tg://user?id={min_user_id})"

        stats_message = f"""📊 *Bank Statistics*

👥 Users with money: {users_with_money}
💰 Total money in circulation: {total_money:,}
📈 Average balance: {avg_money:,.2f}
🔝 Highest balance: {max_money:,} — {max_user_link}
🔻 Lowest balance: {min_money:,} — {min_user_link}
📅 Daily interest payout: {daily_interest:,}"""

        await update.message.reply_text(stats_message, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting bank stats: `{e}`", parse_mode="Markdown")

    



def register_monster_handlers(application):
    # === Party Handlers ===
    application.add_handler(CommandHandler("party", party_command))
    application.add_handler(CallbackQueryHandler(party_callback, pattern=r"^party_"))

    # === Monster Battle Handlers ===
    application.add_handler(CommandHandler("monster", monster_command))
    application.add_handler(CommandHandler("msgcount", msgcount_command))
    application.add_handler(CommandHandler("monsterboard", monsterboard))
    application.add_handler(CommandHandler("paimonbox", paimonbox))
    application.add_handler(CallbackQueryHandler(handle_paimonbox_callback, pattern=r"^paimonbox_\d$"))
    application.add_handler(CommandHandler("resetpaimon", reset_paimon))
    application.add_handler(CommandHandler("flip", toss_game))
    application.add_handler(CommandHandler("dart", dart_game))
    application.add_handler(CommandHandler("mode", toggle_mode))
    application.add_handler(CommandHandler("steal", steal_cmmd))
    application.add_handler(CommandHandler("lsteal", lunarsteal_cmmd))
    application.add_handler(CommandHandler("rlock", rlock_command))
    # === Monster Battle Callbacks ===
    application.add_handler(CallbackQueryHandler(fight_monster, pattern=r"^fight_"))
    application.add_handler(CallbackQueryHandler(handle_character_attack, pattern=r"^attack_"))
    application.add_handler(CallbackQueryHandler(handle_retreat, pattern=r"^retreat_"))
    application.add_handler(CommandHandler("hinterval", hinterval))
    application.add_handler(CommandHandler("deposit", deposit))
    application.add_handler(CommandHandler("withdraw", withdraw))
    application.add_handler(CommandHandler("bank", bank))
    application.add_handler(CommandHandler("interest", trigger_interest_command))
    application.add_handler(CommandHandler("bankstats", bank_stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_message_for_spawn), group=1)
    application.add_handler(CommandHandler("resetmonster", resetmonster))
    application.add_handler(CommandHandler("resetdefeats", reset_defeats_command))
    application.add_handler(CommandHandler("test", test))

    print("👹 Monster battle & party system handlers registered!")
