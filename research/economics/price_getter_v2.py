import re
import time
import requests
import pandas as pd

def parse_items_txt_to_df(path: str) -> pd.DataFrame:
    line_re = re.compile(r"^\s*\d+\s*:\s*(T\d+_[A-Z0-9_]+(?:@\d+)?)\s*:\s*(.*?)\s*$")
    id_re = re.compile(
        r"^T(?P<level>\d+)_(?P<name>[A-Z0-9_]+?)(?:_LEVEL\d+)?(?:@(?P<ench>\d+))?$"
    )


    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = line_re.match(line)
            if not m:
                continue
            item_id = m.group(1).strip()
            m2 = id_re.match(item_id)
            if not m2:
                continue
            level = int(m2.group("level"))
            item_name = m2.group("name")
            ench = m2.group("ench")
            enchantment = int(ench) if ench is not None else 0
            rows.append((item_id, item_name, level, enchantment))

    return pd.DataFrame(rows, columns=["item_id", "item_name", "level", "enchantment"]).drop_duplicates("item_id")


from datetime import datetime, timedelta, timezone
import requests

def fetch_history_for_item(
    session: requests.Session,
    base_url: str,
    item_id: str,
    date: str,
    time_scale: int
) -> list[dict]:
    url = f"{base_url}/api/v2/stats/history/{item_id}"

    start = datetime.strptime(date, "%d-%m-%Y")
    end = datetime.now()

    all_data: list[dict] = []

    chunk = timedelta(days=5)
    current_start = start

    while current_start < end:
        print(item_id, ":", current_start, end = ' ')
        current_end = min(current_start + chunk, end)

        params = {
            "date": current_start.strftime("%-m-%-d-%Y"),
            "end_date": current_end.strftime("%-m-%-d-%Y"),
            "time-scale": time_scale,
        }

        r = session.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        if isinstance(data, list):
            print(len(data))
            all_data.extend(data)
        else:
            print("0")
        current_start = current_end
        time.sleep(1)

    return all_data



def history_json_to_df(payload: list[dict]) -> pd.DataFrame:
    if not payload:
        return pd.DataFrame(columns=["location", "item_id", "quality", "item_count", "price_avg", "timestamp"])

    top = pd.DataFrame(payload)
    if top.empty:
        return pd.DataFrame(columns=["location", "item_id", "quality", "item_count", "price_avg", "timestamp"])

    if "data" not in top.columns:
        return pd.DataFrame(columns=["location", "item_id", "quality", "item_count", "price_avg", "timestamp"])

    top = top.explode("data", ignore_index=True)
    inner = pd.json_normalize(top["data"])
    out = pd.concat([top.drop(columns=["data"]), inner], axis=1)

    if "avg_price" in out.columns and "price_avg" not in out.columns:
        out = out.rename(columns={"avg_price": "price_avg"})

    need = ["location", "item_id", "quality", "item_count", "price_avg", "timestamp"]
    for c in need:
        if c not in out.columns:
            out[c] = pd.NA

    out = out[need]
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out["price_avg"] = pd.to_numeric(out["price_avg"], errors="coerce")
    out["item_count"] = pd.to_numeric(out["item_count"], errors="coerce")
    out = out.dropna(subset=["timestamp", "item_id"])
    return out


def build_prices_df_from_txt_and_api(
    txt_path: str,
    *,
    date: str = "01-06-2025",
    time_scale: int = 1,
    base_url: str = "https://west.albion-online-data.com",
    sleep_s: float = 0.0,
    max_items: int | None = None,
) -> pd.DataFrame:
    items_df = parse_items_txt_to_df(txt_path)
    if items_df.empty:
        raise ValueError("no items parsed from txt")

    item_ids = items_df["item_id"].tolist()
    if max_items is not None:
        item_ids = item_ids[:max_items]

    session = requests.Session()
    frames = []

    for item_id in item_ids:
        try:
            payload = fetch_history_for_item(session, base_url, item_id, date, time_scale)
            df_one = history_json_to_df(payload)
            if not df_one.empty:
                # frames.append(df_one)
                pass
        except requests.HTTPError as e:
            print(e)
        except requests.RequestException as e:
            print(e)

        if sleep_s > 0:
            time.sleep(sleep_s)
        if not df_one.empty:
            df_one.to_csv(f"{item_id}.csv")

    if not frames:
        prices_df = pd.DataFrame(columns=["location", "item_id", "quality", "item_count", "price_avg", "timestamp"])
    else:
        prices_df = pd.concat(frames, ignore_index=True)

    out = prices_df.merge(items_df, on="item_id", how="left")

    missing_level = out["level"].isna() if "level" in out.columns else pd.Series(False, index=out.index)
    if missing_level.any():
        id_re = re.compile(
            r"^T(?P<level>\d+)_(?P<name>[A-Z0-9_]+?)(?:_LEVEL\d+)?(?:@(?P<ench>\d+))?$"
        )
        extracted = out.loc[missing_level, "item_id"].astype(str).str.extract(id_re)
        out.loc[missing_level, "level"] = pd.to_numeric(extracted["level"], errors="coerce").astype("Int64")
        out.loc[missing_level, "item_name"] = extracted["name"]
        out.loc[missing_level, "enchantment"] = pd.to_numeric(extracted["ench"], errors="coerce").fillna(0).astype("Int64")

    out["level"] = pd.to_numeric(out["level"], errors="coerce").astype("Int64")
    out["enchantment"] = pd.to_numeric(out["enchantment"], errors="coerce").fillna(0).astype("Int64")
    out = out.drop_duplicates(subset=["location", "item_id", "quality", "timestamp"], keep="last")

    return out


if __name__ == "__main__":
    df = build_prices_df_from_txt_and_api(
        "/home/scv/code/sengoku-attendance-bot/research/economics/items.txt",
        date="01-06-2025",
        time_scale=24
    )
    df.to_csv("really_all.csv")
