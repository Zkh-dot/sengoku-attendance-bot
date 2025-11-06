import os
import sys
import discord
from datetime import datetime, timedelta, timezone
import dotenv
import datatypes
import common
import CONSTANTS
import db_worker as dbw
import logger
dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.none()
intents.guilds = True
intents.message_content = True
client = discord.Client(intents=intents)

db_worker = dbw.DBWorker()
lgr = logger.get_logger("collector")

async def analyze_channel(channel_id: int, points: int, hide=False, after: datetime = None, before: datetime = None):
    try:
        if not channel_id:
            raise RuntimeError("set DISCORD_CHANNEL_ID")
        channel = client.get_channel(channel_id)
        if channel is None:
            channel = await client.fetch_channel(channel_id)

        now = datetime.now(timezone.utc)
        try:
            after = datetime.fromisoformat(os.getenv("SENGOKU_AFTER", "")) if os.getenv("SENGOKU_AFTER") else (now - timedelta(hours=CONSTANTS.FROM_HOURS))
        except ValueError:
            after = now - timedelta(hours=CONSTANTS.FROM_HOURS)
        try:
            before = datetime.fromisoformat(os.getenv("SENGOKU_BEFORE", "")) if os.getenv("SENGOKU_BEFORE") else (now - timedelta(hours=CONSTANTS.TO_HOURS))
        except ValueError:
            before = now - timedelta(hours=CONSTANTS.TO_HOURS)
        # after = datetime(2025, 11, 1, 0, 1, tzinfo=timezone.utc)
        # before = datetime(2025, 10, 16, 0, 1, tzinfo=timezone.utc)
        lgr.info(f"analyzing channel {channel_id} from {after} to {before}")
        n = 0
        async for m in channel.history(limit=None, after=after, before=before, oldest_first=True):
            event = datatypes.Event(
                message_id=m.id,
                author=await common.get_user_by_id(client, m.guild.id, m.author.id, db_worker),
                message_text=m.content,
                read_time=m.created_at,
                mentioned_users=await common.users_by_message(m, client, db_worker),
                guild_id=m.guild.id if m.guild else None,
                hidden=hide
            )
            event.disband = int(common.check_disband(event.message_text))
            if m.thread:
                async for mm in m.thread.history(limit=None, oldest_first=True):
                    bm = datatypes.BranchMessage(
                        message_id=mm.id,
                        message_text=mm.content,
                        read_time=mm.created_at
                    )
                    event.branch_messages.append(bm)
                    if common.check_disband(bm.message_text) and mm.author.id == m.author.id:
                        event.disband = 1
            event.channel_id = m.channel.id
            event.channel_name = m.channel.name
            event.points = common.points_by_event(event, points)
            if event in CONSTANTS.HIDDEN and common.check_for_treasury(m):
                event.points = CONSTANTS.TREASURY_POINTS
            n += 1
            if len(event.mentioned_users) < CONSTANTS.MIN_USERS:
                event.disband = 1
            db_worker.add_event(event)
            try:
                if CONSTANTS.REACT_TO_MESSAGES:
                    lgr.info(f"adding reaction to message {m.id}, disband={event.disband}")
                    await m.add_reaction(CONSTANTS.REACTION_NO if event.disband == 1 else CONSTANTS.REACTION_YES)
            except Exception as e:
                lgr.error(f"Failed to add reaction to message {m.id}: {e}")
        lgr.info(f"analyzed {n} messages in channel {channel_id}")
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        lgr.error(f"Error analyzing channel {channel_id}: {e}, {exc_type}, {fname}, {exc_tb.tb_lineno}")

async def analyze_usefulness_points(after: datetime = None, before: datetime = None):
    # Placeholder for future implementation
    pass

@client.event
async def on_ready():
    lgr.info(f"logged in as {client.user}")
    try:
        for ch in CONSTANTS.CHANNELS:
            await analyze_channel(ch, CONSTANTS.CHANNELS[ch], hide=False)
            lgr.info(f"analyzed channel {ch}")
        for ch in CONSTANTS.HIDDEN:
            await analyze_channel(ch, CONSTANTS.HIDDEN[ch], hide=True)
            lgr.info(f"analyzed hidden channel {ch}")
    except Exception as e:
        import traceback; traceback.print_exc()
    finally:
        await client.close()
        lgr.info("All done, client closed")

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("set DISCORD_TOKEN")
    client.run(TOKEN)
    datatypes.Website().open()

