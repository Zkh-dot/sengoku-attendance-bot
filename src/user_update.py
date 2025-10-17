import os
import discord
import CONSTANTS
import datatypes
import db_worker as dbw
import common
import logger
import dotenv
dotenv.load_dotenv()

lgr = logger.get_logger("user_update")
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.none()
intents.guilds = True
intents.message_content = True
client = discord.Client(intents=intents)

db_worker = dbw.DBWorker()
lgr = logger.get_logger("collector")

async def get_all_guild_members(guild: discord.Guild):
    try:
        async for member in guild.fetch_members(limit=None):
            member = common.get_user_by_id(client, guild.id, member.id, None)
            db_worker.add_user(member)
    except Exception as e:
        lgr.error(f"Error fetching members for guild {guild.id}: {e}")

@client.event
async def on_ready():
    lgr.info(f'Logged in as {client.user} (ID: {client.user.id})')
    lgr.info('------')
    for guild in client.guilds:
        if guild.id not in CONSTANTS.GUILD_IDS:
            lgr.info(f"Skipping guild: {guild.name} (ID: {guild.id}) not in target list.")
            continue
        lgr.info(f"Processing guild: {guild.name} (ID: {guild.id})")
        await get_all_guild_members(guild)
    lgr.info("Finished processing all guilds.")
    await client.close()

if not TOKEN:
    raise SystemExit("set DISCORD_TOKEN")
client.run(TOKEN)
