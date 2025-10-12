import discord
import CONSTANTS
import datatypes
import re

async def get_user_by_id(client: discord.Client, guild_id: int, user_id: int) -> datatypes.User:
    guild = client.get_guild(guild_id)
    if guild is None:
        try:
            guild = await client.fetch_guild(guild_id)  # редко нужно
        except Exception:
            guild = None

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

    try:
        user = await client.fetch_user(user_id)
    except Exception:
        user = None
    user = datatypes.User(
        uuid=user_id,
        server_username=member.display_name if member else None,
        global_username=user.name if user else None
    )
    return user


async def users_by_message(message: discord.Message, client: discord.Client) -> list[datatypes.User]:
    if '<@' in message.content:
        mentioned_ids = set(int(m) for m in re.findall(CONSTANTS.NAME_LINE, message.content))
        users = []
        for uid in mentioned_ids:
            user = await get_user_by_id(client, message.guild.id, uid)
            users.append(user)
        return users
    return []

def check_disband(message: str) -> bool:
    text = message.lower()
    for word in text:
        if word in CONSTANTS.DISBAND_MESSAGES:
            return True
    return False