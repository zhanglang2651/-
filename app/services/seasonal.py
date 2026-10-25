"""时令旅行服务：二十四节气、节气物候、当季城市、节庆与应季玩法。

节气用太阳视黄经计算（低精度算法，误差约 ±15 分钟），不是查表硬编码，
所以任何年份都能用。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from math import cos, radians, sin
from typing import Any

from app.config import settings
from app.services import poi as poi_svc
from app.services import trends as trend_svc

# ------------------------------------------------------------------ 节气核心

# 小寒 = 285°，每 15° 一个节气
TERM_ORDER = ["小寒", "大寒", "立春", "雨水", "惊蛰", "春分",
              "清明", "谷雨", "立夏", "小满", "芒种", "夏至",
              "小暑", "大暑", "立秋", "处暑", "白露", "秋分",
              "寒露", "霜降", "立冬", "小雪", "大雪", "冬至"]

# 每个节气的物候、气候与旅行建议（面向游客的通俗表达）
TERM_PROFILE: dict[str, dict[str, str]] = {
    "小寒": {"season": "深冬", "pheno": "雁北乡，鹊始巢",
             "climate": "寒气渐盛，南北差异拉大",
             "advice": "北方冰挂雾凇、南方围炉煮茶，温泉与滑雪场进入旺季"},
    "大寒": {"season": "深冬", "pheno": "鸡始乳，征鸟厉疾",
             "climate": "一年中最冷的一段时间",
             "advice": "避寒首选低纬暖城，去海南、昆明过冬正当时"},
    "立春": {"season": "早春", "pheno": "东风解冻，蛰虫始振",
             "climate": "气温回升但波动大，倒春寒常见",
             "advice": "江南看早樱、黄山迎雾凇，装备仍需防寒"},
    "雨水": {"season": "早春", "pheno": "獭祭鱼，候雁北",
             "climate": "降水增多，空气湿润",
             "advice": "烟雨江南、梯田云海出片期，注意防水鞋"},
    "惊蛰": {"season": "早春", "pheno": "桃始华，仓庚鸣",
             "climate": "春雷始动，气温快速回升",
             "advice": "油菜花海、樱花季开幕，川西与江南最出片"},
    "春分": {"season": "仲春", "pheno": "玄鸟至，雷乃发声",
             "climate": "昼夜均分，晴好天气增多",
             "advice": "踏青赏花正当时，骑行与户外的最佳窗口"},
    "清明": {"season": "仲春", "pheno": "桐始华，虹始见",
             "climate": "多雨潮湿，昼夜温差大",
             "advice": "雨后山色最润，适合古村与茶山，雨具必备"},
    "谷雨": {"season": "仲春", "pheno": "萍始生，鸣鸠拂其羽",
             "climate": "雨生百谷，作物生长最快",
             "advice": "春茶开采、采花摘果体验，一年只此几天"},
    "立夏": {"season": "初夏", "pheno": "蝼蝈鸣，蚯蚓出",
             "climate": "万物并秀，南方进入湿热期",
             "advice": "江浙与西南开始闷热，山区与高原最舒服"},
    "小满": {"season": "初夏", "pheno": "苦菜秀，靡草死",
             "climate": "北方干热，南方湿热",
             "advice": "薰衣草与麦浪进入花期，日照强的地区注意防晒"},
    "芒种": {"season": "初夏", "pheno": "螳螂生，鵙始鸣",
             "climate": "雨热同期，午后雷阵雨频繁",
             "advice": "抢收抢种季，可看农事体验；雷雨天避开山谷"},
    "夏至": {"season": "盛夏", "pheno": "鹿角解，蝉始鸣",
             "climate": "一年中白昼最长，暑气最盛",
             "advice": "北回归线看「立杆无影」，夜市与夜游的旺季来了"},
    "小暑": {"season": "盛夏", "pheno": "温风至，蟋蟀居壁",
             "climate": "暴雨与高温并存",
             "advice": "戏水、漂流、避暑开始热门，山区避暑最舒适"},
    "大暑": {"season": "盛夏", "pheno": "腐草为萤，土润溽暑",
             "climate": "全年最热时段，高温高湿",
             "advice": "夜游、灯会、萤火虫最值得追，昼间躲进室内"},
    "立秋": {"season": "初秋", "pheno": "凉风至，白露降",
             "climate": "暑热未消，早晚转凉",
             "advice": "秋高气爽的开端，秋游与登高开始升温"},
    "处暑": {"season": "初秋", "pheno": "鹰乃祭鸟，天地始肃",
             "climate": "昼夜温差拉大，暑气渐收",
             "advice": "云海日出概率变高，摄影的黄金时段到了"},
    "白露": {"season": "仲秋", "pheno": "鸿雁来，玄鸟归",
             "climate": "昼夜温差进一步加大，早晚有凉意",
             "advice": "桂花初开、稻田金黄，江南与东北进入最佳期"},
    "秋分": {"season": "仲秋", "pheno": "雷始收声，蛰虫坯户",
             "climate": "昼夜再次均分，秋高气爽",
             "advice": "一年最舒服的旅行天气， trekking 与长线首选"},
    "寒露": {"season": "深秋", "pheno": "鸿雁来宾，菊有黄华",
             "climate": "露水渐寒，北方已需棉服",
             "advice": "赏菊、红叶初启，摄影主题最好卖"},
    "霜降": {"season": "深秋", "pheno": "豺乃祭兽，草木黄落",
             "climate": "秋末冬初，昼夜温差最大",
             "advice": "红叶与银杏进入最盛期，摄影圈的旺季"},
    "立冬": {"season": "初冬", "pheno": "水始冰，地始冻",
             "climate": "北方封冻，南方缓慢降温",
             "advice": "换季错峰价低，温泉、围炉与热汤正当其时"},
    "小雪": {"season": "初冬", "pheno": "虹藏不见，天气上升",
             "climate": "北方开始降雪，南方湿冷",
             "advice": "初雪打卡、雪景温泉，注意道路结冰"},
    "大雪": {"season": "仲冬", "pheno": "鹖鴠不鸣，虎始交",
             "climate": "降雪增多，昼短夜长",
             "advice": "雪地玩法正当时，但需防滑与保暖双重装备"},
    "冬至": {"season": "仲冬", "pheno": "蚯蚓结，麋角解",
             "climate": "一年中最冷的时段之一",
             "advice": "北方冰雪季高潮，南方避寒与温泉走俏"},
}


def _jd_from_date(y: int, m: int, d: int) -> float:
    """公历日期 → 儒略日（当日 0h UT）。"""
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    jdn = d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045
    return jdn - 0.5


def _apparent_lon(jd: float) -> float:
    """太阳视黄经（度）。低精度公式，误差约 0.01°。"""
    t = (jd - 2451545.0) / 36525.0
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    mm = 357.52911 + 35999.05029 * t - 0.0001537 * t * t
    mr = radians(mm)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * sin(mr)
         + (0.019993 - 0.000101 * t) * sin(2 * mr)
         + 0.000289 * sin(3 * mr))
    om = 125.04 - 1934.136 * t
    return (l0 + c - 0.00569 - 0.00478 * sin(radians(om))) % 360.0


def _lon_delta(jd: float, target: float) -> float:
    """黄经与目标角的最短差值（度），用于二分。"""
    return ((_apparent_lon(jd) - target + 180.0) % 360.0) - 180.0


@lru_cache(maxsize=8)
def _terms_of_year(year: int) -> tuple[tuple[str, str], ...]:
    """返回该年 24 个节气的 (名称, YYYY-MM-DD)，按时间序。"""
    result: list[tuple[str, str]] = []
    for idx, name in enumerate(TERM_ORDER):
        target = (285.0 + idx * 15.0) % 360.0
        # 节气落在某月内（大致：idx 对应月份），全年扫描更稳妥
        lo = _jd_from_date(year, 1, 1)
        hi = _jd_from_date(year + 1, 1, 6)
        step = 1.0
        prev_jd = lo
        prev_d = _lon_delta(prev_jd, target)
        found = None
        cur = lo + step
        while cur <= hi:
            d = _lon_delta(cur, target)
            if prev_d < 0 <= d:  # 上穿零
                a, b = prev_jd, cur
                for _ in range(40):
                    mid = (a + b) / 2
                    if _lon_delta(mid, target) < 0:
                        a = mid
                    else:
                        b = mid
                found = (a + b) / 2
                break
            prev_jd, prev_d = cur, d
            cur += step
        if found is None:
            continue
        # 儒略日 → 北京时间（UTC+8）日期
        beijing_jd = found + 8.0 / 24.0
        jd_mid = beijing_jd + 0.5
        z = int(jd_mid)
        f = jd_mid - z
        if f >= 1:
            z += 1
            f -= 1
        alpha = int((z - 1867216.25) / 36524.25)
        a_ = z + 1 + alpha - alpha // 4
        b_ = a_ + 1524
        c_ = int((b_ - 122.1) / 365.25)
        d_ = int(365.25 * c_)
        e_ = int((b_ - d_) / 30.6001)
        day = b_ - d_ - int(30.6001 * e_) + f
        month = e_ - 1 if e_ < 14 else e_ - 13
        year_out = c_ - 4716 if month > 2 else c_ - 4715
        result.append((name, f"{year_out:04d}-{int(month):02d}-{int(day):02d}"))
    result.sort(key=lambda x: x[1])
    return tuple(result)


def current_term(day: date | None = None) -> dict[str, Any]:
    """当前所处节气 + 下一个节气 + 距离天数。"""
    day = day or date.today()
    terms = _terms_of_year(day.year)
    lookup = {n: d for n, d in terms}
    # 上一个（日期 ≤ 今天）
    prev_name, prev_date = terms[0]
    next_name, next_date = terms[-1]
    for name, dt in terms:
        if dt <= day.isoformat():
            prev_name, prev_date = name, dt
        else:
            next_name, next_date = name, dt
            break
    else:
        nxt = _terms_of_year(day.year + 1)
        next_name, next_date = nxt[0]
    try:
        days_to_next = (date.fromisoformat(next_date) - day).days
    except ValueError:
        days_to_next = 0
    prof = TERM_PROFILE.get(prev_name, {})
    return {
        "name": prev_name,
        "date": prev_date,
        "season": prof.get("season", ""),
        "pheno": prof.get("pheno", ""),
        "climate": prof.get("climate", ""),
        "advice": prof.get("advice", ""),
        "next": next_name,
        "next_date": next_date,
        "days_to_next": days_to_next,
        "year_terms": [{"name": n, "date": d} for n, d in terms],
        "today": day.isoformat(),
    }


# ------------------------------------------------------------------ 当季城市

def _season_months(spec: str) -> set[int]:
    return trend_svc.parse_season(spec)


def best_cities_now(limit: int = 8) -> list[dict[str, Any]]:
    """当前月份处于最佳旅行季的城市。"""
    today = date.today()
    rows = []
    for c in poi_svc.list_cities():
        months = _season_months(c.get("best_season", ""))
        if today.month not in months:
            continue
        fest = [f[1] for f in trend_svc.FESTIVALS.get(c["id"], []) if f[0] == today.month]
        rows.append({
            "city_id": c["id"], "city": c["name"], "province": c["province"],
            "accent": c["accent"], "tags": c.get("tags", []),
            "signature": c.get("signature", ""), "intro": c.get("intro", ""),
            "foods": c.get("foods", []), "best_season": c.get("best_season", ""),
            "festival": fest[0] if fest else "",
        })
    return rows[:limit]


def festivals_now() -> list[dict[str, Any]]:
    """本月全国城市节庆。"""
    today = date.today()
    out = []
    for c in poi_svc.list_cities():
        for month, name in trend_svc.FESTIVALS.get(c["id"], []):
            if month == today.month:
                out.append({"city_id": c["id"], "city": c["name"],
                            "province": c["province"], "name": name, "accent": c["accent"]})
    out.sort(key=lambda x: x["city"])
    return out


# ------------------------------------------------------------------ 玩法主题

THEME_RULES: list[dict[str, Any]] = [
    {"id": "nature", "name": "山水自然", "icon": "⛰", "color": "#4ade80",
     "desc": "山、水、瀑、梯田，把身体交给地形",
     "types": ["自然"], "tags": ["爬山", "徒步", "瀑布", "云海", "雪山", "湖泊", "溶洞",
                                "梯田", "登山", "观景", "自驾"]},
    {"id": "ancient", "name": "古城古镇", "icon": "🏯", "color": "#fbbf24",
     "desc": "老街、青瓦与慢下来的时间",
     "types": ["古镇"], "tags": ["古镇", "古城", "老街", "民俗", "民族", "牌坊"]},
    {"id": "food", "name": "美食寻味", "icon": "🍜", "color": "#f472b6",
     "desc": "一碗热汤、一串烧烤，一座城的胃",
     "types": ["美食"], "tags": ["小吃", "夜市", "烟火气", "市井", "美食街"]},
    {"id": "family", "name": "亲子研学", "icon": "🧸", "color": "#38bdf8",
     "desc": "能让孩子边跑边学的地方",
     "types": ["主题"], "tags": ["亲子", "乐园", "研学", "博物馆", "科普", "动物"]},
    {"id": "humanities", "name": "人文古迹", "icon": "📜", "color": "#a78bfa",
     "desc": "从遗址与碑刻里读一段历史",
     "types": ["人文"], "tags": ["历史", "世界遗产", "建筑", "寺庙", "5A"]},
    {"id": "night", "name": "夜游光影", "icon": "🌃", "color": "#818cf8",
     "desc": "天黑之后，这座城市才真正醒来",
     "types": ["夜游"], "tags": ["夜景", "灯光", "夜游", "游船"]},
    {"id": "citywalk", "name": "城市漫步", "icon": "🚶", "color": "#22d3ee",
     "desc": "不赶景点，走一条自己的路线",
     "types": ["城市"], "tags": ["步行街", "老街", "洋楼", "骑楼", "散步", "商圈"]},
    {"id": "escape", "name": "避暑纳凉", "icon": "🍃", "color": "#34d399",
     "desc": "往山上走，把夏天留在山下",
     "types": [], "tags": ["溶洞", "云海", "近郊", "避暑", "森林", "温泉", "湿地", "梯田", "爬山"]},
]

# 主题最低分：低于此值不展示，避免"人人都是自然风光"的伪差异
THEME_MIN_SCORE = 3
# 各主题单独门槛：越"人人都能沾边"的主题要求越高
THEME_MIN_OVERRIDE = {"food": 5, "nature": 4, "citywalk": 4, "humanities": 6, "escape": 3}


def theme_overview() -> list[dict[str, Any]]:
    """按玩法主题聚合城市。

    打分规则：类型命中 2 分，标签命中 1 分，同一景点只计一次类型分。
    分数达标才算这座城属于该主题，保证主题之间有区分度。
    """
    themes = []
    for rule in THEME_RULES:
        types = set(rule["types"])
        tags = set(rule["tags"])
        per_city: list[dict[str, Any]] = []
        for c in poi_svc.list_cities():
            hits, score = [], 0
            for p in poi_svc.get_pois(c["id"]):
                p_tags = set(p.get("tags", []))
                t_hit = p["type"] in types
                g_hit = bool(p_tags & tags)
                if not (t_hit or g_hit):
                    continue
                score += (2 if t_hit else 0) + (1 if g_hit else 0)
                hits.append(p)
            # 美食主题额外吃 cities.json 的 foods 字段（真实地方饮食清单）
            # 但只作微调，避免每城都有 foods 导致该主题退化成"全城通吃"
            if rule["id"] == "food":
                score += min(2, len(c.get("foods", [])))
            # 避暑纳凉看城市标签（"避暑之都""山城""海滨"等），POI 里没有这层信息
            if rule["id"] == "escape":
                city_tags = " ".join(c.get("tags", []))
                if any(k in city_tags for k in ("避暑", "山城", "高原", "海滨", "温泉", "海滨", "度假")):
                    score += 4
                # 夏季凉爽（最佳季在春秋，说明不是酷暑型）也算
                months = trend_svc.parse_season(c.get("best_season", ""))
                if months and date.today().month not in months:
                    score += 1
            if score < THEME_MIN_OVERRIDE.get(rule["id"], THEME_MIN_SCORE):
                continue
            hits.sort(key=lambda x: x["heat"], reverse=True)
            per_city.append({
                "city_id": c["id"], "city": c["name"], "province": c["province"],
                "accent": c["accent"], "count": len(hits), "score": score,
                "top": hits[0]["name"] if hits else "",
                "foods": c.get("foods", [])[:3],
                "top_rating": hits[0]["rating"] if hits else 0,
                "poi_count": len(poi_svc.get_pois(c["id"])),
            })
        per_city.sort(key=lambda x: (x["score"], x["count"], x["top_rating"]), reverse=True)
        themes.append({
            "id": rule["id"], "name": rule["name"], "icon": rule["icon"],
            "color": rule["color"], "desc": rule["desc"],
            "cities": per_city[:6], "total_cities": len(per_city),
            "total_pois": sum(x["count"] for x in per_city),
        })
    return themes


def food_cities(limit: int = 12) -> list[dict[str, Any]]:
    """一城一味：城市风味清单 + 招牌景观。

    地方风味以 cities.json 的 foods 字段为准（这是真实的地方饮食），
    招牌景观取 signature，街市型景点只作补充。
    """
    rows = []
    for c in poi_svc.list_cities():
        pois = poi_svc.get_pois(c["id"])
        markets = [p for p in pois if p["type"] in ("美食", "市井")]
        markets.sort(key=lambda x: x["heat"], reverse=True)
        rows.append({
            "city_id": c["id"], "city": c["name"], "province": c["province"],
            "accent": c["accent"], "foods": c.get("foods", []),
            "signature": c.get("signature", ""),
            "intro": c.get("intro", ""),
            "tags": c.get("tags", []),
            "markets": [{"name": p["name"], "rating": p["rating"], "best": p.get("best", ""),
                         "desc": p.get("desc", "")} for p in markets[:2]],
        })
    rows.sort(key=lambda r: (-len(r["foods"]), -len(r["markets"])))
    return rows[:limit]



def season_matrix() -> dict[str, Any]:
    """城市 × 12 月的最佳旅行季矩阵。"""
    rows = []
    for c in poi_svc.list_cities():
        months = sorted(_season_months(c.get("best_season", "")))
        rows.append({
            "city_id": c["id"], "city": c["name"], "province": c["province"],
            "accent": c["accent"], "months": months,
            "best_season": c.get("best_season", ""),
        })
    rows.sort(key=lambda r: len(r["months"]))
    return {"current_month": date.today().month, "cities": rows}


# ------------------------------------------------------------------ 经典路线

@lru_cache(maxsize=1)
def _load_routes() -> list[dict[str, Any]]:
    path = settings.data_dir / "routes.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def routes_now() -> list[dict[str, Any]]:
    """经典路线，标注当前是否处于推荐月份。"""
    month = date.today().month
    out = []
    for r in _load_routes():
        item = dict(r)
        item["in_season"] = month in r.get("best_months", [])
        item["season_hint"] = ("本月正当时" if item["in_season"]
                              else f"{r['best_months'][0]}月前后更合适")
        out.append(item)
    return out

