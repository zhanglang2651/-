"""行程局部修改：只重排指定某一天，不重跑整条链路。

为什么要单独做：全量重生成一次要 40-90 秒、烧 4-6k tokens，
而用户「把第二天换成户外」这种诉求只需要改一天。
"""
from __future__ import annotations

import json
from typing import Any

from app.agents.graph import _json_from_text, _rule_repair
from app.core.llm import get_llm
from app.core.resilience import ainvoke
from app.services import poi as poi_svc

REVISE_PROMPT = """你在修改一份已存在行程中的**某一天**，其他天保持不变。

城市：{city}
这一天是：Day {day}（{date}）
用户要求：{instruction}

【这一天当前的安排】
{current}

【可用景点池】只能从这里选，名字必须完全一致：
{candidates}

【其他天已经用过的景点】这次尽量不要重复：
{used}

请按用户要求重排这一天，输出严格 JSON（不要 markdown 代码块，不要解释）：
{{
  "day": {day},
  "date": "{date}",
  "title": "当日主题（12 字内）",
  "items": [
    {{"time": "09:00", "name": "景点名", "type": "自然", "hours": 3, "cost": 0,
      "transport": "地铁/打车约 20 分钟", "desc": "20-40 字，说清为什么这个时间去、看什么",
      "tip": "一句实用提醒"}}
  ],
  "meals": [
    {{"time": "12:30", "name": "餐食名", "place": "区域或店名", "cost": 60}}
  ],
  "stay": "建议住宿区域",
  "day_cost": 数字
}}

硬要求：
1. 2-4 个景点，景点必须来自【可用景点池】。
2. 门票、时长用池中真实数字，不得编造。
3. 保留原安排里合理、用户没要求改动的部分。
4. 三餐饮全，早餐只能是当地早点。"""


async def revise_day(plan: dict[str, Any], day_no: int,
                     instruction: str) -> dict[str, Any]:
    """返回修改后的完整 plan。day_no 从 1 开始。"""
    itin = plan.get("itinerary") or []
    if not (1 <= day_no <= len(itin)):
        raise ValueError(f"行程只有 {len(itin)} 天，无法修改第 {day_no} 天")

    city = poi_svc.find_city(plan.get("city") or "")
    if not city:
        raise ValueError("无法识别行程所在城市")

    current = itin[day_no - 1]
    target_date = current.get("date", "")
    others = {
        it.get("name") for i, d in enumerate(itin) if i != day_no - 1
        for it in (d.get("items") or [])
    }
    pool = [c for c in poi_svc.get_pois(city["id"]) if c["name"] not in others]
    if len(pool) < 2:
        pool = poi_svc.get_pois(city["id"])

    cand_txt = json.dumps(
        [{k: c[k] for k in ("name", "type", "hours", "ticket", "best", "desc", "indoor")}
         for c in pool], ensure_ascii=False)

    prompt = REVISE_PROMPT.format(
        city=city["name"], day=day_no, date=target_date,
        instruction=instruction.strip() or "让这一天更合理、节奏更顺",
        current=json.dumps(current, ensure_ascii=False),
        candidates=cand_txt,
        used="、".join(sorted(n for n in others if n)) or "无",
    )

    msg = await ainvoke(get_llm(0.4), prompt)
    day_data = _json_from_text(str(msg.content))

    # 补齐必要字段
    day_data["day"] = day_no
    day_data["date"] = day_data.get("date") or target_date
    if not day_data.get("title"):
        day_data["title"] = current.get("title") or f"第 {day_no} 天"
    if not day_data.get("weather"):
        day_data["weather"] = current.get("weather", {})

    # 复用规则修补：清幻觉景点、去重、补餐、算当日花费
    tmp = {"itinerary": [day_data], "budget": {"total": 0, "breakdown": {"其他": 1}}}
    fixed = _rule_repair(tmp, pool, city, 1)
    new_day = fixed["itinerary"][0]
    new_day["day"] = day_no
    new_day["date"] = target_date
    new_day["weather"] = current.get("weather", {})

    itin[day_no - 1] = new_day
    plan["itinerary"] = itin

    # 预算自洽：门票按新行程重算
    tickets = sum(int(it.get("cost") or 0) for d in itin for it in (d.get("items") or []))
    budget = plan.setdefault("budget", {})
    breakdown = budget.setdefault("breakdown", {})
    if "门票" in breakdown or tickets:
        breakdown["门票"] = tickets
    budget["total"] = sum(v for v in breakdown.values() if isinstance(v, (int, float)))
    return plan
