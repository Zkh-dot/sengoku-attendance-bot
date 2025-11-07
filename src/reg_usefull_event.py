import os
from typing import List, Dict, Tuple, Optional
import re
import asyncio

import discord
from discord import app_commands
from discord.ext import commands
import dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_CANDIDATES = [
    os.path.join(CURRENT_DIR, ".env"),
    os.path.join(CURRENT_DIR, "..", ".env"),
]
for _p in ENV_CANDIDATES:
    if os.path.isfile(_p):
        dotenv.load_dotenv(_p)
        break
else:
    dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_TOKEN_HERE")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
ALLOWED_CHANNEL_ID = int(os.getenv("DISCORD_ALLOWED_CHANNEL_ID", "0"))
ALLOWED_ROLE_NAMES = [r.strip() for r in os.getenv("DISCORD_ALLOWED_ROLE_NAMES", "").split(",") if r.strip()]

# Event options shown in the dropdown:
# (display_name, (code, points))
EVENT_OPTIONS: List[Tuple[str, Tuple[str, int]]] = [
    ("фиол сфера", ("f_1", 1)),
    ("голд сфера", ("g_1", 2)),
    ("синий вихрь", ("b_2", 1)),
    ("фиол вихрь", ("f_2", 2)),
    ("голд вихрь", ("g_2", 3)),
]

ALIASES: Dict[str, str] = {
    "фиолетовый вихрь": "фиол вихрь",
    "фиолетовая сфера": "фиол сфера",
    "gold сфера": "голд сфера",
    "gold вихрь": "голд вихрь",
    "синий вихор": "синий вихрь",
}


REGISTER_VIEW_TIMEOUT = 300
NICK_INPUT_MAX_LEN = 1800
MAX_PARTICIPANTS = 200
# ----------------------------------------------------

intents = discord.Intents.default()
intents.message_content = False  # not needed here
intents.guilds = True
intents.members = True  # to validate mentions to real members

bot = commands.Bot(command_prefix="!", intents=intents)


def normalize(s: str) -> str:
    x = re.sub(r"\s+", " ", s.strip().lower())
    # common typos
    x = x.replace("вихор", "вихрь")
    x = x.replace("фиолетов", "фиол ")
    x = re.sub(r"\s+", " ", x).strip()
    return ALIASES.get(x, x)

def build_event_index(options: List[Tuple[str, Tuple[str, int]]]) -> Dict[str, Tuple[str, int]]:
    idx: Dict[str, Tuple[str, int]] = {}
    for name, (code, pts) in options:
        idx[normalize(name)] = (code, int(pts))
    return idx

EVENT_INDEX = build_event_index(EVENT_OPTIONS)

def event_label_to_points(event_label: str) -> Tuple[str, int]:
    # Returns (code, points)
    key = normalize(event_label)
    if key not in EVENT_INDEX:
        # Fallback: try exact label from options
        for lbl, (code, pts) in EVENT_OPTIONS:
            if lbl == event_label:
                return code, int(pts)
        # As last resort, return neutral event
        return "unknown", 0
    return EVENT_INDEX[base_key]

RE_ATTENDEE = re.compile(
    r"""
    ^\s*
    (?:\d+\)\s*)?
    @?(?P<handle>[^\s()@]+)
    (?:\s*\((?P<alias>[^)]+)\))?
    \s*$
    """,
    re.VERBOSE,
)

MENTION_RE = re.compile(r"<@!?(\d+)>")

