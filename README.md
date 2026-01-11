🚀 BakaBot - A Genshin Impact Telegram Bot
Welcome to BakaBot, a feature-rich Telegram bot designed for Genshin Impact communities. BakaBot brings a variety of interactive games and social features to your Telegram group, from collecting waifus and battling monsters to engaging in quizzes and mini-games..

##📖 Table of Contents

-[About](#-about)

-[Features](#-Features)

-[Installation](#️-installation)

-[Usage](#-Usage)

## 📌 About

BakaBot is a comprehensive, multi-module Python bot built using the python-telegram-bot library. It integrates a wide array of game-like functionalities to create a lively and interactive experience for users in a Telegram group. The bot uses a SQLite database to persist user data, collections, and game states, and Cloudinary for hosting character images. The entire system is powered by an in-game currency system featuring Primogems, Mora, and Lunar Crystals.

## ✨ Features

✅ Character Collection (Harem): Collect a vast roster of characters (waifus) with different rarities. View your collection, set favorites, and trade with others.

✅ Gacha System: Use Primogems to wish for new characters, featuring a pity system for 4-star and 5-star pulls.

✅ Player vs. Monster (PvE): Form a party of your collected characters and fight monsters that randomly spawn in the chat.

✅ Economy & Shop: Earn and spend multiple in-game currencies. A daily rotating shop allows you to purchase characters using Lunar Crystals.

✅ Interactive Quizzes: Participate in Genshin Impact lore quizzes that appear automatically in the chat or can be started manually.

✅ Mini-Games: A collection of fun, competitive games to play with other users, including Mines, Dice, Coin Flip, Darts, Tic-Tac-Toe, and Rock-Paper-Scissors.

✅ Social Features: Gift characters, trade waifus, and compete on various leaderboards.

✅ Profile Cards: Integrate with Enka.Network to generate and display your Genshin Impact profile cards directly in chat.

✅ Admin Management: A suite of admin-only commands to manage the bot, add characters, moderate users, and back up data.

## ⚙️ Installation

Prerequisites
You'll need Python 3 installed, along with the required libraries.

Python 3.x

pip (Python package installer)

Steps
Clone the Repository

git clone [https://github.com/BakaHatake/BAKA1.git](https://github.com/BakaHatake/BAKA1.git)
cd REPO

Install Dependencies

pip install python-telegram-bot Pillow cloudinary enkanetwork aiohttp requests apscheduler pytz

Set Up Bot Token
Open bakabot.py and replace the placeholder TOKEN with your bot token from BotFather.

TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

Configure Cloudinary
The bot uses Cloudinary to manage images. Add your credentials in harem.py.

cloudinary.config(
    cloud_name='your_cloud_name',
    api_key='your_api_key',
    api_secret='your_api_secret'
)

Run the Bot
The database will be created automatically on the first run.

python bakabot.py

## 🎮 Usage

BakaBot offers a wide variety of commands. Here are some of the most common ones:

Main Commands
/start: Get a welcome message from the bot.

/myc: View your Genshin Impact profile card. Set your UID first.

/inv: Check your currency balance (Primogems, Mora, Lunar Crystals).

Gacha & Character Collection
/wish <name>: Attempt to claim a character that has just appeared in the chat.

/multiwish: Perform a 10-pull from the gacha banner.

/harem: View your collected character harem.

/fav <id>: Set a character as your favorite for your harem display.

/gift <id> (in reply): Gift a character to another user.

/trade <sending_id> <receiving_id> (in reply): Initiate a trade with another user.

/shop: View the daily rotating character shop.

/setwaifu <id>: Set a "wish path" to a specific character you want to obtain.

/waifu: Spend Lunar Crystals for a chance to get your targeted waifu.

Games
/quiz: Manually start a Genshin Impact quiz.

/leaderboard: View the quiz leaderboard.

/party: Create or edit your party of characters for monster battles.

/mines <bet> <bombs>: Start a game of Mines.

/steal (in reply): Attempt to steal primogems from another user.

/tic <bet> (in reply): Challenge someone to a game of Tic-Tac-Toe.

/rps <bet> (in reply): Challenge someone to Rock-Paper-Scissors.

Admin Commands
/addchar: Start the process to add a new character to the database.

/delete <id>: Delete a character from the game.

/add <user_id/reply> <amount> [currency]: Give currency to a user.

/monster: Manually spawn a monster in the chat.

/backupdb: Get a backup of the bot's database.

/restoredb (in reply to file): Restore the database from a backup file.
