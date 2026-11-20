# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ

import asyncio
import hashlib
import logging

import pymongo
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS, OTHER_DB_URI, DATABASE_NAME

logger = logging.getLogger(__name__)

NOTICE_DEBUG = False  # পরীক্ষা শেষে False করুন


async def _dbg(msg, text):
    if not NOTICE_DEBUG or not ADMINS:
        return
    try:
        await msg._client.send_message(ADMINS[0], "🐞 " + text)
    except Exception as e:
        logger.warning(f"debug send error: {e}")

# ---------- ডাটাবেস ----------
_col = pymongo.MongoClient(OTHER_DB_URI)[DATABASE_NAME]["FILE_NOTICES"]


def add_notice(keyword, text):
    keyword = keyword.strip()
    _col.update_one(
        {"_id": keyword.lower()},
        {"$set": {"keyword": keyword, "text": text}},
        upsert=True,
    )


def delete_notice(keyword):
    res = _col.delete_one({"_id": keyword.strip().lower()})
    return res.deleted_count > 0


def list_notices():
    return list(_col.find({}, {"_id": 0}))


def get_notice(file_name):
    """ফাইলের নামে সবচেয়ে লম্বা মিলে যাওয়া কী-ওয়ার্ডের নোটিশ দেয়।"""
    if not file_name:
        return None
    name = file_name.lower()
    best = None
    for doc in _col.find({}, {"_id": 0, "keyword": 1, "text": 1}):
        kw = doc["keyword"].lower()
        if kw in name and (best is None or len(kw) > len(best["keyword"])):
            best = doc
    return best["text"] if best else None


# ---------- ফাইলের সাথে নোটিশ পাঠানো ----------
async def _delete_later(message, delay):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


def _candidate_names(msg, name):
    """ফাইলের আসল নাম, ক্যাপশন ও দেওয়া নাম — কী-ওয়ার্ড খোঁজার জন্য সব সম্ভাব্য নাম।"""
    names = []
    try:
        for attr in ("document", "video", "audio", "animation", "voice", "video_note"):
            media = getattr(msg, attr, None)
            if media:
                names.append(getattr(media, "file_name", "") or "")
                break
    except Exception:
        pass
    caption = getattr(msg, "caption", None)
    if caption:
        names.append(str(caption))
    if isinstance(name, (list, tuple)):
        names.extend(name)
    elif name:
        names.append(name)
    return [n for n in dict.fromkeys(names) if n]


async def send_file_notice(msg, name, delay=600):
    """ফাইলের মেসেজের রিপ্লাই হিসেবে নোটিশ পাঠায়। delay পরে মুছে যায়।"""
    await _dbg(msg, f"send_file_notice চলেছে\nনাম: {name!r}")
    try:
        names = _candidate_names(msg, name)
        notice = None
        for candidate in names:
            notice = get_notice(candidate)
            if notice:
                break
        await _dbg(msg, f"খোঁজা নাম: {names}\nনোটিশ পাওয়া গেছে: {bool(notice)}")
    except Exception as e:
        logger.warning(f"get_notice error: {e}")
        await _dbg(msg, f"get_notice error: {e}")
        return None
    if not notice or not msg:
        return None
    try:
        reply = await msg.reply_text(notice, quote=True)
    except Exception as e:
        logger.warning(f"file notice send error: {e}")
        return None
    asyncio.create_task(_delete_later(reply, delay))
    return reply


