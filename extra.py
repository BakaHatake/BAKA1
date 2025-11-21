# import random
# from pymongo import MongoClient

# client = MongoClient("mongodb+srv://bakahatake:anush%40123@bakabot.to9paey.mongodb.net/?appName=BAKABOT")
# db = client["Main"]
# harem = db["harem"]

# user_id = "6057581189"

# doc = harem.find_one({"user_id": user_id})
# if not doc:
#     print("No harem found")
#     exit()

# keys = [k for k in doc.keys() if k not in ["_id", "user_id", "Rarity", "Fav"]]

# remove_count = int(len(keys) * 0.6)
# to_remove = random.sample(keys, remove_count)

# unset_fields = {k: "" for k in to_remove}

# harem.update_one(
#     {"user_id": user_id},
#     {"$unset": unset_fields}
# )

# print("Removed:", to_remove)
# print(len(keys))
# print(keys)
import json
import sqlite3
from pymongo import MongoClient

# ---------------- MONGO SETUP ----------------
client = MongoClient("mongodb+srv://bakahatake:anush%40123@bakabot.to9paey.mongodb.net/?appName=BAKABOT")
db = client["Main"]
harem = db["harem"]

# ---------------- STEP 1: BACKUP MONGO HAREM ----------------
backup = list(harem.find({}))

for doc in backup:
    doc["_id"] = str(doc["_id"])

with open("harem_backup.json", "w", encoding="utf-8") as f:
    json.dump(backup, f, indent=4)

print("Backup saved as harem_backup.json")

# ---------------- STEP 2: CLEAR OLD MONGO DATA ----------------
harem.delete_many({})
print("Old Mongo harem cleared.")

# ---------------- STEP 3: LOAD SQLITE ----------------
sql_path = "quiz_backup (4) (2).db"   # <-- THE CORRECT FILE IN YOUR PROJECT FOLDER
conn = sqlite3.connect(sql_path)
cursor = conn.cursor()

# SHOW TABLES (DEBUG)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("SQLite tables:", cursor.fetchall())

# ---------------- STEP 4: LOAD FROM user_inventory ----------------
try:
    cursor.execute("SELECT user_id, char_id, stack_count FROM user_inventory;")
except Exception as e:
    print("ERROR: Could not read user_inventory table.")
    print(e)
    exit()

rows = cursor.fetchall()

# ---------------- STEP 5: BUILD NEW HAREM DOCS ----------------
harem_docs = {}

for user_id, char_id, stack in rows:
    user_id = str(user_id)
    char_id = str(char_id).zfill(3)

    if user_id not in harem_docs:
        harem_docs[user_id] = {"user_id": user_id}

    harem_docs[user_id][char_id] = stack

# ---------------- STEP 6: INSERT BACK TO MONGO ----------------
for doc in harem_docs.values():
    harem.insert_one(doc)

print("New harem imported successfully.")
print(f"Total users imported: {len(harem_docs)}")
