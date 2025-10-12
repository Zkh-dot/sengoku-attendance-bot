# This example requires the 'message_content' intent.

import discord
import os
import dotenv

dotenv.load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message: discord.Message):
    print(message.guild.id, message.channel.id, message.author.id, message.content)
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')


token = os.getenv("DISCORD_TOKEN")
print("token", token)
if not token:
    raise SystemExit("set DISCORD_TOKEN")
client.run(token)
