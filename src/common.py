import discord
import CONSTANTS
import datatypes
import re
import datetime
import db_worker as dbw
from datetime import date, timedelta


def days_until_month_end(from_date: date) -> int:
    if isinstance(from_date, datetime.datetime):
        from_date = from_date.date()

    today = date.today()
    next_month = (today.replace(day=28) + timedelta(days=4))
    end_of_current_month = next_month - timedelta(days=next_month.day)

    return (end_of_current_month - from_date).days

def calculate_need_to_get(join_date: datetime.datetime) -> int:
    need_to_get = min(45, int(days_until_month_end(join_date) * 1.5))
    return need_to_get


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
        need_to_get = calculate_need_to_get(member.joined_at)
        is_member = 1
        user_roles = [r.name for r in member.roles if r.name != "@everyone"]
        for admin_role in CONSTANTS.ADMIN_ROLES:
            if admin_role in user_roles:
                liable = CONSTANTS.ADMIN_ROLES[admin_role]
                break
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
        need_to_get=need_to_get if member else 0,
        join_date=member.joined_at if member else None
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

def points_by_event(event: datatypes.Event, points: int) -> int:
    for name in CONSTANTS.GROUP_MAP_NAMES:
        if name in event.message_text.lower():
            return CONSTANTS.POINTS_GROUP_MAP
    return CONSTANTS.CHANNELS.get(event.channel_id, points)

def check_for_treasury(message: discord.Message) -> bool:
    text = message.content.lower()
    for word in text:
        if word in CONSTANTS.TREASURY_MESSAGES:
            return True
    if message.thread:
        for mm in message.thread.history(limit=None, oldest_first=True):
            if mm.content:
                text = mm.content.lower()
                for word in text:
                    if word in CONSTANTS.TREASURY_MESSAGES:
                        return True
    return False

def calculate_points_to_get(join_date):
    pass