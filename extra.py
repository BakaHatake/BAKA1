import random
from pymongo import MongoClient

client = MongoClient("mongodb+srv://bakahatake:anush%40123@bakabot.to9paey.mongodb.net/?appName=BAKABOT")
db = client["Main"]
harem = db["harem"]

user_id = "5192424390"

doc = harem.find_one({"user_id": user_id})
if not doc:
    print("No harem found")
    exit()

keys = [k for k in doc.keys() if k not in ["_id", "user_id", "Rarity", "Fav"]]

remove_count = int(len(keys) * 0.6)
to_remove = random.sample(keys, remove_count)

unset_fields = {k: "" for k in to_remove}

harem.update_one(
    {"user_id": user_id},
    {"$unset": unset_fields}
)

print("Removed:", to_remove)
