import asyncio
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import aiohttp
from PIL import Image, ImageOps, ImageFilter
import pytesseract

import numpy as np
import os

ph_dir = 'photoes'

if not os.path.exists(ph_dir):
    os.makedirs(ph_dir)


@dataclass
class PhotoPayload:
    channel_id: int
    message_id: int
    author_id: int
    created_at_iso: str
    source: str            # "attachment" | "embed"
    filename: Optional[str]
    url: str
    file_path: Optional[str]


class PhotoAnalyseError(RuntimeError):
    pass


# число (2 цифры) + опциональная дробь (до 2 цифр) + потом "м."
# допускаем пробелы/переносы, и запятую вместо точки
_NUMBER_CHARS = re.compile(r"[0-9.,]+")


async def analyse_photo(payload: PhotoPayload) -> float:
    img = await _download_image(payload.url)
    img.save(os.path.join(ph_dir, f"{payload.message_id}.png"))

    roi = _crop_roi(img)  # left half + bottom 15%
    text = await asyncio.to_thread(_ocr_roi, roi)
    value = _parse_value(text)

    if value is None:
        # запасной проход: другой порог + инверсия (на всякий)
        text2 = await asyncio.to_thread(_ocr_roi_alt, roi)
        value = _parse_value(text2)

    if value is None:
        raise PhotoAnalyseError(
            f"Could not parse value for message_id={payload.message_id} url={payload.url} OCR='{text}'"
        )

    return value


async def _download_image(url: str) -> Image.Image:
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": "photo-analyst/1.0"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise PhotoAnalyseError(f"Failed to download image: HTTP {resp.status} ({url})")
            data = await resp.read()

    try:
        im = Image.open(BytesIO(data))
        im.load()
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        return im
    except Exception as e:
        raise PhotoAnalyseError(f"Invalid image data from {url}: {e}") from e


def _crop_roi(img: Image.Image) -> Image.Image:
    w, h = img.size
    base = img.crop((w // 100 * 5, int(h * 0.91), w // 3, h))  # нижние 15% + левая половина

    roi = _auto_crop_text_zone(base)
    return roi

def _auto_crop_text_zone(im: Image.Image) -> Image.Image:
    g = im.convert("L")
    arr = np.array(g)

    # 1) маска "тёмное" — текст
    # порог делаем адаптивным: возьмём нижний квантиль как "тёмное"
    q = np.quantile(arr, 0.25)
    thr = int(min(180, max(90, q + 25)))
    mask = arr < thr  # True = тёмное

    # 2) убираем длинные горизонтальные линии снизу/внизу ROI
    # выкидываем строки, где слишком много тёмных пикселей (это обычно линия, не текст)
    row_dark = mask.mean(axis=1)
    mask[row_dark > 0.35, :] = False

    # 3) находим bbox всех оставшихся тёмных пикселей
    ys, xs = np.where(mask)
    if len(xs) < 50:
        # мало “текста” нашли — возвращаем исходник, пусть дальше препроцессинг/OCR решает
        return im

    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()

    # 4) расширяем bbox (запас, чтобы не отрезать "1" и дробь)
    pad_x = max(8, int((x1 - x0) * 0.25))
    pad_y = max(8, int((y1 - y0) * 0.40))

    x0 = max(0, x0 - pad_x)
    x1 = min(im.size[0], x1 + pad_x)
    y0 = max(0, y0 - pad_y)
    y1 = min(im.size[1], y1 + pad_y)
    return im.crop((x0, y0, x1, y1))



def _prep(im: Image.Image, thresh: int, force_invert: bool = False) -> Image.Image:
    if not isinstance(im, Image.Image):
        raise TypeError(f"_prep expected PIL.Image.Image, got {type(im)}")
    g = im.convert("L")
    # увеличим: тессеракту так проще
    scale = 5
    g = g.resize((g.size[0] * scale, g.size[1] * scale), Image.Resampling.LANCZOS)

    # контраст/шум
    g = ImageOps.autocontrast(g)
    g = g.filter(ImageFilter.MedianFilter(size=3))

    # бинарайз: чёрный текст на светлом фоне
    bw = g.point(lambda p: 0 if p < thresh else 255)

    if force_invert:
        bw = ImageOps.invert(bw)

    return bw


def _tesseract_config() -> str:
    # один "ряд" текста обычно (м. в конце), поэтому psm 7
    # разрешаем только нужные символы: цифры, точка/запятая, "м", пробел
    return "--oem 1 --psm 6 -c tessedit_char_whitelist=0123456789., "


def _ocr_roi(roi: Image.Image) -> str:
    bw = _prep(roi, thresh=90, force_invert=False)
    roi.save("debug_roi.png")
    bw.save("debug_bw.png")

    text = text = pytesseract.image_to_string(bw, lang="eng", config=_tesseract_config()) or ""
    return _cleanup(text)


def _ocr_roi_alt(roi: Image.Image) -> str:
    bw = _prep(roi, thresh=150, force_invert=False)
    text = pytesseract.image_to_string(bw, lang="rus", config=_tesseract_config()) or ""
    return _cleanup(text)


def _cleanup(s: str) -> str:
    # OCR иногда пихает мусор типа лишних переводов строк
    return " ".join((s or "").strip().split())


def _parse_value(text: str) -> Optional[float]:
    if not text:
        return None

    # оставляем только куски, похожие на число
    parts = _NUMBER_CHARS.findall(text)
    if not parts:
        return None

    # берём самый “длинный” кусок (обычно это и есть наше число)
    s = max(parts, key=len).replace(",", ".")

    # если точка есть — пробуем как float
    if "." in s:
        m = re.search(r"\d{2}(?:\.\d{1,2})?", s)
        if not m:
            return None
        try:
            return float(m.group(0))
        except ValueError:
            return None

    # если точки нет: ожидаем, что OCR её потерял
    # формат: две цифры + 1-2 цифры дроби => всего 3-4 цифры
    digits = re.sub(r"\D", "", s)
    if len(digits) < 2:
        return None

    # отрезаем ровно наш формат: 2 до точки + до 2 после
    if len(digits) == 2:
        return float(digits)  # "21" -> 21.0
    if len(digits) == 3:
        return float(digits[:2] + "." + digits[2:])  # "218" -> 21.8
    if len(digits) >= 4:
        return float(digits[:2] + "." + digits[2:4])  # "2195xx" -> 21.95

    return None
