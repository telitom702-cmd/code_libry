"""
copy_channel.py
Native-forward workflow for a Pyrogram project.

Admins forward a source-channel post to the bot's private chat. The bot reads the
native forward origin, offers enabled target channels, asks for Accept, then forwards
the original source post to the chosen target so Telegram keeps the source attribution.

Channel records use MongoDB collection `copy_channels`:
{
  "_id": "<chat_id as string>",
  "chat_id": -1001234567890,
  "title": "Channel title",
  "role": "source" or "target",
  "enabled": True
}

If your existing channel-management code stores channels elsewhere, adapt
`get_target_channels()` and `is_source_enabled()` to that existing schema.
"""

import logging
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS
from plugins.database.database import db
from plugins.index_system import (
    index_enabled,
    is_indexed,
    message_fingerprint,
    save_fingerprint,
)

LOGGER = logging.getLogger(__name__)

CHANNELS_COLLECTION = "copy_channels"
channels_col = db.db[CHANNELS_COLLECTION]

# One pending job per admin.
COPY_STATE = {}


async def get_target_channels():
    cursor = channels_col.find({
        "role": "target",
        "enabled": {"$ne": False},
    })
    return [doc async for doc in cursor]


async def is_source_enabled(chat_id):
    channel = await channels_col.find_one({
        "chat_id": int(chat_id),
        "role": "source",
    })
    if not channel:
        # If the source was not registered, don't silently accept it.
        return False
    return bool(channel.get("enabled", True))


def target_keyboard(channels):
    rows = []
    for ch in channels:
        chat_id = int(ch.get("chat_id", ch.get("_id")))
        title = ch.get("title") or str(chat_id)
        rows.append([InlineKeyboardButton(
            title[:60],
            callback_data=f"cp_target:{chat_id}",
        )])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="cp_cancel")])
    return InlineKeyboardMarkup(rows)


def accept_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept", callback_data="cp_accept"),
            InlineKeyboardButton("❌ Cancel", callback_data="cp_cancel"),
        ]
    ])


def forward_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Forward", callback_data="cp_forward"),
            InlineKeyboardButton("❌ Cancel", callback_data="cp_cancel"),
        ]
    ])


async def send_progress(message, total, sent, skipped, failed, current_title=""):
    text = (
        "📤 <b>Forward Progress</b>\n\n"
        f"🎯 Target: <b>{escape(current_title)}</b>\n"
        f"📦 Total: <code>{total}</code>\n"
        f"✅ Sent: <code>{sent}</code>\n"
        f"⏭ Skipped: <code>{skipped}</code>\n"
        f"❌ Failed: <code>{failed}</code>"
    )
    try:
        await message.edit_text(text, parse_mode=enums.ParseMode.HTML)
    except Exception:
        pass


