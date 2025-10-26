import asyncio
import os
import discord
from discord.ext import commands
import dotenv
import db_worker as dbw
import datatypes
import common
dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
db_worker = dbw.DBWorker()

intents = discord.Intents.default()
intents.members = True

bot = discord.Client(intents=intents)

async def get_nicks(guild_id: int):
    guild = bot.get_guild(guild_id) or await bot.fetch_guild(guild_id)
    for m in guild.members:
        user = db_worker.get_user(m.id)
        if user:
            user.global_username = m.global_name
            user.server_username = m.display_name
            user.join_date = m.joined_at
            user.need_to_get = common.calculate_need_to_get(user.join_date)
        else:
            user = datatypes.User(
                m.id,
                m.display_name,
                m.global_name,
                join_date=m.joined_at,
                need_to_get=common.calculate_need_to_get(m.joined_at)
            )
        db_worker.add_user(user)


@bot.event
async def on_ready():
    print(f"bot ready as {bot.user}")
    await get_nicks(guild_id=1355240968621658242)
    await bot.close()

if __name__ == "__main__":
    bot.run(TOKEN)
