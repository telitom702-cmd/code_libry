# Don't Remove Credit @VJ_Bots
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging, re, asyncio, time
from math import ceil
from utils import temp
from info import ADMINS
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from info import INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()

@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")
    _, raju, chat, lst_msg_id, from_user = query.data.split("#")
    if raju == 'reject':
        await query.message.delete()
        await bot.send_message(
            int(from_user),
            f'Your Submission for indexing {chat} has been decliened by our moderators.',
            reply_to_message_id=int(lst_msg_id)
        )
        return

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
    msg = query.message

    await query.answer('Processing...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(
            int(from_user),
            f'Your Submission for indexing {chat} has been accepted by our moderators and will be added soon.',
            reply_to_message_id=int(lst_msg_id)
        )
    await msg.edit(
        "Starting Indexing",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat)
    except:
        chat = chat
    await index_files_to_db(int(lst_msg_id), chat, msg, bot)


@Client.on_message(filters.private & filters.command('index'))
async def send_for_index(bot, message):
    vj = await bot.ask(message.chat.id, "**Now Send Me Your Channel Last Post Link Or Forward A Last Message From Your Index Channel.\n\nAnd You Can Set Skip Number By - /setskip yourskipnumber**")
    if vj.forward_from_chat and vj.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = vj.forward_from_message_id
        chat_id = vj.forward_from_chat.username or vj.forward_from_chat.id
    elif vj.text:
        regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(vj.text)
        if not match:
            return await vj.reply('Invalid link\n\nTry again by /index')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    else:
        return
    try:
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await vj.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await vj.reply('Invalid Link specified.')
    except Exception as e:
        logger.exception(e)
        return await vj.reply(f'Errors - {e}')
    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That Iam An Admin In The Channel, if channel is private')
    if k.empty:
        return await message.reply('This may be group and iam not a admin of the group.')

    if message.from_user.id in ADMINS:
        buttons = [[
            InlineKeyboardButton('Yes', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
        ],[
            InlineKeyboardButton('close', callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do you Want To Index This Channel/ Group ?\n\nChat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>',
            reply_markup=reply_markup
        )

    if type(chat_id) is int:
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('Make sure iam an admin in the chat and have permission to invite users.')
    else:
        link = f"@{message.forward_from_chat.username}"
    buttons = [[
        InlineKeyboardButton('Accept Index', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
    ],[
        InlineKeyboardButton('Reject Index', callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}'),
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(
        LOG_CHANNEL,
        f'#IndexRequest\n\nBy : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat ID/ Username - <code> {chat_id}</code>\nLast Message ID - <code>{last_msg_id}</code>\nInviteLink - {link}',
        reply_markup=reply_markup
    )
    await message.reply('ThankYou For the Contribution, Wait For My Moderators to verify the files.')


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
        except:
            return await message.reply("Skip number should be an integer.")
        await message.reply(f"Successfully set SKIP number as {skip}")
        temp.CURRENT = int(skip)
    else:
        await message.reply("Give me a skip number")


BATCH_SIZE = 200      # একবারে কতগুলো মেসেজ আনবে (Telegram সর্বোচ্চ 200)
FETCH_RETRY = 5       # মেসেজ আনতে ব্যর্থ হলে কতবার আবার চেষ্টা করবে


def get_progress_bar(percent, length=10):
    filled = int(length * percent / 100)
    return '🟩' * filled + '⬜️' * (length - filled)


def get_readable_time(seconds):
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or hours:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


async def fetch_batch(bot, chat, ids):
    """একটি batch আনে। FloodWait/নেটওয়ার্ক সমস্যায় অপেক্ষা করে আবার চেষ্টা করে।"""
    for attempt in range(FETCH_RETRY):
        try:
            messages = await bot.get_messages(chat, ids)
            return messages if isinstance(messages, list) else [messages]
        except FloodWait as e:
            wait = int(getattr(e, "value", 5)) + 1
            logger.warning(f"FloodWait {wait}s while fetching batch {ids[0]}-{ids[-1]}")
            await asyncio.sleep(wait)
        except Exception as e:
            logger.warning(f"Batch {ids[0]}-{ids[-1]} fetch error (try {attempt + 1}): {e}")
            await asyncio.sleep(2 * (attempt + 1))
    return None


async def safe_edit(msg, text, markup=None):
    try:
        await msg.edit_text(text, reply_markup=markup)
    except MessageNotModified:
        pass
    except Exception:
        pass  # progress আপডেট ব্যর্থ হলে indexing থামবে না


async def index_files_to_db(lst_msg_id, chat, msg, bot):
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    failed_ranges = []
    cancel_markup = InlineKeyboardMarkup([[InlineKeyboardButton('Cancel', callback_data='index_cancel')]])
    close_markup = InlineKeyboardMarkup([[InlineKeyboardButton('Close', callback_data='close_data')]])
    start_time = time.time()

    async with lock:
        try:
            temp.CANCEL = False
            first_id = max(int(temp.CURRENT), 1)
            total_fetch = lst_msg_id - first_id + 1
            if total_fetch <= 0:
                return await safe_edit(msg, "🚫 No Messages To Index.", close_markup)

            batches = ceil(total_fetch / BATCH_SIZE)
            await safe_edit(
                msg,
                f"📊 Indexing Starting......\n"
                f"💬 Last Message ID: <code>{lst_msg_id}</code>\n"
                f"📋 Total Fetch: <code>{total_fetch}</code>",
                cancel_markup
            )

            batch_times = []
            fetched = 0
            for batch in range(batches):
                if temp.CANCEL:
                    break
                batch_start = time.time()
                start_id = first_id + batch * BATCH_SIZE
                end_id = min(start_id + BATCH_SIZE - 1, lst_msg_id)
                ids = list(range(start_id, end_id + 1))

                messages = await fetch_batch(bot, chat, ids)
                fetched += len(ids)

                if messages is None:
                    errors += len(ids)
                    failed_ranges.append(f"{start_id}-{end_id}")
                    continue

                save_tasks = []
                for message in messages:
                    try:
                        if message.empty:
                            deleted += 1
                            continue
                        elif not message.media:
                            no_media += 1
                            continue
                        elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                            unsupported += 1
                            continue
                        media = getattr(message, message.media.value, None)
                        if not media:
                            unsupported += 1
                            continue
                        media.file_type = message.media.value
                        media.caption = message.caption
                        save_tasks.append(save_file(media))
                    except Exception as e:
                        logger.warning(f"Message handling error: {e}")
                        errors += 1

                results = await asyncio.gather(*save_tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        errors += 1
                        continue
                    ok, code = result
                    if ok:
                        total_files += 1
                    elif code == 0:
                        duplicate += 1
                    else:  # code 2 / 3 = সেভ ব্যর্থ, কিছুই চুপচাপ বাদ যাবে না
                        errors += 1

                batch_times.append(time.time() - batch_start)
                elapsed = time.time() - start_time
                percentage = min(fetched / total_fetch * 100, 100)
                avg_batch = sum(batch_times) / len(batch_times)
                eta = (batches - batch - 1) * avg_batch
                await safe_edit(
                    msg,
                    f"📊 Indexing Progress 📦 Batch {batch + 1}/{batches}\n"
                    f"{get_progress_bar(int(percentage))} <code>{percentage:.1f}%</code>\n\n"
                    f"Fetched: <code>{fetched}</code> / <code>{total_fetch}</code>\n"
                    f"Saved: <code>{total_files}</code>\n"
                    f"Duplicates: <code>{duplicate}</code>\n"
                    f"Deleted: <code>{deleted}</code>\n"
                    f"Non-Media: <code>{no_media + unsupported}</code> (Unsupported: <code>{unsupported}</code>)\n"
                    f"Errors: <code>{errors}</code>\n"
                    f"⏱️ Elapsed: <code>{get_readable_time(elapsed)}</code>\n"
                    f"⏰ ETA: <code>{get_readable_time(eta)}</code>",
                    cancel_markup
                )

            title = "🛑 Indexing Cancelled!" if temp.CANCEL else "✅ Indexing Completed!"
            text = (
                f"{title}\n"
                f"Fetched: <code>{fetched}</code> / <code>{total_fetch}</code>\n"
                f"Saved: <code>{total_files}</code>\n"
                f"Duplicates: <code>{duplicate}</code>\n"
                f"Deleted: <code>{deleted}</code>\n"
                f"Non-Media: <code>{no_media + unsupported}</code> (Unsupported: <code>{unsupported}</code>)\n"
                f"Errors: <code>{errors}</code>\n"
                f"⏱️ Elapsed: <code>{get_readable_time(time.time() - start_time)}</code>"
            )
            if failed_ranges:
                text += (
                    "\n\n⚠️ These ID ranges could not be fetched: "
                    f"<code>{', '.join(failed_ranges)}</code>\n"
                    "Use /setskip with the first number and index again."
                )
            await safe_edit(msg, text, close_markup)
        except Exception as e:
            logger.exception(e)
            await safe_edit(
                msg,
                f"❌ Error: <code>{e}</code>\n\n"
                f"Saved so far: <code>{total_files}</code> | Duplicates: <code>{duplicate}</code> | Errors: <code>{errors}</code>",
                close_markup
  )
