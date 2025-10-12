import os
import asyncio
import discord
import dotenv
import re
from datetime import datetime, timedelta, timezone

dotenv.load_dotenv()

TOKEN=os.getenv("DISCORD_TOKEN")
GUILD_ID=int(os.getenv("DISCORD_GUILD_ID","0"))
CHANNEL_ID=int(os.getenv("DISCORD_CHANNEL_ID","0"))

NAME_LINE = r"<@(.*?)>"

intents=discord.Intents.default()
intents.message_content=True
client=discord.Client(intents=intents)

# возвращает строку с лучшим доступным именем (серверный ник если есть, иначе глобальный)
async def get_name_for_id(client: discord.Client, guild_id: int, user_id: int) -> str:
    guild = client.get_guild(guild_id)
    if guild is None:
        try:
            guild = await client.fetch_guild(guild_id)  # редко нужно
        except Exception:
            guild = None

    member = None
    if guild:
        # попробуй взять из кэша
        member = guild.get_member(user_id)
        if member is None:
            # надёжный вариант — запросить по API
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                member = None
            except discord.Forbidden:
                # бот не имеет прав читать участников
                member = None

    if member:
        # display_name уже подставит ник или username
        return member.display_name

    user = await client.fetch_user(user_id)
    return user.name

@client.event
async def on_ready():
    print(f"ready: {client.user}")
    try:
        if not CHANNEL_ID:
            raise RuntimeError("set DISCORD_CHANNEL_ID")
        channel = client.get_channel(CHANNEL_ID)
        if channel is None:
            channel = await client.fetch_channel(CHANNEL_ID)

        now = datetime.now(timezone.utc)
        after = now - timedelta(hours=48)
        before = now - timedelta(hours=24)
        n = 0
        async for m in channel.history(limit=None, after=after, before=before, oldest_first=True):
            atts = " ".join(a.url for a in m.attachments) if m.attachments else ""
            line = f"[{m.created_at.isoformat()}][{m.author.display_name}] {m.content}"
            if atts:
                line += f" [ATTACHMENTS] {atts}"
            print(line)
            n += 1
        print(f"dumped {n} messages from {after.isoformat()} to {before.isoformat()}")
    except Exception as e:
        import traceback; traceback.print_exc()


@client.event
async def on_message(message:discord.Message):
    if message.author.bot:
        return
    if '<@' in message.content:
        mentioned_ids = set(int(m) for m in re.findall(NAME_LINE, message.content))
        id_to_name = {}
        for uid in mentioned_ids:
            name = await get_name_for_id(client, message.guild.id, uid)
            id_to_name[uid] = name
        def replace_mention(m: re.Match) -> str:
            uid = int(m.group(1))
            return f"@{id_to_name.get(uid, 'unknown')}"
        content = re.sub(NAME_LINE, replace_mention, message.content)
        print("replaced mentions:", id_to_name)
    else:
        content = message.content
    message.content = content
    await message.add_reaction("✅")
    print(f"[LIVE][{message.guild.id}][{message.channel.id}][{message.created_at.isoformat()}] {message.author.display_name}: {message.content}")

if not TOKEN:
    raise SystemExit("set DISCORD_TOKEN")
client.run(TOKEN)


# --- one-shot last-24h dumper (dump_last_day.py) ---
# Запуск: DISCORD_TOKEN=... DISCORD_CHANNEL_ID=... python dump_last_day.py
import os
import asyncio
import discord
from datetime import datetime, timedelta, timezone

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

intents = discord.Intents.none()
intents.guilds = True
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"ready: {client.user}")
    try:
        if not CHANNEL_ID:
            raise RuntimeError("set DISCORD_CHANNEL_ID")
        channel = client.get_channel(CHANNEL_ID)
        if channel is None:
            channel = await client.fetch_channel(CHANNEL_ID)
        after = datetime.now(timezone.utc) - timedelta(days=1)
        n = 0
        async for m in channel.history(limit=None, after=after, oldest_first=True):
            atts = " ".join(a.url for a in m.attachments) if m.attachments else ""
            line = f"[{m.created_at.isoformat()}][{m.author.display_name}] {m.content}"
            if atts:
                line += f" [ATTACHMENTS] {atts}"
            print(line)
            n += 1
        print(f"dumped {n} messages since {after.isoformat()}")
    except Exception as e:
        import traceback; traceback.print_exc()
    finally:
        await client.close()

if not TOKEN:
    raise SystemExit("set DISCORD_TOKEN")
client.run(TOKEN)
