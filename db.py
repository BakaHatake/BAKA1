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
shop=db["shop"]

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
        {"$setOnInsert": {"Balance": 0}},
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
    return doc
    
def get_harem_doc(user_id):
    return harem.find_one({"user_id": str(user_id)})


def user_has_character(user_id, char_id):
    doc = get_harem_doc(user_id)
    if not doc:
        return False
    return doc.get(char_id, 0) > 0


def decrement_character(user_id, char_id):
    harem.update_one(
        {"user_id": str(user_id)},
        {"$inc": {char_id: -1}}
    )

    doc = get_harem_doc(user_id)
    if doc.get(char_id, 0) <= 0:
        harem.update_one(
            {"user_id": str(user_id)},
            {"$unset": {char_id: ""}}
        )


def increment_character(user_id, char_id):

    harem.update_one(
        {"user_id": str(user_id)},
        {"$inc": {char_id: 1}},
        upsert=True
    )


def transfer_character(sender_id, receiver_id, char_id):
    if not user_has_character(sender_id, char_id):
        return False
    decrement_character(sender_id, char_id)
    increment_character(receiver_id, char_id)

    return True

def update_shop(user_id, waifus, date):
    return shop.update_one(
        {"user_id": str(user_id)},
        {
            "$set": {
                "Waifus": waifus,
                "Refreshes": 0,
                "Rolls": 0,
                "Rolled ids":[],
                "Last Updated": date
            }
        },
        upsert=True
    )
def refresh_shop(user_id,waifus):
    return shop.update_one(
        {"user_id":str(user_id)},
        {
        "$set":{"Waifus":waifus,},
        "$inc":{"Refreshes":1},
        },
        upsert=True
    )
def get_shop(user_id):
    doc=shop.find_one({"user_id":str(user_id)})
    if not doc:
        return None
    date=doc.get("Last Updated",0)
    today = datetime.now().strftime("%Y-%m-%d")
    if date!=today:
        return None
    else:
        return doc
    
def record_roll(user_id, waifu_id, reset=False):
    if reset:
        return shop.update_one(
            {"user_id": str(user_id)},
            {
                "$set": {
                    "Rolled ids": [],
                    "Rolls": 0,
                    "Refreshes": 0
                }
            }
        )
    else:
        return shop.update_one(
            {"user_id": str(user_id)},
            {
                "$push": {"Rolled ids": waifu_id},
                "$inc": {"Rolls": 1}
            },
            upsert=True
        )
    
def set_fav(user_id,waifu_id):
    return harem.update_one(
        {"user_id":str(user_id)},
        {"$set":{"Fav":waifu_id}},
        upsert=True
    )

def get_fav(user_id):
    doc=harem.find_one({"user_id":str(user_id)})
    if not doc:
        return None
    else:
        return doc.get("Fav",None)
    
def who_collected(char_id,limit:int=10):
    char_id=str(char_id).zfill(3)

    pipeline=[
        {"$match":{char_id:{"$exists":True}}},
        {
            "$project":{
                "_id":0,
                "user_id":1,
                "stack_count":f"${char_id}"
            }
        },
        {"$limit":limit}
    ]
    return list(harem.aggregate(pipeline))

def update_name(user_id,name):
    return inv.update_one(
        {"user_id":str(user_id)},
        {
            "$set":{"Name":str(name)}
        },
        upsert=True
    )

