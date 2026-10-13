"""
index_system.py
Target-channel file indexer for a Pyrogram project.

Expected project dependencies:
- Pyrogram Client
- `from plugins.database.database import db` where db.db is an async MongoDB database.

Channel records are stored in `copy_channels`:
{
  "_id": "<chat_id as string>",
  "chat_id": -1001234567890,
  "title": "Target title",
  "role": "target",
  "enabled": True
}

Index fingerprints are stored in `copy_channel_index`.
"""

import hashlib
import logging
from datetime import datetime

from pyrogram import enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from plugins.database.database import db

LOGGER = logging.getLogger(__name__)

CHANNELS_COLLECTION = "copy_channels"
INDEX_COLLECTION = "copy_channel_index"
SETTINGS_COLLECTION = "copy_channel_settings"

channels_col = db.db[CHANNELS_COLLECTION]
index_col = db.db[INDEX_COLLECTION]
settings_col = db.db[SETTINGS_COLLECTION]


def message_fingerprint(message):
    """Return a stable fingerprint for media, or a normalized hash for text."""
    media_attrs = (
        "document", "video", "audio", "animation", "voice",
        "video_note", "sticker", "photo"
    )
    for attr in media_attrs:
        item = getattr(message, attr, None)
        if not item:
            continue
        if attr == "photo":
            item = item[-1]
        unique_id = getattr(item, "file_unique_id", None)
        if unique_id:
            return f"media:{unique_id}"

    text = (message.text or message.caption or "").strip()
    if text:
        normalized = " ".join(text.split()).casefold()
        return "text:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    # This fallback prevents repeated indexing of this exact post only; it does not
    # identify equivalent media posted with a different message ID.
    return f"message:{message.chat.id}:{message.id}"


async def index_enabled(chat_id):
    settings = await settings_col.find_one({"_id": str(int(chat_id))})
    if not settings:
        await settings_col.update_one(
            {"_id": str(int(chat_id))},
            {"$setOnInsert": {"index_enabled": True, "updated_at": datetime.utcnow()}},
            upsert=True,
        )
        return True
    return bool(settings.get("index_enabled", True))


async def set_index_enabled(chat_id, enabled):
    await settings_col.update_one(
        {"_id": str(int(chat_id))},
        {"$set": {"index_enabled": bool(enabled), "updated_at": datetime.utcnow()}},
        upsert=True,
    )
    return True


async def is_indexed(target_chat_id, fingerprint):
    return bool(await index_col.find_one({
        "target_chat_id": int(target_chat_id),
        "fingerprint": fingerprint,
    }))


async def save_fingerprint(target_chat_id, fingerprint, message_id=None, source_chat_id=None):
    await index_col.update_one(
        {
            "target_chat_id": int(target_chat_id),
            "fingerprint": fingerprint,
        },
        {"$setOnInsert": {
            "target_chat_id": int(target_chat_id),
            "fingerprint": fingerprint,
            "message_id": int(message_id) if message_id else None,
            "source_chat_id": int(source_chat_id) if source_chat_id else None,
            "indexed_at": datetime.utcnow(),
        }},
        upsert=True,
    )


