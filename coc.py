import requests

api_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjY3NDg1YjJlLTVkYWItNDM0My04NDM2LTg3MGUyOTM4MWIzZSIsImlhdCI6MTc2MzU1Nzk2Niwic3ViIjoiZGV2ZWxvcGVyLzJmZGVkZDRiLWUxMGUtMWYwZC1jY2JhLTU0MWNmYTQ2MDYyZCIsInNjb3BlcyI6WyJjbGFzaCJdLCJsaW1pdHMiOlt7InRpZXIiOiJkZXZlbG9wZXIvc2lsdmVyIiwidHlwZSI6InRocm90dGxpbmcifSx7ImNpZHJzIjpbIjIyMy4yMzcuMTYyLjE5MyJdLCJ0eXBlIjoiY2xpZW50In1dfQ.EITJ3Qrof0b-wFqOSRotIoGHDpbEqEYtBL-eWuuYrejwU_tBoUR31MNgxB_BS_lwnWNLAjsHQxudI6cEhiQPBA"


def get_info(tag,api_token):


    url=f"https://api.clashofclans.com/v1/players/%23{tag}"
    headers={
        "Accept":"application/json",
        "Authorization":f"Bearer {api_token}"
    }

    response=requests.get(url,headers=headers)
    if response.status_code==200:
        return response.json()
    else:
        print("Error:", response.status_code, response.text)
        return None


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove, ForceReply
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, CallbackContext, ConversationHandler
import requests
from db import update_id,get_id

async def scoc(update,context):
    user_id=update.effective_user.id

    if len(context.args)==0:
        await update.message.reply_text("Please provide a player tag.\nExample: /scoc PJJ0VPQUR")
        return
    tag=context.args[0].upper().replace("#","")
    update_id(user_id,tag)
    await update.message.reply_text(f"Saved your Clash of Clans tag: {tag}")

async def coc(update, context):
    chat_id = update.effective_user.id

    tag = get_id(chat_id)
    if tag is None:
        await update.message.reply_text("No tag saved. Use /scoc <tag> first.")
        return

    data = get_info(tag, api_token)
    if not data:
        await update.message.reply_text("Failed to fetch profile. API error.")
        return

    name = data.get("name")
    th = data.get("townHallLevel")
    bh = data.get("builderHallLevel")
    exp = data.get("expLevel")
    trophies = data.get("trophies")
    best_trophies = data.get("bestTrophies")
    war_stars = data.get("warStars")
    role = data.get("role", "N/A")
    clan = data.get("clan", {}).get("name", "No Clan")
    clan_lvl = data.get("clan", {}).get("clanLevel", "N/A")
    league = data.get("leagueTier", {}).get("name", "Unranked")
    donations = data.get("donations", 0)
    received = data.get("donationsReceived", 0)

    hero_html = ""
    for h in data.get("heroes", []):
        hero_html += f"• <b>{h['name']}</b>: {h['level']}/{h['maxLevel']}\n"

    msg = f"""
<b>Clash of Clans Profile</b>

<b>Name:</b> {name}
<b>Town Hall:</b> {th}
<b>Builder Hall:</b> {bh}
<b>XP Level:</b> {exp}

<b>Trophies:</b> {trophies}
<b>Best Trophies:</b> {best_trophies}
<b>War Stars:</b> {war_stars}
<b>League:</b> {league}

<b>Clan:</b> {clan} (Lvl {clan_lvl})
<b>Role:</b> {role}

<b>Donations:</b> {donations}
<b>Received:</b> {received}

<b>Heroes:</b>
{hero_html}
"""

    await update.message.reply_text(msg, parse_mode="HTML")




def register_coc_handlers(application):
        application.add_handler(CommandHandler("scoc", scoc))
        application.add_handler(CommandHandler("coc", coc))
