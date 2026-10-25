"""批量拉取城市真实图片（Unsplash）。

用法：
    python scripts/fetch_photos.py            # 只补缺失的城市
    python scripts/fetch_photos.py --force    # 全部重拉
    python scripts/fetch_photos.py guiyang chengdu   # 只拉指定城市
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.services import photos as photo_svc  # noqa: E402
from app.services import poi as poi_svc  # noqa: E402


async def main() -> None:
    out = io.open(str(settings.base_dir / "_photos_report.txt"), "w", encoding="utf-8", buffering=1)
    if not settings.photos_ready:
        print("未配置 UNSPLASH_ACCESS_KEY，跳过。请在 .env 填入后重试。", file=out)
        out.close()
        return

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    targets = args or [c["id"] for c in poi_svc.list_cities()]

    total = 0
    for cid in targets:
        city = poi_svc.get_city(cid)
        if not city:
            print(f"跳过未知城市：{cid}", file=out)
            continue
        items = await photo_svc.fetch_city_photos(cid, force=force)
        total += len(items)
        names = ", ".join(i["author"] for i in items) or "无"
        print(f'{city["name"]:6} {len(items)} 张  ← {names}', file=out)
        await asyncio.sleep(0.4)

    print(f"\n完成：{len(targets)} 城 / {total} 张，文件在 {settings.photo_dir}", file=out)
    out.close()


if __name__ == "__main__":
    asyncio.run(main())