async def index_target_channel(client, target_chat_id, progress_message=None):
    """
    Scan the accessible history of a target channel and store fingerprints.
    Requires the logged-in Pyrogram client to have permission to read the channel.
    """
    total = indexed = errors = 0
    await index_col.create_index(
        [("target_chat_id", 1), ("fingerprint", 1)],
        unique=True,
        background=True,
    )

    async for message in client.get_chat_history(int(target_chat_id)):
        total += 1
        try:
            # Ignore service messages without media/text.
            if not any(getattr(message, a, None) for a in (
                "document", "video", "audio", "animation", "voice",
                "video_note", "sticker", "photo", "text"
            )) and not message.caption:
                continue

            fingerprint = message_fingerprint(message)
            await save_fingerprint(target_chat_id, fingerprint, message.id, message.chat.id)
            indexed += 1
        except Exception:
            errors += 1
            LOGGER.exception("Index failed for target=%s message=%s", target_chat_id, message.id)

        if progress_message and (total == 1 or total % 10 == 0):
            try:
                await progress_message.edit_text(
                    "🔎 <b>Indexing Target Channel</b>\n\n"
                    f"📥 Scanned: <code>{total}</code>\n"
                    f"✅ Indexed: <code>{indexed}</code>\n"
                    f"⚠️ Errors: <code>{errors}</code>\n"
                    "Progress updates every 10 messages.",
                    parse_mode=enums.ParseMode.HTML,
                )
            except Exception:
                pass

    if progress_message:
        try:
            await progress_message.edit_text(
                "✅ <b>Index Complete</b>\n\n"
                f"📥 Scanned: <code>{total}</code>\n"
                f"✅ Indexed: <code>{indexed}</code>\n"
                f"⚠️ Errors: <code>{errors}</code>",
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass

    return {"total": total, "indexed": indexed, "errors": errors}


async def list_target_channels():
    cursor = channels_col.find({
        "role": "target",
        "enabled": {"$ne": False},
    })
    return [doc async for doc in cursor]


async def index_menu_keyboard():
    targets = await list_target_channels()
    rows = []
    for channel in targets:
        chat_id = int(channel.get("chat_id", channel.get("_id")))
        enabled = await index_enabled(chat_id)
        title = channel.get("title") or str(chat_id)
        rows.append([InlineKeyboardButton(
            f"{'🟢' if enabled else '🔴'} {title} | Index {'ON' if enabled else 'OFF'}",
            callback_data=f"idx_toggle:{chat_id}",
        )])
        rows.append([InlineKeyboardButton(
            f"🔎 Index now: {title}",
            callback_data=f"idx_run:{chat_id}",
        )])
    rows.append([InlineKeyboardButton("❌ Close", callback_data="idx_close")])
    return InlineKeyboardMarkup(rows)


def register_index_handlers(Client, ADMINS):
    """Call register_index_handlers(Client, ADMINS) from your plugin loader."""
    @Client.on_message(__import__("pyrogram").filters.private & __import__("pyrogram").filters.command("index"))
    async def index_command(client, message):
        if not message.from_user or message.from_user.id not in ADMINS:
            return await message.reply_text("Admins only.")
        await message.reply_text(
            "🔎 <b>Target Channel Index</b>\nSelect a target to index, or toggle duplicate-check.",
            reply_markup=await index_menu_keyboard(),
            parse_mode=enums.ParseMode.HTML,
        )

    @Client.on_callback_query(__import__("pyrogram").filters.regex(r"^idx_"))
    async def index_callbacks(client, query):
        if not query.from_user or query.from_user.id not in ADMINS:
            return await query.answer("Admins only.", show_alert=True)

        data = query.data
        if data == "idx_close":
            await query.message.delete()
            return await query.answer()

        if data.startswith("idx_toggle:"):
            chat_id = int(data.split(":", 1)[1])
            new_value = not await index_enabled(chat_id)
            await set_index_enabled(chat_id, new_value)
            await query.answer(f"Index {'ON' if new_value else 'OFF'}")
            try:
                await query.message.edit_reply_markup(reply_markup=await index_menu_keyboard())
            except Exception:
                pass
            return

        if data.startswith("idx_run:"):
            chat_id = int(data.split(":", 1)[1])
            await query.answer("Index started")
            status = await query.message.reply_text("🔎 Starting index…")
            try:
                await index_target_channel(client, chat_id, status)
            except Exception as exc:
                LOGGER.exception("Index operation failed for %s", chat_id)
                await status.edit_text(f"❌ Index failed: <code>{str(exc)[:700]}</code>",
                                       parse_mode=enums.ParseMode.HTML)

    return index_command, index_callbacks
