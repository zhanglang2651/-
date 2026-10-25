"""给后加的 10 座城市补图片检索词（可重复执行）。"""
import json
from pathlib import Path

P = Path(r"D:\文旅助手\app\data\photo_queries.json")
q = json.loads(P.read_text(encoding="utf-8"))

NEW = {
    "guangzhou": ["Guangzhou Canton Tower", "Guangzhou city China"],
    "shenzhen": ["Shenzhen skyline China", "Shenzhen city"],
    "wuhan": ["Yellow Crane Tower Wuhan", "Wuhan Yangtze river"],
    "tianjin": ["Tianjin city China", "Tianjin skyline"],
    "luoyang": ["Longmen Grottoes Luoyang", "Luoyang China temple"],
    "sanya": ["Sanya beach China", "Hainan island sea"],
    "lhasa": ["Potala Palace Lhasa", "Tibet Lhasa city"],
    "urumqi": ["Xinjiang landscape China", "Urumqi city"],
    "dunhuang": ["Dunhuang desert China", "Mogao caves Dunhuang"],
    "fuzhou": ["Fuzhou China city", "Fujian Fuzhou"],
}
added = {k: v for k, v in NEW.items() if k not in q}
q.update(NEW)
P.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"added={len(added)} total={len(q)}")
