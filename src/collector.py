import os
import asyncio
import discord
from datetime import datetime, timedelta, timezone
import dotenv
import datatypes
import common
import CONSTANTS
import db_worker as dbw

dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.none()
intents.guilds = True
intents.message_content = True
client = discord.Client(intents=intents)

db_worker = dbw.DBWorker()

async def analyze_channel(channel_id):
    try:
        if not channel_id:
            raise RuntimeError("set DISCORD_CHANNEL_ID")
        channel = client.get_channel(channel_id)
        if channel is None:
            channel = await client.fetch_channel(channel_id)

        now = datetime.now(timezone.utc)
        after = now - timedelta(hours=CONSTANTS.FROM_HOURS)
        before = now - timedelta(hours=CONSTANTS.TO_HOURS)
        # after = datetime(2025, 10, 1, 0, 1, tzinfo=timezone.utc)
        # before = datetime(2025, 10, 14, 0, 1, tzinfo=timezone.utc)
        n = 0
        async for m in channel.history(limit=None, after=after, before=before, oldest_first=True):
            event = datatypes.Event(
                message_id=m.id,
                author=await common.get_user_by_id(client, m.guild.id, m.author.id, db_worker),
                message_text=m.content,
                read_time=datetime.now(timezone.utc),
                mentioned_users=await common.users_by_message(m, client, db_worker),
                guild_id=m.guild.id if m.guild else None
            )
            event.disband = int(common.check_disband(event.message_text))
            if m.thread:
                async for mm in m.thread.history(limit=None, oldest_first=True):
                    bm = datatypes.BranchMessage(
                        message_id=mm.id,
                        message_text=mm.content,
                        read_time=datetime.now(timezone.utc)
                    )
                    event.branch_messages.append(bm)
                    if common.check_disband(bm.message_text) and mm.author.id == m.author.id:
                        event.disband = 1
            event.channel_id = m.channel.id
            event.channel_name = m.channel.name
            event.points = common.points_by_event(event)
            n += 1
            if len(event.mentioned_users) < CONSTANTS.MIN_USERS:
                event.disband = 1
            db_worker.add_event(event)
            try:
                if CONSTANTS.REACT_TO_MESSAGES:
                    if event.disband == 1:
                        await m.add_reaction(CONSTANTS.REACTION_NO)
                    else:
                        await m.add_reaction(CONSTANTS.REACTION_YES)
            except Exception:
                pass
        print(f"dumped {n} messages from {after.isoformat()} to {before.isoformat()}")
        with open(str(datetime.now().timestamp()) + '.log', 'w', encoding='utf-8') as f:
            f.write(f"dumped {n} messages from {after.isoformat()} to {before.isoformat()}\n")
    except Exception as e:
        import traceback; traceback.print_exc()


@client.event
async def on_ready():
    print(f"ready: {client.user}")
    try:
        for ch in CONSTANTS.CHANNELS:
            await analyze_channel(ch)
            print(f"analyzed channel {ch}")
    except Exception as e:
        import traceback; traceback.print_exc()
    finally:
        await client.close()

if not TOKEN:
    raise SystemExit("set DISCORD_TOKEN")
client.run(TOKEN)
