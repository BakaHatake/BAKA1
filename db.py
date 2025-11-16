from pymongo import MongoClient
from bson import objectid
from datetime import datetime
client=MongoClient("mongodb+srv://bakahatake:anush%40123@bakabot.to9paey.mongodb.net/?appName=BAKABOT")
db=client["Main"]

inv=db["inv"]
bank=db["bank"]
harem=db["harem"]
counters=db["counters"]
drops=db["drops"]

def update_inv(user_id,primogems=0,mora=0,lunar_crystals=0):
    return inv.update_one(
        {"user_id":str(user_id)},
        {
            "$inc":{
                "Primogems":primogems,
                "Mora":mora,
                "Lunar Crystals":lunar_crystals,
            }
        },
        upsert=True
    )
def user_exists(user_id):
    return inv.count_documents({"user_id": str(user_id)}, limit=1) > 0

def get_daily(user_id):
    user=inv.find_one({"user_id":str(user_id)})
    if not user:
        return None
    return user.get("Last Claim")


def update_claim(user_id):
    today=datetime.now().strftime('%Y-%m-%d')
    inv.update_one(
        {"user_id":str(user_id)},
        {"$set":{"Last Claim":today}},
        upsert=True
    )

def ensure_bank(user_id):
    bank.update_one(
        {"user_id": str(user_id)},
        {"$setOnInsert": {"balance": 0}},
        upsert=True
    )
def get_bank(user_id):
    doc = bank.find_one({"user_id": str(user_id)})
    return doc.get("Balance", 0) if doc else 0

def get_primogems(user_id):
    doc = inv.find_one({"user_id": str(user_id)})
    return doc.get("Primogems", 0) if doc else 0

def get_balance(user_id, key):
    doc = inv.find_one({"user_id": str(user_id)})
    if not doc:
        return 0
    return doc.get(key, 0)


def update_balance(user_id, key, amount):
    return inv.update_one(
        {"user_id": str(user_id)},
        {"$inc": {key: amount}},
        upsert=True
    )

def update_primos(user_id,value):
    return inv.update_one(
        {"user_id":str(user_id)},
        {"$inc":{"Primogems":value}},
        upsert=True
    )


def update_bank(user_id,value):
    return bank.update_one(
        {"user_id":str(user_id)},
        {"$inc":{"Balance":value}},
        upsert=True
    )

def update_counters(chat_id, key, value,reset=False):
    if key == "Interval":
        return counters.update_one(
            {"Chat id": str(chat_id)},
            {"$set": {key: value}},
            upsert=True
        )
    if reset:
        return counters.update_one(
            {"Chat id":str(chat_id)},
            {"$set":{key:value}},
            upsert=True
        )
    else:
        return counters.update_one(
            {"Chat id": str(chat_id)},
            {"$inc": {key: value}},
            upsert=True
        )


def get_counters(chat_id,key):
    doc=counters.find_one({"Chat id":str(chat_id)})
    if not doc:
        return 0
    return doc.get(key,0)

def update_drops(chat_id,char_id,char_name,rarity,image_path):
    return drops.update_one(
        {"Chat id":str(chat_id)},
        {
        "$set":{
        "Char name":str(char_name),
        "Char id":str(char_id),
        "Rarity":str(rarity),
        "Image path":str(image_path),
        }
        },
        upsert=True
    )
def clear_active_drop(chat_id: int):
    return drops.delete_one({"Chat id": str(chat_id)})

def get_drops(chat_id):
    doc=drops.find_one({"Chat id":str(chat_id)})
    return doc

def update_harem(user_id, char_id, count, rarity, replace=False):

    if replace:
        return harem.update_one(
            {"user_id": str(user_id)},
            {"$set": {
                "Rarity": rarity,
            }},
            upsert=True
        )

    else:
        return harem.update_one(
            {"user_id": str(user_id)},
            {"$inc": {char_id: count}},
            upsert=True
        )
    
def get_harem_rarity(user_id):
    doc=harem.find_one({"user_id":str(user_id)})
    return doc.get("Rarity",None)


def get_harem(user_id):
    doc=harem.find_one({"user_id":str(user_id)})
    doc.pop("_id", None)
    doc.pop("user_id", None)
    doc.pop("Rarity", None)
    print(doc)
    return doc
    