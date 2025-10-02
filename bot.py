import os
import tempfile
from types import SimpleNamespace
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from enkanetwork import EnkaNetworkAPI
from enkacard.encbanner import ENC

user_uid_map = {}
user_cache = {}
user_template_settings = {}


# === PATCH ICON FALLBACKS ===
def patch_enka_user(player):
    if not player:
        return

    if getattr(player, "avatar", None) is None:
        player.avatar = SimpleNamespace(icon=SimpleNamespace(
            filename="UI_AvatarIcon_PlayerBoy",
            url="https://enka.network/ui/UI_AvatarIcon_PlayerBoy.png"
        ))
    else:
        icon_obj = getattr(player.avatar, "icon", None)
        if icon_obj is None:
            player.avatar.icon = SimpleNamespace(
                filename="UI_AvatarIcon_PlayerBoy",
                url="https://enka.network/ui/UI_AvatarIcon_PlayerBoy.png"
            )
        elif getattr(icon_obj, "filename", None):
            player.avatar.icon.url = f"https://enka.network/ui/{icon_obj.filename}.png"

    for char in getattr(player, "characters", []):
        icon_obj = getattr(char, "icon", None)
        if icon_obj and getattr(icon_obj, "filename", None):
            icon_obj.url = f"https://enka.network/ui/{icon_obj.filename}.png"


# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Use /myc to view your Genshin Impact profile.")


# === /myc ===
async def myc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_uid_map:
        await update.message.reply_text("🔢 Please send your Genshin UID.")
        context.user_data["awaiting_uid"] = True
        return
    uid = user_uid_map[user_id]
    await generate_profile_card(update, context, uid)


# === UID input handler ===
async def handle_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_uid"):
        return
    uid_text = update.message.text.strip()
    if not uid_text.isdigit():
        await update.message.reply_text("❌ Invalid UID. Use digits only.")
        return
    user_uid_map[update.effective_user.id] = uid_text
    context.user_data["awaiting_uid"] = False
    await update.message.reply_text(f"✅ UID set to {uid_text}. Fetching your profile...")
    await generate_profile_card(update, context, uid_text)


# === /template ===
async def template_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Profile Template", callback_data="choose_profile_template")],
        [InlineKeyboardButton("🃏 Card Template", callback_data="choose_card_template")]
    ])
    await update.message.reply_text("⚙️ Choose what to customize:", reply_markup=keyboard)


# === Profile Template Selector ===
async def profile_template_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧩 Profile Template 1", callback_data="profile_template_1")],
        [InlineKeyboardButton("🧩 Profile Template 2", callback_data="profile_template_2")]
    ])
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("📄 Choose a profile template:", reply_markup=keyboard)


# === Card Template Selector ===
async def card_template_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🃏 Card Template {i}", callback_data=f"card_template_{i}")]
        for i in range(1, 6)
    ])
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("🃏 Choose a card template:", reply_markup=keyboard)


# === Store Template Choice ===
async def store_template_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    parts = query.data.split("_")
    category = parts[0]  # 'profile' or 'card'
    template_num = int(parts[-1])

    if user_id not in user_template_settings:
        user_template_settings[user_id] = {}

    user_template_settings[user_id][category] = template_num
    await query.message.reply_text(f"✅ {category.capitalize()} template set to {template_num}!")


