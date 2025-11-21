from pymongo import MongoClient
from bson import objectid
from datetime import datetime
import time
from pymongo import ASCENDING, DESCENDING


client=MongoClient("mongodb+srv://bakahatake:anush%40123@bakabot.to9paey.mongodb.net/?appName=BAKABOT")

db=client["Main"]
inv=db["inv"]
bank=db["bank"]
harem=db["harem"]
counters=db["counters"]
drops=db["drops"]
shop=db["shop"]
spam=db['spam']
mines=db['mines']
paimonbox=db['paimonbox']
steals=db['steals']
clash=db['clash']
gacha = db["gacha"]
owned = db["owned_characters"]
pvp = db["pvp_users"]
monster_defeats = db["monster_defeats"] 
path = db["waifu_paths"]


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

def is_blocked(user_id)->bool:
    doc=spam.find_one({"user_id":str(user_id)})
    now=int(time.time())
    return bool(doc and doc.get("Block untill",0)>now)


def block_user(user_id):
    block=int(time.time())+10*60
    spam.update_one(
        {"user_id":str(user_id)},
        {"$set":{"Block untill":block,"Streak":0}},
        upsert=True
    )
def reset_streak(user_id):
    return spam.update_one(
        {"user_id": str(user_id)},
        {"$set": {"Streak": 0}}
    )


def increment_streak(user_id):
    now=int(time.time())
    doc=spam.find_one({"user_id":str(user_id)})

    if doc and doc.get("Block untill",0)>now:
        return False,False
    
    streak=doc.get("Streak",0)if doc else 0
    streak+=1

    spam.update_one(
        {"user_id":str(user_id)},
        {"$set":{"Streak":streak}},
        upsert=True
    )

    if streak>=10:
        block_user(user_id)
        return True,True
    
    return True,False

def unblock_user(user_id):
    spam.update_one(
        {"user_id": str(user_id)},
        {"$set": {"Block untill": 0, "Streak": 0}}
    )
    return True

def get_streak(user_id):
    doc=spam.find_one({"user_id":str(user_id)})
    return doc

def get_top_waifu_holders(limit=10):
    top = []

    for doc in harem.find({}, {"_id": 0}):
        user_id = doc.get("user_id")
        if not user_id:
            continue

        total = 0
        for k, v in doc.items():
            if k in ("user_id", "Rarity"):
                continue
            try:
                total += int(v)
            except:
                pass

        top.append((user_id, total))
    top.sort(key=lambda x: x[1], reverse=True)
    return top[:limit]

def update_mines(user_id,state):
    if state is None:
        mines.delete_one({"user_id":str(user_id)})
    else:
        mines.update_one(
            {"user_id":str(user_id)},
            {"$set":
            {"State":state},},
            upsert=True
        )

def get_user_state(user_id):
    doc = mines.find_one({"user_id": str(user_id)})
    return doc.get("State") if doc else None

def update_paimon_box(user_id,update=False):
    doc=paimonbox.find_one({"user_id":str(user_id)})
    today=datetime.now().strftime("%Y-%m-%d")
    if not doc or doc.get("Last used") != today:
        print("triggered1")
        paimonbox.update_one(
            {"user_id": str(user_id)},
            {"$set": {"Counts": 0, "Last used": today}},
            upsert=True
        )
        return 0
    elif update:
        print("triggered2")
        paimonbox.update_one({"user_id":str(user_id)},
                             {"$inc":{"Counts":1}},
                             )
    else:
        return doc.get("Counts",None)

def get_steal_doc(user_id):
    doc = steals.find_one({"user_id": str(user_id)})
    if not doc:
        doc = {"Mode": "On", "Locked": False, "Unlock": 0}
        steals.update_one(
            {"user_id": str(user_id)},
            {"$set": doc},
            upsert=True
        )
    return doc


def lock_steal_mode(user_id):
    now = int(time.time())
    steals.update_one(
        {"user_id": str(user_id)},
        {"$set": {
            "Mode": "Off",
            "Locked": True,
            "Unlock": now + 3600
        }},
        upsert=True
    )


def unlock_steal_mode(user_id):
    steals.update_one(
        {"user_id": str(user_id)},
        {"$set": {
            "Mode": "On",
            "Locked": False,
            "Unlock": 0
        }}
    )


def set_steal_mode(user_id, mode):
    steals.update_one(
        {"user_id": str(user_id)},
        {"$set": {"Mode": mode}}
    )
def unlock_expired_modes():
    now = int(time.time())

    expired = list(
        steals.find({
            "Locked": True,
            "Unlock": {"$lte": now}
        })
    )

    if not expired:
        return []

    user_ids = [doc["user_id"] for doc in expired]

    steals.update_many(
        {"user_id": {"$in": user_ids}},
        {"$set": {"Mode": "On", "Locked": False, "Unlock": 0}}
    )

    return user_ids

