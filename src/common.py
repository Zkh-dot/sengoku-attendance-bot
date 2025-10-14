import discord
import CONSTANTS
import datatypes
import re
import datetime
import db_worker as dbw

async def get_user_by_id(client: discord.Client, guild_id: int, user_id: int, db_worker: dbw.DBWorker = None) -> datatypes.User:
    user = db_worker.get_user(user_id) if db_worker else None
    if user:
        return user
    guild = client.get_guild(guild_id)
    if guild is None:
        try:
            guild = await client.fetch_guild(guild_id)  # редко нужно
        except Exception:
            guild = None
    need_to_get = 45
    member = None
    if guild:
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                member = None
            except discord.Forbidden:
                member = None
    liable = 1
    is_member = 0
    if member:
        next_month = (discord.utils.utcnow().replace(day=28) + datetime.timedelta(days=4)).replace(hour=0, minute=0, second=0, microsecond=0)
        last_day = next_month - datetime.timedelta(days=next_month.day)

        delta = last_day - member.joined_at
        print(f"member {member.display_name} joined_at: {member.joined_at.isoformat()}, delta: {delta}")
        need_to_get = min(45, int(delta.days * 1.5))
        is_member = 1
        liable = 0 if (CONSTANTS.RENTOR_NAME in [r.name for r in member.roles if r.name != "@everyone"]) else 1
    try:
        user = await client.fetch_user(user_id)
    except Exception:
        user = None
    
    user = datatypes.User(
        uuid=user_id,
        server_username=member.display_name if member else None,
        global_username=user.name if user else None,
        liable=liable,
        is_member=is_member,
        need_to_get=need_to_get
    )
    return user


async def users_by_message(message: discord.Message, client: discord.Client, db_worker: dbw.DBWorker = None) -> list[datatypes.User]:
    if '<@' in message.content:
        mentioned_ids = set(int(m) for m in re.findall(CONSTANTS.NAME_LINE, message.content))
        users = []
        for uid in mentioned_ids:
            user = await get_user_by_id(client, message.guild.id, uid, db_worker)
            users.append(user)
        return users
    return []

def check_disband(message: str) -> bool:
    text = message.lower()
    for word in text:
        if word in CONSTANTS.DISBAND_MESSAGES:
            return True
    return False

def points_by_event(event: datatypes.Event) -> int:
    for name in CONSTANTS.GROUP_MAP_NAMES:
        if name in event.message_text.lower():
            return CONSTANTS.POINTS_GROUP_MAP
    return CONSTANTS.CHANNELS.get(event.channel_id, 0)