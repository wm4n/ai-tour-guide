"""對真實的 Overpass 與維基百科跑一次景點查詢（免費公開 API，不呼叫 Claude）。

python -m buddy_host.places --lat 25.0553 --lon 121.5098 --heading 0
"""

import argparse
import asyncio

import httpx2
import truststore

from buddy_host.config import default_home
from buddy_host.places.cache import JsonCache
from buddy_host.places.fetch import RetryingHttp
from buddy_host.places.gather import gather_candidates
from buddy_host.places.merge import names_match
from buddy_host.places.models import Location
from buddy_host.places.overpass import OverpassClient
from buddy_host.places.ranking import DEFAULT_RADIUS_M, rank, theme_of
from buddy_host.places.wikipedia import WikipediaClient

DAY = 24 * 3600


async def run(args: argparse.Namespace) -> None:
    truststore.inject_into_ssl()
    home = default_home()
    location = Location(args.lat, args.lon, args.heading)
    async with httpx2.AsyncClient(timeout=30) as client:
        http = RetryingHttp(client)
        overpass = OverpassClient(http, JsonCache(home / "cache" / "overpass", DAY))
        wiki = WikipediaClient(http, JsonCache(home / "cache" / "wikipedia", 7 * DAY))

        merged = await gather_candidates(
            overpass, wiki, location.lat, location.lon, DEFAULT_RADIUS_M
        )
        titled = sum(c.wiki_title is not None for c in merged)
        print(f"合併後候選 {len(merged)} 個，其中已有維基條目標題 {titled} 個")

        ranked = rank(merged, location, limit=args.limit)
        for i, r in enumerate(ranked, start=1):
            c = r.candidate
            title = c.wiki_title
            if title is None:
                found = await wiki.search(c.name)
                title = found if found and names_match(c.name, found) else None
            summary = await wiki.summary(title) if title else None
            print(
                f"\n#{i} {c.name}  [{c.id}]  距離 {r.distance_m:.0f} m  方位 {r.bearing_deg:.0f}°  "
                f"分數 {r.score:.2f}  主題 {theme_of(c)}"
            )
            preview = summary.extract[:60] + "…" if summary else "（沒有）"
            print(f"   維基標題：{title}  摘要：{preview}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--heading", type=float, default=None)
    parser.add_argument("--limit", type=int, default=5)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
