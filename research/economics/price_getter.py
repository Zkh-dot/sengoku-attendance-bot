import requests
import pandas as pd

url = "https://albionmarket.gg/wp-admin/admin-ajax.php"

class Item:
    def __init__(self, name: str, tier: int, enchantment: int, level=False):
        self.name = name
        self.tier = tier
        self.enchantment = enchantment
        self.level = level

    def __str__(self):
        return f"T{self.tier}_{self.name}" + (f"_LEVEL{self.enchantment}" if self.level and self.enchantment != 0 else "") + (f"@{self.enchantment}" if self.enchantment != 0 else "")


def get_prices(item: Item) -> pd.DataFrame:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://albionmarket.gg",
        "Referer": f"https://albionmarket.gg/market/europe/{str(item).lower()}/",
    }

    cookies = {
        "cookieyes-consent": "consentid:OHNOck5kY2gzQjJ6UFlmN2dPUGFkZjVNM2hWRm9lZU4,consent:yes,action:yes,necessary:yes,functional:yes,analytics:yes,performance:yes,advertisement:yes",
        "adv_lang_pref": "ru_RU",
    }

    data = {
        "action": "adv_get_chart_data",
        "nonce": "665a8589ad",
        "item_id": str(item),
        "server": "europe",
}


    r = requests.post(url, headers=headers, cookies=cookies, data=data)
    j = r.json()

    rows = []
    print("responce json:", j, "code:", r.status_code)
    try:
        for entry in j["data"]:
        
            loc = entry["location"]
            item_id = entry["item_id"]
            quality = entry["quality"]
            prices = entry["data"]["prices_avg"]
            counts = entry["data"]["item_count"]
            times = entry["data"]["timestamps"]
        
        for p, c, t in zip(prices, counts, times):
            rows.append({
                "location": loc,
                "item_id": item_id,
                "quality": quality,
                "timestamp": t,
                "price_avg": p,
                "item_count": c,
            })
    except Exception as e:
        print(e)
        print(j["data"])
        raise ConnectionError


    df = pd.DataFrame(rows)
    return df
 