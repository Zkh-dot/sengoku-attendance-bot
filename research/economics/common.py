import discord
import dotenv
import os
import datetime
from dataclasses import dataclass
from typing import Optional, Sequence
import photo_anal
import pandas as pd
dotenv.load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CH_ID = os.getenv("CHANNEL_ID")

intents = discord.Intents.none()
intents.guilds = True
intents.message_content = True
client = discord.Client(intents=intents)

rows = []

# --- Утилиты ---
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff")


def _looks_like_image_attachment(att: discord.Attachment) -> bool:
    ct = (att.content_type or "").lower()
    if ct.startswith("image/"):
        return True
    name = (att.filename or "").lower()
    return name.endswith(_IMAGE_EXTS)


def _extract_image_urls_from_message(msg: discord.Message) -> list[tuple[str, str, Optional[str]]]:
    """
    Возвращает список троек (source, url, filename)
    source: "attachment" | "embed"
    """
    out: list[tuple[str, str, Optional[str]]] = []

    # attachments
    for att in msg.attachments:
        if _looks_like_image_attachment(att):
            out.append(("attachment", att.url, att.filename))

    # embeds (картинки, превью, и т.п.)
    for emb in msg.embeds:
        if emb.image and emb.image.url:
            out.append(("embed", emb.image.url, None))
        if emb.thumbnail and emb.thumbnail.url:
            out.append(("embed", emb.thumbnail.url, None))

    return out


# --- Главное ---
@client.event
async def on_ready() -> None:
    if hasattr(client, "intents"):
        client.intents.messages = True  # type: ignore[attr-defined]

    channel_id = int(CH_ID)

    channel = client.get_channel(channel_id)
    if channel is None:
        channel = await client.fetch_channel(channel_id)

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        raise TypeError(f"CHANNEL_ID={channel_id} не текстовый канал/тред: {type(channel)}")

    total_msgs = 0
    total_imgs = 0

    # limit=None = вся история; oldest_first=True = с начала (удобнее для прогресса/логов)
    async for msg in channel.history(limit=None, oldest_first=True):
        total_msgs += 1

        img_items = _extract_image_urls_from_message(msg)
        if not img_items:
            continue

        for source, url, filename in img_items:
            total_imgs += 1
            payload = photo_anal.PhotoPayload(
                channel_id=channel_id,
                message_id=msg.id,
                author_id=msg.author.id,
                created_at_iso=msg.created_at.isoformat(),
                source=source,
                filename=filename,
                url=url,
                file_path=None
            )
            try:
                r = await photo_anal.analyse_photo(payload)
            except photo_anal.PhotoAnalyseError as e:
                print(e)
                r = None
            print(f"message {total_imgs}, link {source}, {r}")
            rows.append({
                'number': r,
                'date': msg.created_at,
                'link': url
            })

        # Если канал огромный и хочешь быть бережнее к лимитам/CPU — можно чуть притормаживать
        # (не обязательно, но иногда спасает)
        # if total_msgs % 100 == 0:
        #     print(f"первые 100 успешно, последняя дата: {msg.created_at.isoformat()}")
        #     break
            # await asyncio.sleep(1)

    print(f"Done. Messages scanned: {total_msgs}, images queued: {total_imgs}")
    df = pd.DataFrame(rows)
    df.to_csv(f'data{datetime.datetime.now().hour}:{datetime.datetime.now().minute}.csv')
    await client.close()


if __name__ == "__main__":
    if TOKEN is None:
        raise RuntimeError("DISCORD_TOKEN не найден в env")
    client.run(TOKEN)