def get_top_users(key, limit=10):
    pipeline = [
        {"$project": {
            "user_id": 1,
            "value": f"${key}"
        }},
        {"$sort": {"value": -1}},
        {"$limit": limit}
    ]

    results = list(inv.aggregate(pipeline))

    for r in results:
        user = inv.find_one({"user_id": r["user_id"]})
        r["name"] = user.get("Name", f"User {r['user_id']}")

    return results

def update_id(user_id,id):
    return clash.update_one({"user_id":str(user_id)},
                     {"$set":{"id":id}},
                    upsert=True
                     )
def get_id(user_id):
    doc=clash.find_one({"user_id":str(user_id)})
    if doc is None:
        return None
    return doc.get("id",None)
    
def ensure_gacha_user(user_id):
    gacha.update_one(
        {"user_id": str(user_id)},
        {
            "$setOnInsert": {
                "pity_4": 0,
                "pity_5": 0,
                "last_five_star": None,
                "total_pulls": 0
            }
        },
        upsert=True
    )
def get_pity(user_id):
    doc = gacha.find_one({"user_id": str(user_id)})
    if not doc:
        ensure_gacha_user(user_id)
        doc = gacha.find_one({"user_id": str(user_id)})
    return doc["pity_4"], doc["pity_5"], doc.get("last_five_star")

def update_pity(user_id, pity4, pity5):
    gacha.update_one(
        {"user_id": str(user_id)},
        {"$set": {"pity_4": pity4, "pity_5": pity5}},
    )
def update_last_five_star(user_id, name):
    gacha.update_one(
        {"user_id": str(user_id)},
        {"$set": {"last_five_star": name}}
    )
def get_character(user_id, name):
    doc = owned.find_one({"user_id": str(user_id)})
    if not doc:
        return None
    return doc.get("characters", {}).get(name)
def add_character(user_id, name, rarity, power):

    try:
        rarity = int(rarity)
    except:
        return

    if rarity < 4:

        return

    owned.update_one(
        {"user_id": str(user_id)},
        {
            "$set": {
                f"characters.{name}": {
                    "rarity": rarity,
                    "power": power,
                    "constellation": 0
                }
            }
        },
        upsert=True
    )

def increment_constellation(user_id, name, rarity):
    try:
        rarity = int(rarity)
    except:
        return

    if rarity < 4:
        return

    inc_power = 10 if rarity == 5 else 5

    owned.update_one(
        {"user_id": str(user_id)},
        {
            "$inc": {
                f"characters.{name}.constellation": 1,
                f"characters.{name}.power": inc_power
            }
        }
    )

def get_user_characters(user_id):
    doc = owned.find_one({"user_id": str(user_id)})
    if not doc:
        ensure_owned_doc(user_id)
        return {}
    return doc.get("characters", {})


def ensure_owned_doc(user_id):
    owned.update_one(
        {"user_id": str(user_id)},
        {"$setOnInsert": {"characters": {}}},
        upsert=True
    )
def list_characters(user_id):
    chars = get_user_characters(user_id)
    arr = []
    for name, data in chars.items():
        arr.append({
            "name": name,
            "rarity": data["rarity"],
            "constellation": data["constellation"],
            "power": data["power"]
        })
    return arr



quiz_questions = db["quiz_questions"]
quiz_scores = db["quiz_scores"]
quiz_meta = db["quiz_meta"] 
quiz_clash = db["quiz_clash"] 
quiz_questions = db["quiz_questions"]

def insert_question_doc(question_text: str, options_str: str, answer: str):
    doc = {
        "question": question_text,
        "options": options_str,
        "answer": answer,
        "created_at": datetime.utcnow()
    }
    quiz_questions.insert_one(doc)
    return doc

def get_random_question():
    doc = list(quiz_questions.aggregate([{"$sample": {"size": 1}}]))
    if not doc:
        return None
    d = doc[0]
    return (str(d["_id"]), d["question"], d["options"], d["answer"])

def get_question_by_id(qid):
    from bson import ObjectId
    try:
        return quiz_questions.find_one({"_id": ObjectId(qid)})
    except:
        return None


def get_random_question():
    doc = list(quiz_questions.aggregate([{"$sample": {"size": 1}}]))
    if not doc:
        return None
    d = doc[0]
    return (str(d.get("_id")), d.get("question"), d.get("options"), d.get("answer"))

def get_all_questions():
    return list(quiz_questions.find({}, {"question":1, "options":1, "answer":1}))

def delete_question_by_id(qid):

    try:
        from bson import ObjectId
        oid = ObjectId(qid)
    except:
        return None
    return quiz_questions.delete_one({"_id": oid})

def update_score_db(user_id, username, increment=1):
    quiz_scores.update_one(
        {"user_id": str(user_id)},
        {
            "$setOnInsert": {"username": username},
            "$inc": {"points": increment}
        },
        upsert=True
    )

def get_leaderboard_db(limit=10):
    docs = list(quiz_scores.find({}, {"user_id":1, "username":1, "points":1}).sort("points", DESCENDING).limit(limit))

    return [(d.get("username") or f"id_{d['user_id']}", d.get("points",0), d.get("user_id")) for d in docs]

