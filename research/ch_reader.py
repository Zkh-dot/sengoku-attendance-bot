import os
import asyncio
import discord
import dotenv

dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.none()
intents.guilds = True  # чтобы видеть список каналов
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"logged in as {client.user}")
    for guild in client.guilds:
        print(f"\n=== {guild.name} ({guild.id}) ===")
        me = guild.me
        for ch in guild.channels:
            if ch.permissions_for(me).view_channel:
                print(f"{ch.name}: {ch.id}")
    await client.close()

if not TOKEN:
    raise SystemExit("set DISCORD_TOKEN")
client.run(TOKEN)
