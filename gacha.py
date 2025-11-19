import os
import random
import sqlite3
import asyncio
from telegram.ext import CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

import os
from db import (
    ensure_gacha_user, get_pity, update_pity, update_last_five_star,
    get_character, add_character, increment_constellation, get_user_characters,
    get_primogems, update_primos
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


DB_PATH = "/mnt/data/quiz.db"
ANIMATION_PATH = os.path.join(os.path.dirname(__file__), "assets", "animation.mp4")


ALL_CHARACTERS = {
    "five_star": {
        "Albedo":60, "Alhaitham": 80, "Aloy": 60, "Arataki Itto": 60, "Arlecchino": 100,
        "Baizhu": 70, "Chiori": 60, "Clorinde": 80, "Cyno": 75,"Diluc":60, "Dehya": 65, "Escoffier":90,"Emilie": 70,
        "Eula": 65, "Furina": 100, "Ganyu": 70, "Hu Tao": 70, "Kaedehara Kazuha": 90,
        "Kamisato Ayaka": 70, "Kamisato Ayato": 70, "Kinich": 80, "Lyney": 70,
        "Nahida": 90, "Navia": 70, "Neuvillette": 100, "Nilou": 70,"Mavuika":110, "Raiden Shogun": 80,
        "Shenhe": 65,"Sangonomiya Kokomi":60, "Sigewinne": 60, "Tartaglia": 75, "Tighnari": 70,
        "Venti": 70, "Wanderer": 75, "Wriothesley": 80, "Xiao": 75,"Xilonen":80, "Xianyun": 70,
        "Yumemizuki Mizuki":70,"Yae Miko": 70, "Yelan": 80, "Yoimiya": 70, "Zhongli": 80,"Mualani":90,"Chasca":85,"Jean":70
        ,"Qiqi":10,"Mona":70,"Klee":70,
    },
    "four_star": {
        "Candace": 40, "Charlotte": 40, "Chevreuse": 40, "Collei": 40, "Dahlia": 40,
        "Diona": 40, "Dori": 40, "Faruzan": 40, "Freminet": 40, "Gaming": 40, "Ifa": 40,
        "Kachina": 40, "Kaveh": 40, "Kirara": 40, "Kujou Sara": 50, "Kuki Shinobu": 50,
        "Iansan": 60, "Layla": 40, "Lynette": 40, "Mika": 40, "Rosaria": 40, "Sayu": 40,
        "Sethos": 40, "Shikanoin Heizou": 40, "Thoma": 40, "Xinyan": 40, "Yanfei": 40,
        "Yaoyao": 40, "Yun Jin": 40,"Lisa":40,"Lan yan":50,"Amber":40,"Fiscl":40,"Xinqui":50,"Bennett":65,"Sucrose":40,
        "Xilanglang":60,"Niggauang":40,"Goruo":40,"Chongyun":40,"Noelle":50
    }
}


THREE_STAR_POOL = [
    "Cool Steel", "Harbinger of Dawn", "Thrilling Tales", "Sharpshooter's Oath",
    "Black Tassel", "Bloodtainted Greatsword", "Skyrider Sword", "Raven Bow",
    "Emerald Orb", "Ferrous Shadow", "Magic Guide", "Debate Club"
]


def get_user_data(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO gacha_state (user_id) VALUES (?)", (user_id,))
        c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()

async def multiwish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    ensure_gacha_user(user_id)

    primos = get_primogems(user_id)
    if primos < 1600:
        await update.message.reply_text("❌ Not enough primogems! You need 1600 for 10-pull.")
        return

    update_primos(user_id, -1600)

    pity4, pity5, last5 = get_pity(user_id)

    results = []

    for _ in range(10):
        pity4 += 1
        pity5 += 1

        base_5 = 0.006
        soft = max(0, pity5 - 74) * 0.06
        chance_5 = base_5 + soft

        roll = random.random()

        if roll < chance_5 or pity5 >= 90:
            name = random.choice(list(ALL_CHARACTERS["five_star"].keys()))
            rarity = 5
            pity5 = 0
            update_last_five_star(user_id, name)

        elif roll < 0.10 or pity4 >= 10:
            name = random.choice(list(ALL_CHARACTERS["four_star"].keys()))
            rarity = 4
            pity4 = 0

        else:
            name = random.choice(THREE_STAR_POOL)
            rarity = 3

        results.append((name, rarity))

    update_pity(user_id, pity4, pity5)

    for name, rarity in results:

        if rarity < 4:
            continue   

        char = get_character(user_id, name)

        if char:
            increment_constellation(user_id, name, rarity)
        else:
            power = ALL_CHARACTERS["five_star"].get(name) if rarity == 5 else ALL_CHARACTERS["four_star"].get(name)
            add_character(user_id, name, rarity, power)


    highest_rarity = max(r for _, r in results)

    if highest_rarity == 5:
        animation_path = os.path.join(BASE_DIR, "assets", "animations", "gold.mp4")
    elif highest_rarity == 4:
        animation_path = os.path.join(BASE_DIR, "assets", "animations", "purple.mp4")
    else:
        animation_path = os.path.join(BASE_DIR, "assets", "animations", "blue.mp4")

    try:
        with open(animation_path, "rb") as video_file:
            animation_msg = await update.message.reply_video(video=video_file)
    except FileNotFoundError:
        await update.message.reply_text("⚠️ Animation file missing.")
        animation_msg = None

    if animation_msg:
        await asyncio.sleep(3)
        try:
            await animation_msg.delete()
        except:
            pass

    display_img = None

    for name, rarity in results:
        if rarity == 5:
            for ext in ["png", "jpg", "jpeg"]:
                path = os.path.join(BASE_DIR, "assets", "characters", f"{name}.{ext}")
                if os.path.exists(path):
                    display_img = path
                    break
            if display_img:
                break

    if not display_img:
        for name, rarity in results:
            if rarity == 4:
                for ext in ["png", "jpg", "jpeg"]:
                    path = os.path.join(BASE_DIR, "assets", "characters", f"{name}.{ext}")
                    if os.path.exists(path):
                        display_img = path
                        break
                if display_img:
                    break

    summary = "🎁 Wish Results:\n"

    for name, rarity in results:
        const_suffix = ""
        if rarity >= 4:
            c = get_character(user_id, name)["constellation"]
            if c > 0:
                const_suffix = f" (C{c})"
        summary += f"{'★'*rarity} {name}{const_suffix}\n"

    if display_img:
        with open(display_img, "rb") as img:
            await update.message.reply_photo(photo=img, caption=summary)

    else:
        await update.message.reply_text(summary)


async def characters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    chars = get_user_characters(user_id)
    if not chars:
        await update.message.reply_text("😢 You don’t own any characters yet.")
        return

    msg = "📜 **Your Characters:**\n\n"

    sorted_chars = sorted(
        chars.items(),
        key=lambda x: (-x[1]["rarity"], x[0])
    )

    for name, data in sorted_chars:
        msg += f"{'★'*data['rarity']} {name} C{data['constellation']}\n"

    await update.message.reply_text(msg, parse_mode="Markdown")



async def pity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    ensure_gacha_user(user_id)

    pity4, pity5, last5 = get_pity(user_id)
    primos = get_primogems(user_id)

    msg = f"""
🔮 **Wish Stats**

💎 Primogems: {primos} ({primos//160} wishes)

4★ Pity: {pity4}/10
5★ Pity: {pity5}/90

Last 5★: {last5 or 'None yet'}
"""

    await update.message.reply_text(msg, parse_mode="Markdown")




def register_gacha_handlers(application):
    # === Gacha Feature Handlers ===

    application.add_handler(CommandHandler("multiwish", multiwish))
    application.add_handler(CommandHandler("characters", characters))
    application.add_handler(CommandHandler("pity", pity))
    print("🎲 Gacha + DB backup handlers registered!")