# === Generate profile overview + buttons ===
async def generate_profile_card(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: str):
    message = await update.message.reply_text("⏳ Fetching profile from Enka.Network...")

    try:
        async with EnkaNetworkAPI() as client:
            await client.set_language("en")
            user = await client.fetch_user_by_uid(int(uid))

        if not user.characters:
            await message.edit_text("⚠️ No public characters found or profile is private.")
            return

        patch_enka_user(user.player)
        user_cache[update.effective_user.id] = user
        await message.edit_text("🖼 Generating profile card...")

        # Fetch user profile template setting (default to 1)
        template_profile = user_template_settings.get(update.effective_user.id, {}).get("profile", 1)

        async with ENC(uid=uid, lang="en") as encard:
            profile = await encard.profile(card=True, teamplate=template_profile)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image_path = tmp.name
            profile.card.save(image_path)

            # Build character selection keyboard
            keyboard = []
            row = []
            for idx, char in enumerate(user.characters[:12]):
                button = InlineKeyboardButton(char.name, callback_data=f"char_{char.id}")
                row.append(button)
                if (idx + 1) % 4 == 0:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send profile card image with caption and character selection keyboard
            with open(image_path, "rb") as f:
                await update.message.reply_photo(
                    photo=f,
                    caption=f"📋 UID {uid} Profile\n\nChoose a character:",
                    reply_markup=reply_markup
                )

            os.remove(image_path)
    except Exception as e:
        await message.edit_text(f"🚫 Failed to fetch profile:\n{e}")


# === Character Build Handler ===
async def character_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    uid = user_uid_map.get(user_id)

    if not uid:
        return await query.message.edit_text("❌ UID not found. Please run /myc again.")

    try:
        template_card = user_template_settings.get(user_id, {}).get("card", 1)

        async with ENC(uid=uid, lang="en") as encard:
            result = await encard.creat(template=template_card)

        char_id_from_button = int(query.data.split("_")[1])
        card_obj = next((c for c in result.card if c.id == char_id_from_button), None)

        if not card_obj or card_obj.card is None:
            return await query.message.edit_text("⚠️ No image found for that character.")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image_path = tmp.name
            card_obj.card.save(image_path)

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_characters")]
        ])

        with open(image_path, "rb") as f:
            await query.message.edit_media(
                media=InputMediaPhoto(f, caption=f"🔧 Build: {card_obj.name}"),
                reply_markup=reply_markup
            )
        os.remove(image_path)

    except Exception as e:
        await query.message.edit_text(f"🚫 Failed to generate character build.\nError: {e}")


async def back_to_characters_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    uid = user_uid_map.get(user_id)
    user = user_cache.get(user_id)
    if not uid or not user:
        return await query.message.edit_text("❌ Please fetch your profile first using /myc.")

    try:
        # Fetch user's profile template setting (default to 1)
        template_profile = user_template_settings.get(user_id, {}).get("profile", 1)

        async with ENC(uid=uid, lang="en") as encard:
            profile = await encard.profile(card=True, teamplate=template_profile)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image_path = tmp.name
            profile.card.save(image_path)
        keyboard = []
        row = []
        for idx, char in enumerate(user.characters[:12]):
            button = InlineKeyboardButton(char.name, callback_data=f"char_{char.id}")
            row.append(button)
            if (idx + 1) % 4 == 0:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        reply_markup = InlineKeyboardMarkup(keyboard)

        with open(image_path, "rb") as f:
            await query.message.edit_media(
                media=InputMediaPhoto(f, caption=f"📋 UID {uid} Profile\n\nChoose a character:"),
                reply_markup=reply_markup
            )
        os.remove(image_path)
    except Exception as e:
        await query.message.edit_text(f"🚫 Failed to re-generate profile card.\nError: {e}")
# === Run Bot ===
def register_profile_bot_handlers(application):
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myc", myc))
    application.add_handler(CommandHandler("template", template_menu))

    # Register message handler for UID input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_uid))

    # Register callback query handlers
    application.add_handler(CallbackQueryHandler(character_callback, pattern=r"^char_\d+$"))
    application.add_handler(CallbackQueryHandler(profile_template_selector, pattern="^choose_profile_template$"))
    application.add_handler(CallbackQueryHandler(card_template_selector, pattern="^choose_card_template$"))
    application.add_handler(CallbackQueryHandler(store_template_choice, pattern="^(profile|card)_template_\\d+$"))
    application.add_handler(CallbackQueryHandler(back_to_characters_callback, pattern="^back_to_characters$"))

    print("✨ Profile bot handlers registered!")


