from asyncio import sleep
from logging import INFO, basicConfig, getLogger
from re import search
from time import time

from emoji import UNICODE_EMOJI
from pyrogram import Client, __version__, filters
from pyrogram.errors import RPCError
from pyrogram.types import (
    CallbackQuery,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from redis import StrictRedis
from uvloop import install

from config import API_HASH, APP_ID, BOT_TOKEN, BOT_USERNAME, REDIS_URL

print("Starting ...")
install()
basicConfig(
    format="%(asctime)s - [UNICODE-DETECTOR] - %(levelname)s - %(message)s",
    level=INFO,
)
LOGGER = getLogger(__name__)
bot = Client(
    "detector",
    bot_token=BOT_TOKEN,
    api_id=APP_ID,
    api_hash=API_HASH,
    sleep_threshold=15,
)
BOT_ID = int(BOT_TOKEN.split(":")[0])
print(f"Started detector with pyrogram version {__version__}")

REDIS = StrictRedis.from_url(REDIS_URL, decode_responses=True)
try:
    REDIS.ping()
except BaseException:
    raise Exception("Your redis server is not alive, please check again!")
finally:
    REDIS.ping()
    LOGGER.info("Your redis server is alive!")


@bot.on_message(filters.command(["start", f"start@{BOT_USERNAME}"]) & ~filters.bot)
async def start(_, m: Message):
    if m.chat.type != "private":
        return await m.reply_text("I'm alive!")
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="Add me to your chat!",
                    url=f"https://t.me/{BOT_USERNAME}?startgroup=true",
                )
            ],
        ]
    )
    return await m.reply_text(
        "Hi there! i'm the one who removes all unicode users from your chat, if you give me a chance!\nCheck /help and for support join @memerschatgroup",
        reply_markup=kb,
    )


@bot.on_message(filters.command(["help", f"help@{BOT_USERNAME}"]) & ~filters.bot)
async def help_re(_, m: Message):
    return await m.reply_text(
        "Just add me to your chat with ban user permission and toggle /detector on | off !\nNote: for support join @memerschatgroup and this is not a final release !"
    )


@bot.on_message(filters.command(["ping", f"ping@{BOT_USERNAME}"]) & ~filters.bot)
async def ping(_, m: Message):
    starttime = time()
    reply = await m.reply_text("Pinging ...")
    delta_ping = time() - starttime
    return await reply.edit_text(f"<b>Pong!</b>\n{delta_ping * 1000:.3f} ms")


# thanks to hamkercat for this shortcut
async def member_permissions(chat_id: int, user_id: int):
    perms = []
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except RPCError:
        return []
    if member.can_delete_messages:
        perms.append("can_delete_messages")
    if member.can_restrict_members:
        perms.append("can_restrict_members")
    if member.can_change_info:
        perms.append("can_change_info")
    return perms


@bot.on_message(
    filters.command(["detector", f"detector@{BOT_USERNAME}"]) & ~filters.bot
)
async def power(_, m: Message):
    if m and not m.from_user:
        return
    if m.chat.type == "private":
        return await m.reply_text("This command works only on supergroups!")

    permissions = await member_permissions(int(m.chat.id), int(m.from_user.id))
    if "can_restrict_members" and "can_change_info" not in permissions:
        return await m.reply_text("You don't have enough permissions!")
    args = m.text.split()
    status = REDIS.get(f"Chat_{m.chat.id}")

    if len(args) >= 2:
        option = args[1].lower()
        if option in ("yes", "on", "true"):
            REDIS.set(f"Chat_{m.chat.id}", str("True"))
            await m.reply_text(
                "Turned on.",
                quote=True,
            )
        elif option in ("no", "off", "false"):
            REDIS.set(f"Chat_{m.chat.id}", str("False"))
            await m.reply_text(
                "Turned off.",
                quote=True,
            )
    else:
        return await m.reply_text(
            f"This group's current setting is: `{status}`\nTry with on and off to toggle!"
        )
    return


async def check_string(string: str):
    # thanks to https://github.com/Squirrel-Network/nebula8/blob/master/core/utilities/regex.py
    HAS_ARABIC = "[\u0600-\u06ff]|[\u0750-\u077f]|[\ufb50-\ufbc1]|[\ufbd3-\ufd3f]|[\ufd50-\ufd8f]|[\ufd92-\ufdc7]|[\ufe70-\ufefc]|[\uFDF0-\uFDFD]+"
    HAS_CIRILLIC = "[а-яА-Я]+"
    HAS_CHINESE = "[\u4e00-\u9fff]+"
    EMOJI = UNICODE_EMOJI["en"]

    try:
        check1 = search(HAS_ARABIC, string)
        check2 = search(HAS_CHINESE, string)
        check3 = search(HAS_CIRILLIC, string)
        check4 = None
        for a in string:
            if a in EMOJI:
                check4 = True
        CHK = [check1, check2, check3, check4]
        if not any(CHK):
            return False
        return True
    except ValueError:
        return False


def rm_indb(_id: int, user_):
    already_triggered = list(REDIS.sunion(f"User_{_id}"))
    if already_triggered:
        for a in already_triggered:
            if a == str(user_):
                REDIS.srem(f"User_{_id}", user_)
                LOGGER.info(f"Removed {user_} of {_id} from db.")
                return True
            return False
    else:
        return False