# ---------- /addnotice, /delnotice ----------
@Client.on_message(filters.private & filters.user(ADMINS) & filters.command("addnotice"))
async def addnotice_cmd(client, message):
    # ব্যবহার: /addnotice কী-ওয়ার্ড            -> বট পরে নোটিশের লেখা চাইবে
    #         /addnotice কী-ওয়ার্ড | লেখা      -> একসাথে সেভ
    parts = message.text.split(None, 1)
    body = parts[1].strip() if len(parts) > 1 else ""
    if not body:
        return await message.reply("ব্যবহার: /addnotice কী-ওয়ার্ড\nঅথবা: /addnotice কী-ওয়ার্ড | নোটিশের লেখা")
    if "|" in body:
        keyword, text = [x.strip() for x in body.split("|", 1)]
        if not keyword or not text:
            return await message.reply("কী-ওয়ার্ড ও লেখা দুটোই দিন: /addnotice কী-ওয়ার্ড | লেখা")
        add_notice(keyword, text)
        return await message.reply(f"✅ নোটিশ সেভ হয়েছে: `{keyword}`")
    _pending_add[message.from_user.id] = body
    await message.reply(f"`{body}` এর জন্য নোটিশের লেখাটি এখন পাঠান। বাতিল করতে /cancel লিখুন।")


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command("delnotice"))
async def delnotice_cmd(client, message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.reply("ব্যবহার: /delnotice কী-ওয়ার্ড")
    ok = delete_notice(parts[1])
    await message.reply("✅ মুছে ফেলা হয়েছে" if ok else "❌ এমন নোটিশ নেই")


# ---------- /listnotices, বদলানো, মোছা (বাটন দিয়ে) ----------
_pending_edit = {}  # admin_id -> keyword
_pending_add = {}   # admin_id -> keyword (শুধু নাম দেওয়া, লেখা বাকি)


def _hid(keyword):
    # কলব্যাক ডেটার সীমা ছোট, তাই কী-ওয়ার্ডের ছোট হ্যাশ ব্যবহার হয়
    return hashlib.md5(keyword.lower().encode()).hexdigest()[:10]


def _find_by_hid(hid):
    for d in list_notices():
        if _hid(d["keyword"]) == hid:
            return d
    return None


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command("listnotices"))
async def listnotices_cmd(client, message):
    items = list_notices()
    if not items:
        return await message.reply("কোনো নোটিশ নেই।")
    for d in items:
        hid = _hid(d["keyword"])
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✏️ বদলান", callback_data=f"nedit|{hid}"),
            InlineKeyboardButton("🗑 মুছুন", callback_data=f"ndel|{hid}"),
        ]])
        await message.reply(f"• `{d['keyword']}`\n{d['text']}", reply_markup=kb)


@Client.on_callback_query(filters.user(ADMINS) & filters.regex(r"^ndel\|"))
async def notice_delete_cb(client, query):
    d = _find_by_hid(query.data.split("|", 1)[1])
    if not d:
        return await query.answer("নোটিশটি পাওয়া যায়নি", show_alert=True)
    delete_notice(d["keyword"])
    await query.message.edit_text(f"🗑 মুছে ফেলা হয়েছে: `{d['keyword']}`")
    await query.answer()


@Client.on_callback_query(filters.user(ADMINS) & filters.regex(r"^nedit\|"))
async def notice_edit_cb(client, query):
    d = _find_by_hid(query.data.split("|", 1)[1])
    if not d:
        return await query.answer("নোটিশটি পাওয়া যায়নি", show_alert=True)
    _pending_edit[query.from_user.id] = d["keyword"]
    await query.message.reply(f"`{d['keyword']}` এর নতুন লেখাটি পাঠান। বাতিল করতে /cancel লিখুন।")
    await query.answer()


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command("cancel"))
async def notice_cancel_cmd(client, message):
    _pending_edit.pop(message.from_user.id, None)
    _pending_add.pop(message.from_user.id, None)
    await message.reply("❌ বাতিল করা হয়েছে।")


@Client.on_message(
    filters.private & filters.user(ADMINS) & filters.text
    & ~filters.command(["addnotice", "delnotice", "listnotices", "cancel"]),
    group=-1,  # আগে চলবে, যাতে PM সার্চের হ্যান্ডলার (group 0) এর আগে নোটিশের লেখা ধরতে পারে
)
async def notice_edit_text(client, message):
    uid = message.from_user.id
    kw = _pending_add.pop(uid, None)
    if kw:
        add_notice(kw, message.text)
        return await message.reply(f"✅ নোটিশ সেভ হয়েছে: `{kw}`")
    kw = _pending_edit.pop(uid, None)
    if not kw:
        # কোনো অপেক্ষা না থাকলে মেসেজটি বাকি হ্যান্ডলারদের কাছে যাবে (যেমন সার্চ/স্টার্ট)
        await message.continue_propagation()
    add_notice(kw, message.text)
    await message.reply(f"✅ নোটিশ বদলানো হয়েছে: `{kw}`")


def is_episodic(*names):
    """নাম বা ক্যাপশনে সিজন/পর্ব নম্বর থাকলে True (সিরিজ ফাইল)।"""
    from types import SimpleNamespace
    from episode_order import episode_sort_key
    for n in names:
        if n and episode_sort_key(SimpleNamespace(file_name=str(n), caption=""))[0] == 0:
            return True
    return False