def _extract_handle_or_id(token: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Returns (user_id, handle) — only one populated:
    - if token looks like a mention <@123> -> (123, None)
    - else -> (None, "@Nick")
    """
    m = MENTION_RE.fullmatch(token)
    if m:
        return int(m.group(1)), None
    # treat as handle
    handle = "@" + token.lstrip("@")
    return None, handle

def parse_nicks(raw: str) -> List[str]:
    if not raw or not raw.strip():
        return []

    # Split by newlines, commas, semicolons; also accept multiple spaces as separator
    parts = re.split(r"[\n,;]+|\s{2,}", raw.strip())

    cleaned: List[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # split numbered lists packed on one line: "1) @A 2) @B"
        sub = re.split(r"(?<=\))\s+(?=\d+\)\s*@?)", p)
        for s in sub:
            s = s.strip()
            if not s:
                continue
            m = RE_ATTENDEE.match(s)
            if not m:
                # Try to extract mention or @handle from within the line
                at = re.search(r"(<@!?\d+>|@([^\s()@]+))", s)
                if at:
                    token = at.group(1)
                    uid, handle = _extract_handle_or_id(token)
                    cleaned.append(f"<@{uid}>" if uid else handle)
                else:
                    tokens = s.split()
                    if len(tokens) == 1:
                        _, handle = _extract_handle_or_id(tokens[0])
                        cleaned.append(handle)
                continue
            handle = m.group("handle")
            alias = m.group("alias")
            uid, handle_norm = _extract_handle_or_id(handle)
            base = f"<@{uid}>" if uid else (handle_norm or ("@" + handle.lstrip("@")))
            if alias:
                cleaned.append(f"{base} ({alias.strip()})")
            else:
                cleaned.append(base)
    seen_keys = set()
    result: List[str] = []
    for item in cleaned:
        key = item.split()[0].lower()
        if key not in seen_keys:
            seen_keys.add(key)
            result.append(item)
    if len(result) > MAX_PARTICIPANTS:
        result = result[:MAX_PARTICIPANTS]
    return result

async def filter_existing_members(nicks: List[str], guild: discord.Guild) -> Tuple[List[str], List[str]]:
    """
    Return (valid, invalid) where valid are either mentions that resolve to members
    or plain handles left as-is; we only mark invalid those that are discord mentions that didn't resolve.
    """
    valid, invalid = [], []
    for entry in nicks:
        token = entry.split()[0]
        m = MENTION_RE.fullmatch(token.strip())
        if m:
            uid = int(m.group(1))
            member = guild.get_member(uid)
            if not member:
                try:
                    member = await guild.fetch_member(uid)
                except Exception:
                    member = None
            if member:
                valid.append(entry)
            else:
                invalid.append(entry)
        else:
            valid.append(entry)
    return valid, invalid

async def format_participant(entry: str, guild: discord.Guild) -> str:
    alias = None
    if " (" in entry and entry.endswith(")"):
        base, alias = entry.rsplit(" (", 1)
        alias = alias[:-1]
    else:
        base = entry
    token = base.split()[0]
    m = MENTION_RE.fullmatch(token.strip())
    if not m:
        return f"{base} ({alias})" if alias else base
    uid = int(m.group(1))
    member = guild.get_member(uid)
    if not member:
        try:
            member = await guild.fetch_member(uid)
        except Exception:
            member = None
    if member:
        display = member.display_name
        tag = f"{member.name}#{member.discriminator}" if getattr(member, "discriminator", None) not in (None, "0") else member.name
        pretty = f"{display}" if display and display != member.name else tag
        decorated = f"{token} ({pretty})"
    else:
        decorated = token
    return f"{decorated} ({alias})" if alias else decorated

def user_has_allowed_role(user: discord.abc.User, guild: discord.Guild) -> bool:
    if not ALLOWED_ROLE_NAMES:
        return True
    member = guild.get_member(user.id)
    if not member:
        return False
    user_role_names = {r.name for r in member.roles if hasattr(r, "name")}
    return any(name in user_role_names for name in ALLOWED_ROLE_NAMES)

class RegistrationView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=REGISTER_VIEW_TIMEOUT)
        self.author_id = author_id
        self.selected_event_label: Optional[str] = None
        self.selected_event_code: Optional[str] = None
        self.selected_event_points: int = 0

        options = [
            discord.SelectOption(label=label, value=label, description=f"+{pts} очк.")
            for label, (_, pts) in EVENT_OPTIONS
        ]
        self.event_select = discord.ui.Select(
            placeholder="Выбери событие",
            min_values=1,
            max_values=1,
            options=options
        )
        self.event_select.callback = self.on_select
        self.add_item(self.event_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only the command author can use the view controls
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Эта форма не для тебя.", ephemeral=True)
            return False
        if not user_has_allowed_role(interaction.user, interaction.guild):  # role gate while interacting
            await interaction.response.send_message("Недостаточно прав для использования формы.", ephemeral=True)
            return False
        return True

    async def on_select(self, interaction: discord.Interaction):
        label = self.event_select.values[0]
        code, pts = event_label_to_points(label)
        self.selected_event_label = label
        self.selected_event_code = code
        self.selected_event_points = pts
        await interaction.response.edit_message(
            content=f"Выбрано событие: **{label}** (+{pts} очк.). Теперь нажми \"Ввести ники\".",
            view=self
        )

    @discord.ui.button(label="Ввести ники", style=discord.ButtonStyle.primary)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_event_label:
            await interaction.response.send_message("Сначала выбери событие.", ephemeral=True)
            return
        await interaction.response.send_modal(NicknamesModal(
            event_label=self.selected_event_label,
            event_code=self.selected_event_code or "unknown",
            points=self.selected_event_points
        ))


class NicknamesModal(discord.ui.Modal, title="Регистрация — участники"):
    def __init__(self, event_label: str, event_code: str, points: int):
        super().__init__(timeout=120)
        self.event_label = event_label
        self.event_code = event_code
        self.points = int(points)

        self.nick_input = discord.ui.TextInput(
            label="Ники (через запятую/новые строки)",
            style=discord.TextStyle.paragraph,
            placeholder="@Nick, @Друг (Петя), 1) @User ...  (можно указать 'x2'/'2 раза')",
            required=True,
            max_length=NICK_INPUT_MAX_LEN,
        )
        self.add_item(self.nick_input)
        self.mult_input = discord.ui.TextInput(
            label="Множитель (опционально, число: 1..10)",
            style=discord.TextStyle.short,
            required=False,
            max_length=4,
            placeholder="например: 2"
        )
        self.add_item(self.mult_input)

    async def on_submit(self, interaction: discord.Interaction):
        if ALLOWED_CHANNEL_ID and interaction.channel_id != ALLOWED_CHANNEL_ID:
            await interaction.response.send_message("Регистрация доступна только в разрешённом канале.", ephemeral=True)
            return
        if not user_has_allowed_role(interaction.user, interaction.guild):
            await interaction.response.send_message("Недостаточно прав.", ephemeral=True)
            return
        mult = self.multiplier
        if self.mult_input.value:
            try:
                mult = int(str(self.mult_input.value).strip())
                mult = max(1, min(10, mult))
            except ValueError:
                pass
        if mult < 1:
            mult = 1
        raw = str(self.nick_input.value or "")
        mult_in_text = extract_multiplier(raw)
        if mult_in_text > 1:
            mult = mult_in_text
        nicks = parse_nicks(raw)
        if not nicks:
            await interaction.response.send_message("Не нашла ни одного валидного ника. Проверь формат.", ephemeral=True)
            return
        valid, invalid = await filter_existing_members(nicks, interaction.guild)
        formatted: List[str] = []
        for entry in valid:
            try:
                formatted.append(await format_participant(entry, interaction.guild))
            except Exception:
                formatted.append(entry)
        total_points = self.points * mult
        lines = [f"{i+1}) {n}" for i, n in enumerate(formatted)]
        description = ""
        for line in lines:
            if len(description) + len(line) + 1 > 4000:
                break
            description += (("\n" if description else "") + line)
        adder = interaction.user.mention
        embed = discord.Embed(
            title=f"Регистрация: {self.event_label}",
            description=description,
            color=discord.Color.blue()
        )
        embed.add_field(name="Очки за одно событие", value=f"+{self.points}", inline=True)
        embed.add_field(name="Множитель", value=f"x{mult}", inline=True)
        embed.add_field(name="Итого очков", value=f"+{total_points}", inline=True)
        embed.add_field(name="Код", value=self.event_code, inline=True)
        embed.add_field(name="Добавил(а)", value=adder, inline=False)
        embed.set_footer(text=f"Участники: {len(formatted)}")
        content = None
        if invalid:
            content = "Некоторые упоминания не найдены в гильдии и были пропущены."
        try:
            sent = await interaction.channel.send(content=content, embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("Нет прав писать в этот канал.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.response.send_message("Не удалось отправить сообщение (HTTP ошибка).", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Готово. Отправлено сообщение: {self.event_label} x{mult} (итого +{total_points}). Участников: {len(formatted)}."
            + (f" Пропущено: {len(invalid)}." if invalid else ""),
            ephemeral=True
        )


# ---------- Bot lifecycle and slash command ----------

@bot.event
async def on_ready():
    # Sync commands for a specific guild if provided to avoid global delays
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            await bot.tree.sync(guild=guild)
        else:
            await bot.tree.sync()
    except Exception as e:
        print("Slash sync failed:", e)
    print(f"Logged in as {bot.user} (id={bot.user.id})")

@bot.tree.command(name="reg_event", description="Открыть форму регистрации события")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def register(interaction: discord.Interaction):
    if ALLOWED_CHANNEL_ID and interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Команда доступна только в разрешённом канале.", ephemeral=True)
        return
    if not user_has_allowed_role(interaction.user, interaction.guild):
        await interaction.response.send_message("Недостаточно прав.", ephemeral=True)
        return

    view = RegistrationView(author_id=interaction.user.id)
    try:
        await interaction.response.send_message(
            "Выбери событие, затем нажми «Ввести ники».",
            view=view,
            ephemeral=True
        )
    except discord.HTTPException:
        # Fallback: if ephemeral fails, send without view
        await interaction.response.send_message(
            "Выбери событие, затем нажми «Ввести ники». (без интерактива, произошла ошибка)",
            ephemeral=True
        )


# ---------- Entrypoint ----------

if __name__ == "__main__":
    if not TOKEN or TOKEN == "YOUR_TOKEN_HERE":
        raise RuntimeError("Set DISCORD_TOKEN env variable")
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print("Bot failed:", e)
# ... existing code ...