@bot.on_callback_query(filters.regex("^action_"))
async def _buttons(c: Client, q: CallbackQuery):
    splitter = (str(q.data).replace("action_", "")).split("=")
    chat_id = q.message.chat.id
    action = str(splitter[1])
    user_id = int(splitter[2])
    preeser = q.from_user.id
    mention = (await c.get_users(user_id)).mention
    permissions = await member_permissions(chat_id, preeser)
    whopress = await q.message.chat.get_member(preeser)
    LOGGER.info("Action buttons pressed ...")
    if whopress.status not in ["creator", "administrator"]:
        await q.answer(
            "You're not even an admin, don't try this!",
            show_alert=True,
        )
        return
    if action == "ban":
        bann = "Baned !"
    elif action == "kick":
        bann = "Kicked !"
    elif action == "mute":
        bann = "Muted !"
    else:
        bann = "Solved !"

    editreport = f"""
<b>Action:</b>
{mention} was having unicode letters in the name!
<b>Status:</b> Action Taken by {q.from_user.mention} !
<b>Action:</b> {bann}
    """
    if action == "kick":
        if "can_restrict_members" not in permissions:
            await q.answer("You don't have enough permissions.", show_alert=True)
            return
        try:
            await c.kick_chat_member(chat_id, user_id)
            await q.answer("kicked Successfully !")
            await q.message.edit_text(editreport)
            await c.unban_chat_member(chat_id, user_id)
            return rm_indb(int(chat_id), user_id)
        except RPCError as err:
            await q.message.edit_text(
                f"Failed to Kick\n<b>Error:</b>\n</code>{err}</code>"
            )
            return rm_indb(int(chat_id), user_id)
    elif action == "ban":
        if "can_restrict_members" not in permissions:
            await q.answer("You don't have enough permissions.", show_alert=True)
            return
        try:
            await c.kick_chat_member(chat_id, user_id)
            await q.answer("Successfully Banned!")
            await q.message.edit_text(editreport)
            return rm_indb(int(chat_id), user_id)
        except RPCError as err:
            await q.message.edit_text(f"Failed to Ban\n<b>Error:</b>\n`{err}`")
            return rm_indb(int(chat_id), user_id)
    elif action == "mute":
        if "can_restrict_members" not in permissions:
            await q.answer("You don't have enough permissions.", show_alert=True)
            return
        try:
            await q.message.chat.restrict_member(
                user_id,
                ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_stickers=False,
                    can_send_animations=False,
                    can_send_games=False,
                    can_use_inline_bots=False,
                    can_add_web_page_previews=False,
                    can_send_polls=False,
                    can_change_info=False,
                    can_invite_users=True,
                    can_pin_messages=False,
                ),
            )
            await q.answer("Muted !")
            await q.message.edit_text(editreport)
            return rm_indb(int(chat_id), user_id)
        except RPCError as err:
            await q.message.edit_text(f"Failed to Ban\n<b>Error:</b>\n`{err}`")
            return rm_indb(int(chat_id), user_id)
    elif action == "oke":
        if "can_restrict_members" not in permissions:
            await q.answer("You don't have enough permissions.", show_alert=True)
            return
        if "can_delete_messages" not in permissions:
            await q.answer("You don't have enough permissions.", show_alert=True)
            return
        await q.message.edit_text(editreport)
        return rm_indb(int(chat_id), user_id)
    return


@bot.on_message(filters.group & filters.all & ~filters.bot)
async def triggered(c: Client, m: Message):
    if m and not m.from_user:
        return
    if m and m.left_chat_member:
        return
    if REDIS.get(f"Chat_{m.chat.id}") == str("False"):
        return
    LOGGER.info("Checking ...")
    user_has = ""
    try:
        user_has = m.from_user.first_name
    except TypeError:
        pass
    try:
        user_has += m.from_user.last_name
    except TypeError:
        pass
    what = await check_string(str(user_has))
    already_triggered = list(REDIS.sunion(f"User_{m.chat.id}"))
    if already_triggered:
        for a in already_triggered:
            if a == str(m.from_user.id):
                LOGGER.info("User is in db.")
                if not what:
                    REDIS.srem(f"User_{m.chat.id}", m.from_user.id)
                    return
                return

    who = await m.chat.get_member(int(m.from_user.id))
    if who.status in ["creator", "administrator"]:
        return
    if not user_has:
        await c.send_message(
            int(m.chat.id), f"User {m.from_user.mention} detected without a name!!"
        )
        return await sleep(3)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Kick",
                    callback_data=f"action_=kick={m.from_user.id}",
                ),
                InlineKeyboardButton(
                    "Ban",
                    callback_data=f"action_=ban={m.from_user.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Mute",
                    callback_data=f"action_=mute={m.from_user.id}",
                ),
                InlineKeyboardButton(
                    "Solved !",
                    callback_data=f"action_=oke={m.from_user.id}",
                ),
            ],
        ]
    )
    admin_data = await bot.get_chat_members(int(m.chat.id), filter="administrators")
    admin_tag = str()
    tag = "\u200b"
    for admin in admin_data:
        if not admin.user.is_bot:
            admin_tag = admin_tag + f"[{tag}](tg://user?id={admin.user.id})"
    admin_tag += f"User {m.from_user.mention} is detected as a Unicode user !!"
    if what:
        await c.send_message(int(m.chat.id), admin_tag, reply_markup=keyboard)
        REDIS.sadd(f"User_{m.chat.id}", m.from_user.id)
        LOGGER.info(f"Added {m.from_user.id} from {m.chat.id} in db.")
    else:
        isor = rm_indb(int(m.chat.id), m.from_user.id)
        LOGGER.info(f"Ok ! Removed - {isor}")
    return await sleep(3)


bot.run()