def reset_scores_and_reward_top(rewards=[1600, 1000, 500], owner_notify_id=None):

    top = list(quiz_scores.find({}, {"user_id":1, "username":1, "points":1}).sort("points", DESCENDING).limit(len(rewards)))
    rewarded = []
    for i, doc in enumerate(top):
        uid = doc.get("user_id")
        uname = doc.get("username")
        pts = doc.get("points", 0)
        amount = rewards[i]
        try:
            update_primos(uid, amount)
        except Exception:
            update_primos(int(uid), amount)
        rewarded.append((uid, uname, pts, amount))

    quiz_scores.delete_many({})
    return rewarded

def update_clash_points_db(user_id, username, points=1):
    quiz_clash.update_one(
        {"user_id": str(user_id)},
        {"$setOnInsert": {"username": username}, "$inc": {"points": points}},
        upsert=True
    )

def get_clash_leaderboard_db(limit=10):
    docs = list(quiz_clash.find({}, {"user_id":1, "username":1, "points":1}).sort("points", DESCENDING).limit(limit))
    return [(d.get("user_id"), d.get("username"), d.get("points",0)) for d in docs]

authorized = db["authorized_users"]

def is_authorized(uid):
    return authorized.count_documents({"user_id": str(uid)}, limit=1) > 0

def add_authorized(uid):
    authorized.update_one({"user_id": str(uid)}, {"$set": {}}, upsert=True)

def get_authorized_users():
    return [doc["user_id"] for doc in authorized.find({}, {"_id": 0, "user_id": 1})]
def get_user_party(user_id):
    doc = pvp.find_one({"user_id": str(user_id)}, {"_id": 0, "party": 1})
    return doc.get("party", []) if doc else []


def save_user_party(user_id, party_list):
    pvp.update_one(
        {"user_id": str(user_id)},
        {"$set": {"party": party_list}},
        upsert=True
    )

def get_defeats_today(user_id):
    doc = pvp.find_one({"user_id": str(user_id)}, {"_id": 0, "defeats_today": 1})
    return doc.get("defeats_today", 0) if doc else 0


def set_defeats_today(user_id, value):
    pvp.update_one(
        {"user_id": str(user_id)},
        {"$set": {"defeats_today": value}},
        upsert=True
    )


def reset_daily_defeats():
    pvp.update_many({}, {"$set": {"defeats_today": 0}})
def increment_monster_kill(user_id, monster_name):
    monster_defeats.update_one(
        {"user_id": str(user_id), "monster": monster_name},
        {"$inc": {"count": 1}},
        upsert=True
    )


def get_user_monster_kills(user_id):
    docs = monster_defeats.find({"user_id": str(user_id)}, {"_id": 0})
    return list(docs)
def get_monsterboard_top(limit=10):
    pipeline = [
        {"$group": {
            "_id": "$user_id",
            "total_kills": {"$sum": "$count"}
        }},
        {"$sort": {"total_kills": -1}},
        {"$limit": limit}
    ]

    results = list(monster_defeats.aggregate(pipeline))
    out = []

    for r in results:
        user_id = r["_id"]
        total = r["total_kills"]

        # fetch username from your inv/users collection
        user = inv.find_one({"user_id": user_id})
        name = user.get("Name", f"User {user_id}")

        out.append((user_id, name, total))

    return out
def reset_monster_season():
    monster_defeats.delete_many({})
def get_user_path(user_id):
    return path.find_one({"user_id": str(user_id)})
def set_user_path(user_id, waifu_id):
    path.update_one(
        {"user_id": str(user_id)},
        {"$set": {"waifu_id": waifu_id, "pity": 0}},
        upsert=True
    )
def clear_user_path(user_id):
    path.update_one(
        {"user_id": str(user_id)},
        {"$unset": {"waifu_id": "", "pity": ""}}
    )

def increment_pity(user_id):
    path.update_one(
        {"user_id": str(user_id)},
        {"$inc": {"pity": 1}}
    )
def get_setwaifu_count(user_id):
    doc = path.find_one({"user_id": str(user_id)}, {"usage_count": 1, "last_used": 1})
    if not doc:
        return 0
    
    today = datetime.now().strftime("%Y-%m-%d")
    if doc.get("last_used") != today:
        path.update_one(
            {"user_id": str(user_id)},
            {"$set": {"usage_count": 0, "last_used": today}},
            upsert=True
        )
        return 0

    return doc.get("usage_count", 0)
def increment_setwaifu_count(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    path.update_one(
        {"user_id": str(user_id)},
        {
            "$inc": {"usage_count": 1},
            "$set": {"last_used": today}
        },
        upsert=True
    )
import random

def roll_for_path_waifu(user_id, waifu_id):
    doc = get_user_path(user_id)
    pity = doc.get("pity", 0)

    chance = 10 + (pity * 9)  

    return random.randint(1, 100) <= chance
def get_all_users_ids():
    return [doc["user_id"] for doc in inv.find({}, {"user_id": 1, "_id": 0})]