@Client.on_message(filters.private & filters.forwarded)
async def receive_native_forward(client, message):
    if not message.from_user or message.from_user.id not in ADMINS:
        return

    # Pyrogram versions expose forward origin through forward_from_chat / forward_from_message_id.
    source_chat = getattr(message, "forward_from_chat", None)
    source_message_id = getattr(message, "forward_from_message_id", None)

    if not source_chat or not source_message_id:
        await message.reply_text(
            "❌ সোর্স চ্যানেলের আসল Forward তথ্য পাওয়া যায়নি।\n"
            "চ্যানেলের পোস্টটি Copy/Paste না করে Telegram-এর Forward অপশন দিয়ে পাঠান।"
        )
        return

    source_chat_id = int(source_chat.id)
    if not await is_source_enabled(source_chat_id):
        await message.reply_text(
            f"⚠️ Source channel তালিকায় নেই বা OFF করা আছে.\n"
            f"Channel ID: <code>{source_chat_id}</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    targets = await get_target_channels()
    if not targets:
        await message.reply_text("❌ কোনো enabled Target Channel পাওয়া যায়নি।")
        return

    COPY_STATE[message.from_user.id] = {
        "source_chat_id": source_chat_id,
        "source_message_id": int(source_message_id),
        "source_title": source_chat.title or str(source_chat_id),
        "targets": [int(ch.get("chat_id", ch.get("_id"))) for ch in targets],
        "accepted": False,
    }

    await message.reply_text(
        "📥 <b>Source শনাক্ত হয়েছে</b>\n\n"
        f"📢 Source: <b>{escape(source_chat.title or str(source_chat_id))}</b>\n"
        f"🆔 Source ID: <code>{source_chat_id}</code>\n\n"
        "কোন Target Channel-এ পাঠাবেন?",
        reply_markup=target_keyboard(targets),
        parse_mode=enums.ParseMode.HTML,
    )


@Client.on_callback_query(filters.regex(r"^cp_"))
async def copy_channel_callbacks(client, query):
    if not query.from_user or query.from_user.id not in ADMINS:
        return await query.answer("Admins only!", show_alert=True)

    user_id = query.from_user.id
    state = COPY_STATE.get(user_id)
    data = query.data

    if data == "cp_cancel":
        COPY_STATE.pop(user_id, None)
        await query.answer("Cancelled")
        try:
            await query.message.edit_text("❌ Forward task cancelled.")
        except Exception:
            pass
        return

    if not state:
        return await query.answer("কোনো pending Forward task নেই।", show_alert=True)

    if data.startswith("cp_target:"):
        target_id = int(data.split(":", 1)[1])
        if target_id not in state["targets"]:
            return await query.answer("Invalid target.", show_alert=True)

        target = await channels_col.find_one({"chat_id": target_id, "role": "target"})
        state["target_chat_id"] = target_id
        state["target_title"] = (target or {}).get("title", str(target_id))
        await query.answer("Target selected")
        await query.message.edit_text(
            "📋 <b>Forward Confirmation</b>\n\n"
            f"📢 Source: <b>{escape(state['source_title'])}</b>\n"
            f"🎯 Target: <b>{escape(state['target_title'])}</b>\n\n"
            "নিশ্চিত হলে Accept চাপুন।",
            reply_markup=accept_keyboard(),
            parse_mode=enums.ParseMode.HTML,
        )
        return

    if data == "cp_accept":
        if "target_chat_id" not in state:
            return await query.answer("আগে Target Channel নির্বাচন করুন।", show_alert=True)
        state["accepted"] = True
        await query.answer("Accepted")
        await query.message.edit_text(
            "✅ Accepted.\n\nForward শুরু করতে Forward বাটনে চাপুন।",
            reply_markup=forward_keyboard(),
        )
        return

    if data == "cp_forward":
        if not state.get("accepted") or "target_chat_id" not in state:
            return await query.answer("আগে Target নির্বাচন করে Accept করুন।", show_alert=True)

        await query.answer("Forward started")
        target_id = state["target_chat_id"]
        target_title = state["target_title"]
        progress = await query.message.reply_text("📤 Forward শুরু হচ্ছে…")

        total = sent = skipped = failed = 1
        sent = skipped = failed = 0

        try:
            # Duplicate check is controlled per-target by Index ON/OFF.
            # To compare content fingerprints reliably, the source message needs to be
            # accessible to this client. Get the original source post, then forward it.
            index_on = await index_enabled(target_id)
            try:
                source_message = await client.get_messages(
                    state["source_chat_id"], state["source_message_id"]
                )
                fingerprint = message_fingerprint(source_message)
            except Exception:
                source_message = None
                fingerprint = None

            if index_on and fingerprint and await is_indexed(target_id, fingerprint):
                skipped = 1
                await send_progress(progress, total, sent, skipped, failed, target_title)
            else:
                # Native forward from source chat preserves Telegram's source attribution.
                await client.forward_messages(
                    chat_id=target_id,
                    from_chat_id=state["source_chat_id"],
                    message_ids=state["source_message_id"],
                )
                sent = 1
                if fingerprint:
                    await save_fingerprint(
                        target_id, fingerprint,
                        message_id=state["source_message_id"],
                        source_chat_id=state["source_chat_id"],
                    )
                await send_progress(progress, total, sent, skipped, failed, target_title)

        except Exception as exc:
            failed = 1
            LOGGER.exception("Forward failed")
            await send_progress(progress, total, sent, skipped, failed, target_title)
            try:
                await progress.edit_text(
                    "❌ <b>Forward failed</b>\n"
                    f"Target: <b>{escape(target_title)}</b>\n"
                    f"Error: <code>{escape(str(exc)[:500])}</code>",
                    parse_mode=enums.ParseMode.HTML,
                )
            except Exception:
                pass
        else:
            try:
                await progress.edit_text(
                    "✅ <b>Forward process complete</b>\n\n"
                    f"🎯 Target: <b>{escape(target_title)}</b>\n"
                    f"📦 Total: <code>{total}</code>\n"
                    f"✅ Sent: <code>{sent}</code>\n"
                    f"⏭ Skipped: <code>{skipped}</code>\n"
                    f"❌ Failed: <code>{failed}</code>",
                    parse_mode=enums.ParseMode.HTML,
                )
            except Exception:
                pass
        finally:
            COPY_STATE.pop(user_id, None)
        return
