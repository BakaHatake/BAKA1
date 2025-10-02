import os
import random
import sqlite3
import asyncio
from telegram.ext import CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

import os

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
def ensure_power_column():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Create table if it doesn't exist
        c.execute("""
            CREATE TABLE IF NOT EXISTS owned_characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                character_name TEXT NOT NULL,
                rarity INTEGER NOT NULL,
                count INTEGER DEFAULT 1,
                power INTEGER DEFAULT 0,
                obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Check if power column exists
        c.execute("PRAGMA table_info(owned_characters)")
        columns = [col[1] for col in c.fetchall()]
        if "power" not in columns:
            c.execute("ALTER TABLE owned_characters ADD COLUMN power INTEGER DEFAULT 0")
        conn.commit()

def update_character_powers():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Ensure table exists first
        c.execute("""
            CREATE TABLE IF NOT EXISTS owned_characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                character_name TEXT NOT NULL,
                rarity INTEGER NOT NULL,
                count INTEGER DEFAULT 1,
                power INTEGER DEFAULT 0,
                obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        for name, power in ALL_CHARACTERS["five_star"].items():
            c.execute("UPDATE owned_characters SET power = ? WHERE character_name = ? AND rarity = 5", (power, name))
        for name, power in ALL_CHARACTERS["four_star"].items():
            c.execute("UPDATE owned_characters SET power = ? WHERE character_name = ? AND rarity = 4", (power, name))
        conn.commit()

def ensure_gacha_columns():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
    
        c.execute("""
            CREATE TABLE IF NOT EXISTS gacha_state (
                user_id INTEGER PRIMARY KEY,
                pity_5 INTEGER DEFAULT 0,
                pity_4 INTEGER DEFAULT 0,
                last_5star TEXT,
                total_pulls INTEGER DEFAULT 0
            )
        """)
        
        # Check if columns exist before adding them
        c.execute("PRAGMA table_info(gacha_state)")
        columns = [col[1] for col in c.fetchall()]
        
        if "pity_4" not in columns:
            c.execute("ALTER TABLE gacha_state ADD COLUMN pity_4 INTEGER DEFAULT 0")
        
        # Add any other missing columns here if needed
        
        conn.commit()


ensure_gacha_columns()

def init_gacha_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            primogems INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS gacha_state (
            user_id INTEGER PRIMARY KEY,
            pity_4 INTEGER DEFAULT 0,
            pity_5 INTEGER DEFAULT 0,
            last_five_star TEXT DEFAULT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS owned_characters (
            user_id INTEGER,
            character_name TEXT,
            rarity INTEGER,
            constellation INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, character_name)
        )""")
        conn.commit()

def get_user_data(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO gacha_state (user_id) VALUES (?)", (user_id,))
        c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()

async def multiwish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_user_data(user_id)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT primogems FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        primos = row[0] if row else 0

        if primos < 1600:
            await update.message.reply_text("❌ Not enough primogems! You need 1600 primogems for a 10-pull.")
            return

        c.execute("UPDATE users SET primogems = primogems - 1600 WHERE user_id = ?", (user_id,))
        c.execute("SELECT pity_4, pity_5 FROM gacha_state WHERE user_id = ?", (user_id,))
        pity4, pity5 = c.fetchone()

        results = []
        for _ in range(10):
            pity5 += 1
            pity4 += 1
            base_5 = 0.006
            soft_pity = max(0, pity5 - 74) * 0.06
            chance_5 = base_5 + soft_pity
            roll = random.random()

            if roll < chance_5 or pity5 >= 90:
                name = random.choice(list(ALL_CHARACTERS["five_star"].keys()))
                results.append((name, 5))
                pity5 = 0
                c.execute("UPDATE gacha_state SET last_five_star = ? WHERE user_id = ?", (name, user_id))
            elif roll < 0.10 or pity4 >= 10:
                name = random.choice(list(ALL_CHARACTERS["four_star"].keys()))
                results.append((name, 4))
                pity4 = 0
            else:
                name = random.choice(THREE_STAR_POOL)
                results.append((name, 3))

        c.execute("UPDATE gacha_state SET pity_4 = ?, pity_5 = ? WHERE user_id = ?", (pity4, pity5, user_id))

        for name, rarity in results:
            if rarity >= 4:
                c.execute(
                    "SELECT constellation FROM owned_characters WHERE user_id = ? AND character_name = ?",
                    (user_id, name)
                )
                result = c.fetchone()
                if result:
                    current_const = result[0]
                    if current_const < 6:
                        # Update constellation
                        c.execute(
                            "UPDATE owned_characters SET constellation = constellation + 1 WHERE user_id = ? AND character_name = ?",
                            (user_id, name)
                        )
                        # Increase power based on rarity
                        if rarity == 5:
                            c.execute(
                                "UPDATE owned_characters SET power = power + 10 WHERE user_id = ? AND character_name = ?",
                                (user_id, name)
                            )
                        elif rarity == 4:
                            c.execute(
                                "UPDATE owned_characters SET power = power + 5 WHERE user_id = ? AND character_name = ?",
                                (user_id, name)
                            )
                else:
                    if rarity == 5:
                        power = ALL_CHARACTERS["five_star"].get(name, 0)
                    else:
                        power = ALL_CHARACTERS["four_star"].get(name, 0)
                    c.execute(
                        "INSERT INTO owned_characters (user_id, character_name, rarity, constellation, power) VALUES (?, ?, ?, 0, ?)",
                        (user_id, name, rarity, power)
                    )


    highest_rarity = max(rarity for _, rarity in results)
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
        except Exception as e:
            print(f"⚠️ Could not delete animation message: {e}")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        summary = []
        for name, rarity in results:
            constellation_text = ""
            if rarity >= 4:
                c.execute(
                    "SELECT constellation FROM owned_characters WHERE user_id = ? AND character_name = ?",
                    (user_id, name)
                )
                constellation = c.fetchone()[0]
                if constellation > 0:
                    constellation_text = f" (C{constellation})"
            summary.append(f"{'★'*rarity} {name}{constellation_text}")

    summary_text = "🎁 Wish Results:\n" + "\n".join(summary)

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

    if display_img:
        with open(display_img, "rb") as photo_file:
            await update.message.reply_photo(photo=photo_file, caption=summary_text)
    else:
        await update.message.reply_text(summary_text)



async def characters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT character_name, rarity, constellation FROM owned_characters WHERE user_id = ?", (user_id,))
        characters = c.fetchall()

    if not characters:
        await update.message.reply_text("😢 You don't own any characters yet.")
        return

    chars_by_rarity = {}
    for name, rarity, constellation in characters:
        chars_by_rarity.setdefault(rarity, []).append((name, constellation))

    msg = "📜 **Your Characters:**\n"
    for rarity in sorted(chars_by_rarity.keys(), reverse=True):
        msg += f"\n{'★'*rarity}  Characters:\n"
        for name, const in sorted(chars_by_rarity[rarity]):
            msg += f"• {name} C{const}\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def pity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_user_data(user_id)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT primogems FROM users WHERE user_id = ?", (user_id,))
        primos = c.fetchone()[0]

        c.execute("SELECT pity_4, pity_5, last_five_star FROM gacha_state WHERE user_id = ?", (user_id,))
        pity4, pity5, last_five_star = c.fetchone()

    msg = "🔮 **Wish Stats**\n\n"
    msg += f"💎 **Primogems:** {primos} ({primos//160} wishes)\n\n"
    msg += f"4★ Pity: {pity4}/10\n"
    msg += f"5★ Pity: {pity5}/90\n\n"
    msg += f"Last 5★: {last_five_star if last_five_star else 'None yet'}"

    await update.message.reply_text(msg, parse_mode="Markdown")



def register_gacha_handlers(application):
    # === Gacha Feature Handlers ===
    ensure_power_column()
    update_character_powers()
    application.add_handler(CommandHandler("multiwish", multiwish))
    application.add_handler(CommandHandler("characters", characters))
    application.add_handler(CommandHandler("pity", pity))
    print("🎲 Gacha + DB backup handlers registered!")
