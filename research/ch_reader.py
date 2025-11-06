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
    file = open("channel_ids.txt", "w", encoding="utf-8")
    for guild in client.guilds:
        print(f"\n=== {guild.name} ({guild.id}) ===")
        me = guild.me
        for ch in guild.channels:
            if ch.permissions_for(me).view_channel:
                print(f"{ch.name}: {ch.id}")
                file.write(f"{guild.name} ({guild.id}) - {ch.name}: {ch.id}\n")
    await client.close()
    file.close()

if not TOKEN:
    raise SystemExit("set DISCORD_TOKEN")
client.run(TOKEN)
