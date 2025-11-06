# NOT WORKING YET

import os
from typing import List
import re

import discord
from discord import app_commands
from discord.ext import commands
import dotenv   
dotenv.load_dotenv()

# ---------------------- CONFIG ----------------------
# Fill these before running
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_TOKEN_HERE")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))  # optional: for faster slash sync
ALLOWED_CHANNEL_ID = int(os.getenv("DISCORD_ALLOWED_CHANNEL_ID", "0"))  # restrict to one channel; 0 disables check

# Event options shown in the dropdown
EVENT_OPTIONS = [
    ("фиол сфера", ("f_1", 1)),
    ("голд сфера", ("g_1", 2)),
    ("синий вихрь", ("b_2", 1)),
    ("фиол вихрь", ("f_2", 2)),
    ("голд вихрь", ("g_2", 3))
]
# ----------------------------------------------------

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def parse_nicks(raw: str) -> List[str]:
    # Accept comma, semicolon, newline, whitespace
    parts = re.split(r"[\n,;]+|\s{2,}", raw.strip())
    # Also split single whitespace if commas not used
    cleaned = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Ensure discord-like tag formatting is kept as-is
        cleaned.append(p)
    # Deduplicate preserving order
    seen = set()
    result = []
    for n in cleaned:
        if n.lower() not in seen:
            seen.add(n.lower())
            result.append(n)
    return result

class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.selected_event_label: str | None = None
        self.selected_event_value: str | None = None

        # Add dropdown
        options = [discord.SelectOption(label=label, value=value[1]) for label, value in EVENT_OPTIONS]
        self.event_select = discord.ui.Select(placeholder="Выбери событие", min_values=1, max_values=1, options=options)
        self.event_select.callback = self.on_select
        self.add_item(self.event_select)

    async def on_select(self, interaction: discord.Interaction):
        val = self.event_select.values[0]
        # Map value back to label
        label = next((l for l, v in EVENT_OPTIONS if v[0] == val), val)
        self.selected_event_label = label
        self.selected_event_value = val
        await interaction.response.edit_message(content=f"Выбрано событие: **{label}**. Теперь нажми \"Ввести ники\"",
                                                view=self)

    @discord.ui.button(label="Ввести ники", style=discord.ButtonStyle.primary)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_event_label:
            await interaction.response.send_message("Сначала выбери событие в выпадающем списке", ephemeral=True)
            return
        await interaction.response.send_modal(NicknamesModal(self.selected_event_label))

class NicknamesModal(discord.ui.Modal, title="Регистрация — ники"):
    def __init__(self, event_label: str):
        super().__init__()
        self.event_label = event_label
        self.nick_input = discord.ui.TextInput(
            label="Ники (через запятую/новые строки)",
            style=discord.TextStyle.paragraph,
            placeholder="@Nick#0001, @Друг#1234, ...",
            required=True,
            max_length=1800,
        )
        self.add_item(self.nick_input)

    async def on_submit(self, interaction: discord.Interaction):
        if ALLOWED_CHANNEL_ID and interaction.channel_id != ALLOWED_CHANNEL_ID:
            await interaction.response.send_message("Регистрация доступна только в разрешённом канале", ephemeral=True)
            return

        raw = str(self.nick_input.value)
        nicks = parse_nicks(raw)
        if not nicks:
            await interaction.response.send_message("Ни одного валидного ника не нашла. Попробуй ещё раз.", ephemeral=True)
            return

        # Post to the same channel (public)
        mention = interaction.user.mention
        msg = (
            f"📌 Регистрация на **{self.event_label}**\n"
            f"Добавил(а): {mention}\n\n"
            f"Участники (\u200b{len(nicks)}):\n" + "\n".join(f"• {n}" for n in nicks)
        )
        await interaction.channel.send(msg)
        await interaction.response.send_message("Готово. Сообщение отправлено в канал.", ephemeral=True)

@bot.event
async def on_ready():
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            await bot.tree.sync(guild=guild)
            print(f"Synced commands to guild {GUILD_ID}")
        else:
            await bot.tree.sync()
            print("Synced global commands")
    except Exception as e:
        print("Sync failed:", e)
    print(f"Logged in as {bot.user}")

@bot.tree.command(name="reg_event", description="Открыть форму регистрации")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: (i.user.id))
async def register(interaction: discord.Interaction):
    if ALLOWED_CHANNEL_ID and interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Команда доступна только в разрешённом канале", ephemeral=True)
        return

    view = RegistrationView()
    await interaction.response.send_message(
        "Выбери событие, затем нажми \"Ввести ники\". Сообщение с итогом уйдёт в канал.",
        view=view,
        ephemeral=True,
    )

if __name__ == "__main__":
    if not TOKEN or TOKEN == "YOUR_TOKEN_HERE":
        raise RuntimeError("Set DISCORD_BOT_TOKEN env or put token into TOKEN")
    bot.run(TOKEN)
