"""LangGraph 行程规划智能体。

图结构：
    START → intake（需求解析）→ context（工具调用：天气/景点/预算）
          → compose（行程生成，流式）→ review（结构校验）
          → [不通过且可重试] compose
          → [通过] END
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from app.agents.prompts import COMPOSE_PROMPT, INTAKE_PROMPT, REVIEW_PROMPT
from app.agents.state import PlanState
from app.agents.tools import tool_attractions, tool_budget, tool_weather
from app.config import settings
from app.core.llm import get_fast_llm, get_llm
from app.core.resilience import ainvoke
from app.services import budget as budget_svc
from app.services import poi as poi_svc
from app.services import weather as weather_svc

Emit = Callable[[dict[str, Any]], None]


def _emit(state: PlanState, **evt: Any) -> None:
    fn = state.get("emit")
    if fn:
        fn(evt)


def _fix_budget(plan: dict[str, Any]) -> None:
    """预算自洽：各项之和必须等于 total，模型算错时以分项为准。"""
    bb = plan.get("budget")
    if isinstance(bb, dict) and isinstance(bb.get("breakdown"), dict):
        bd = {k: v for k, v in bb["breakdown"].items() if isinstance(v, (int, float))}
        if bd:
            bb["breakdown"] = bd
            bb["total"] = sum(bd.values())


def _json_from_text(text: str) -> dict[str, Any]:
    """从模型输出里稳健地抠出 JSON。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start < 0:
        raise ValueError("模型输出中没有 JSON")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("JSON 括号未闭合")


# ---------------------------------------------------------------- intake
def _rule_brief(query: str) -> dict[str, Any]:
    """LLM 不可用时的规则兜底解析。"""
    city = None
    for c in poi_svc.list_cities():
        if c["name"] in query:
            city = c["name"]
            break
    m = re.search(r"(\d+)\s*(天|日)", query)
    days = int(m.group(1)) if m else (2 if "周末" in query else 3)
    level = next((k for k in ("经济", "舒适", "豪华", "中等") if k in query), "中等")
    prefs = [k for k in ("自然", "人文", "古镇", "美食", "夜游", "亲子", "城市", "体验", "文创")
             if k in query]
    companions = [k for k in ("带娃", "孩子", "老人", "情侣", "独自") if k in query]
    om = re.search(r"从([\u4e00-\u9fa5]{2,6}?)(?:出发|过去|飞|坐车|自驾)", query)
    return {"city": city, "origin": om.group(1) if om else None,
            "days": max(1, min(days, 10)),
            "people": 2, "budget_level": level, "prefs": prefs,
            "companions": companions, "pace": "轻松" if "轻松" in query or "慢" in query else "适中",
            "must_go": [], "avoid": [], "start_date": None, "note": ""}


async def intake_node(state: PlanState) -> PlanState:
    query = state["query"]
    _emit(state, type="step", key="intake", status="start",
          label="解析需求", detail="拆解目的地、天数、预算与偏好")

    brief: dict[str, Any] = {}
    if settings.llm_ready:
        try:
            msg = await ainvoke(get_fast_llm(0.2), [
                {"role": "system", "content": "你是精确的结构化信息抽取器，只输出 JSON。"},
                {"role": "user", "content": INTAKE_PROMPT.format(query=query)},
            ])
            brief = _json_from_text(str(msg.content))
        except Exception:  # noqa: BLE001
            brief = {}

    rule = _rule_brief(query)
    for k, v in rule.items():
        if not brief.get(k):
            brief[k] = v
    # 前端显式选择的出发地优先级最高
    if state.get("origin_hint"):
        brief["origin"] = state["origin_hint"]

    # 城市兜底
    city = poi_svc.find_city(brief.get("city") or "") or poi_svc.find_city(
        next((c["name"] for c in poi_svc.list_cities() if c["name"] in query), "")
    )
    if city:
        brief["city"] = city["name"]
        brief["city_id"] = city["id"]

    brief.setdefault("people", 2)
    brief.setdefault("budget_level", "中等")
    brief.setdefault("pace", "适中")
    brief.setdefault("prefs", [])
    brief.setdefault("companions", [])
    brief.setdefault("must_go", [])
    brief.setdefault("avoid", [])
    try:
        brief["days"] = max(1, min(int(brief.get("days") or 3), 10))
    except (TypeError, ValueError):
        brief["days"] = 3

    _emit(state, type="step", key="intake", status="done",
          label="解析需求",
          detail=f"{brief.get('city') or '待定'} · {brief['days']} 天 · {brief['people']} 人 · "
                 f"{brief['budget_level']} · {'/'.join(brief['prefs']) or '均衡'}")
    return {"brief": brief}


# ---------------------------------------------------------------- context
async def context_node(state: PlanState) -> PlanState:
    brief = state["brief"]
    city = poi_svc.get_city(brief.get("city_id", ""))
    _emit(state, type="step", key="context", status="start",
          label="采集实时数据", detail="拉取气象实况与本地景点池")

    if not city:
        _emit(state, type="step", key="context", status="error",
              label="采集实时数据", detail="未识别到目的地城市")
        return {"errors": ["未识别目的地城市"], "ok": False}

    weather_raw, cand_raw = await asyncio.gather(
        tool_weather.ainvoke({"city_name": city["name"]}),
        tool_attractions.ainvoke({
            "city_name": city["name"],
            "preference": " ".join(brief.get("prefs", [])) + " " + " ".join(brief.get("companions", [])),
            "budget": brief.get("budget_level", "中等"),
            "limit": 10,
        }),
    )
    weather = json.loads(weather_raw)
    candidates = json.loads(cand_raw)

    budget = json.loads(await tool_budget.ainvoke({
        "days": brief["days"], "people": brief["people"],
        "level": brief.get("budget_level", "中等"),
        "origin": brief.get("origin") or "",
        "destination": city["name"],
    }))

    daily = weather.get("daily", [])
    cur = weather.get("current", {})
    _emit(state, type="step", key="context", status="done", label="采集实时数据",
          detail=f"{cur.get('text', '')} {cur.get('temp', '')}℃ · 候选景点 {len(candidates)} 个 · "
                 f"数据源 {weather.get('source', '')}")
    return {"city": city, "weather": weather, "candidates": candidates,
            "brief": {**brief, "budget_ref": budget}, "errors": [], "retries": 0}


# ---------------------------------------------------------------- compose
async def compose_node(state: PlanState) -> PlanState:
    brief, city = state["brief"], state["city"]
    days = brief["days"]
    _emit(state, type="step", key="compose", status="start",
          label="编排每日行程", detail=f"为 {days} 天安排景点、餐饮与住宿")

    start = brief.get("start_date")
    try:
        start_day = datetime.strptime(start, "%Y-%m-%d").date() if start else date.today() + timedelta(days=1)
    except (TypeError, ValueError):
        start_day = date.today() + timedelta(days=1)

    weather_list = state["weather"].get("daily", [])[:days]
    # 预报窗口只有 7 天；超出部分用末日数据外推，避免长行程后段没有天气
    if weather_list:
        while len(weather_list) < days:
            weather_list.append({**weather_list[-1], "extrapolated": True})
    weather_txt = json.dumps([{**w, "date": (start_day + timedelta(days=i)).isoformat()}
                              for i, w in enumerate(weather_list)], ensure_ascii=False) \
        if len(weather_list) >= days else json.dumps(weather_list, ensure_ascii=False)

    cand_txt = json.dumps([{k: c.get(k) for k in ("name", "type", "rating", "hours", "ticket",
                                                  "best", "desc", "tags")}
                           | {"indoor": c.get("indoor", False),
                              "weather_fit": c.get("weather_fit", 80)}
                           for c in state["candidates"]], ensure_ascii=False)

    prompt = COMPOSE_PROMPT.format(
        city=city["name"], days=days,
        brief=json.dumps(brief, ensure_ascii=False),
        weather=weather_txt, candidates=cand_txt,
        budget=json.dumps(brief.get("budget_ref", {}), ensure_ascii=False),
        today=date.today().isoformat(),
    )

    chunks: list[str] = []
    total_chars = 0
    shown = 0
    raw = ""
    try:
        async for piece in get_llm(0.55).astream(prompt):
            text = piece.content if isinstance(piece.content, str) else str(piece.content)
            chunks.append(text)
            total_chars += len(text)
            if total_chars - shown > 160:
                shown = total_chars
                _emit(state, type="step", key="compose", status="progress",
                      label="编排每日行程", detail=f"已生成 {shown} 字…")
        raw = "".join(chunks)
    except Exception as exc:  # noqa: BLE001
        _emit(state, type="step", key="compose", status="warn", label="编排每日行程",
              detail=f"模型异常，启用规则兜底（{exc}）")
        plan = _fallback_plan(city, state["candidates"], brief, weather_list, start_day)
        return {"plan": plan, "raw": "",
                "errors": [f"模型调用失败，已用规则模板兜底：{exc}"], "ok": False}

    # 归一化日期与基础字段
    raw_err = ""
    try:
        plan = _json_from_text(raw)
        plan.setdefault("city", city["name"])
        plan.setdefault("days", days)
        _fix_budget(plan)
        for i, d in enumerate(plan.get("itinerary", [])):
            d["day"] = i + 1
            d["date"] = (start_day + timedelta(days=i)).isoformat()
            if i < len(weather_list):
                w = weather_list[i]
                d["weather"] = {"text": w.get("text"), "t_min": w.get("t_min"),
                                "t_max": w.get("t_max"), "rain_prob": w.get("rain_prob")}
    except Exception as exc:  # noqa: BLE001
        plan = {}
        raw_err = str(exc)

    if not plan.get("itinerary"):
        plan = _fallback_plan(city, state["candidates"], brief, weather_list, start_day)
        raw_err = raw_err or "模型输出缺少 itinerary"
        _emit(state, type="step", key="compose", status="warn", label="编排每日行程",
              detail="结构不完整，已切规则模板兜底")

    _emit(state, type="step", key="compose", status="done", label="编排每日行程",
          detail=f"输出 {len(chunks)} 段，共 {len(raw)} 字")
    return {"plan": plan, "raw": raw,
            "errors": [f"已降级兜底：{raw_err}"] if raw_err else []}


def _fallback_plan(city: dict[str, Any], candidates: list[dict[str, Any]],
                   brief: dict[str, Any], weather_list: list[dict[str, Any]],
                   start_day: date) -> dict[str, Any]:
    """模型不可用时的规则兜底：按天气挑景点、按时间槽排程，保证永远有可交付行程。"""
    days = brief["days"]
    people = brief.get("people", 2)
    foods = city.get("foods") or ["当地特色小吃"]
    pool = candidates or poi_svc.get_pois(city["id"])
    slots = ["09:00", "13:30", "16:30"]
    per_day = 3 if len(pool) >= days * 3 else 2

    itinerary, used, tickets = [], 0, 0
    for di in range(days):
        w = weather_list[di] if di < len(weather_list) else {}
        rainy = (w.get("rain_prob") or 0) >= 55
        sub = [p for p in pool if p.get("indoor")] if rainy else list(pool)
        if len(sub) < per_day:
            sub = list(pool)
        picks = [sub[(used + k) % len(sub)] for k in range(min(per_day, len(sub)))]
        used += per_day

        items = []
        for k, p in enumerate(picks):
            tickets += p["ticket"]
            items.append({
                "time": slots[k] if k < len(slots) else "17:00",
                "name": p["name"], "type": p["type"],
                "hours": p["hours"], "cost": p["ticket"],
                "transport": "打车/公交前往，市内通勤约 20-40 分钟",
                "desc": p.get("desc", ""),
                "tip": f'最佳时段 {p.get("best", "全天")}，建议预留 {p["hours"]} 小时',
            })
        meals = [
            {"time": "08:00", "name": f"{foods[di % len(foods)]} 早餐", "place": "住宿周边", "cost": 25},
            {"time": "12:30", "name": foods[(di + 1) % len(foods)], "place": "景区附近", "cost": 60},
            {"time": "18:30", "name": foods[(di + 2) % len(foods)], "place": "老城区", "cost": 80},
        ]
        day_cost = sum(i["cost"] for i in items) + sum(m["cost"] for m in meals) + 120
        itinerary.append({
            "day": di + 1, "date": (start_day + timedelta(days=di)).isoformat(),
            "title": f"第 {di + 1} 天 · {'雨天室内线' if rainy else '经典打卡线'}",
            "weather": {"text": w.get("text"), "t_min": w.get("t_min"),
                        "t_max": w.get("t_max"), "rain_prob": w.get("rain_prob")},
            "items": items, "meals": meals,
            "stay": f'{city["name"]}市区（交通便利）', "day_cost": day_cost,
        })

    est = budget_svc.estimate(days=days, people=people,
                              level=brief.get("budget_level", "中等"),
                              origin=brief.get("origin") or "",
                              dest=city["name"], tickets=tickets)
    return {
        "city": city["name"], "days": days,
        "theme": f'{city["name"]} {days} 日经典路线（规则模板）',
        "summary": (f'按天气与景点热度自动排布：{"、".join(i["items"][0]["name"] for i in itinerary)} 作为每日开场。'
                    f'节奏适中，门票合计约 ¥{tickets}。此为模型不可用时的兜底方案，建议重试获取更精细的个性化排程。'),
        "highlights": [p["name"] for i in itinerary for p in i["items"]][:4],
        "budget": {"total": est["total"], "breakdown": est["breakdown"]},
        "itinerary": itinerary,
        "tips": ["景点门票建议提前 1 天在线预约", "避开 10:00-15:00 客流高峰",
                 f'当地美食推荐：{"、".join(foods)}'],
        "packing": ["身份证件", "舒适步行鞋", "雨具", "充电宝"],
    }


# ---------------------------------------------------------------- review
TIMES = ["09:00", "13:30", "16:30", "18:30"]


def _rule_repair(plan: dict[str, Any], candidates: list[dict[str, Any]],
                 city: dict[str, Any], days: int) -> dict[str, Any]:
    """确定性就地修补：删幻觉景点、补空缺、去重、补餐食。不调用模型。"""
    if not isinstance(plan, dict):
        return plan
    known = {c["name"]: c for c in candidates}
    itin = plan.get("itinerary")
    if not isinstance(itin, list) or not itin:
        return plan

    # 天数对齐
    while len(itin) < days:
        itin.append({"day": len(itin) + 1, "title": f"第 {len(itin) + 1} 天",
                     "items": [], "meals": []})
    itin = itin[:days]

    used: set[str] = set()
    for idx, d in enumerate(itin):
        d["day"] = idx + 1
        raw_items = d.get("items") or []
        fixed: list[dict[str, Any]] = []

        for pos, it in enumerate(raw_items):
            if not isinstance(it, dict):
                continue
            name = str(it.get("name") or "").strip()
            if name in known and name not in used:
                used.add(name)
                it.setdefault("time", TIMES[min(pos, len(TIMES) - 1)])
                fixed.append(it)
                continue
            # 幻觉景点 / 重复景点 → 找一个同类型且未用过的候选替换
            want = it.get("type")
            alt = next((c for c in candidates
                        if c["name"] not in used and c.get("type") == want), None) \
                or next((c for c in candidates if c["name"] not in used), None)
            if alt:
                used.add(alt["name"])
                fixed.append({
                    "time": it.get("time") or TIMES[min(pos, len(TIMES) - 1)],
                    "name": alt["name"], "type": alt["type"],
                    "hours": alt["hours"], "cost": alt["ticket"],
                    "transport": it.get("transport") or "市内步行/打车前往",
                    "desc": alt.get("desc", ""),
                    "tip": f'最佳时段 {alt.get("best", "全天")}，建议预留 {alt["hours"]} 小时',
                })
            # 没有可替换的候选就丢弃该项

        # 不足 2 个则补齐
        for c in candidates:
            if len(fixed) >= 2:
                break
            if c["name"] in used:
                continue
            used.add(c["name"])
            fixed.append({
                "time": TIMES[min(len(fixed), len(TIMES) - 1)],
                "name": c["name"], "type": c["type"], "hours": c["hours"], "cost": c["ticket"],
                "transport": "市内步行/打车前往", "desc": c.get("desc", ""),
                "tip": f'最佳时段 {c.get("best", "全天")}',
            })
        d["items"] = fixed

        if not d.get("meals"):
            foods = city.get("foods") or ["当地特色小吃"]
            d["meals"] = [
                {"time": "08:00", "name": f"{foods[0]} 早点", "place": "住宿周边", "cost": 20},
                {"time": "12:30", "name": foods[1 % len(foods)], "place": "景区附近", "cost": 60},
                {"time": "18:30", "name": foods[2 % len(foods)], "place": "老城区", "cost": 70},
            ]
        d["day_cost"] = sum(int(i.get("cost") or 0) for i in d["items"]) + \
            sum(int(m.get("cost") or 0) for m in d.get("meals", [])) + 100

    plan["itinerary"] = itin
    _fix_budget(plan)
    return plan


def validate(plan: dict[str, Any], days: int,
             candidates: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """分级校验：errors 会阻断交付并触发自动修复，warnings 只做提示。"""
    errors: list[str] = []
    warnings: list[str] = []
    if not plan:
        return ["行程为空"], []
    for field in ("summary", "itinerary", "budget"):
        if not plan.get(field):
            errors.append(f"缺少字段 {field}")
    itin = plan.get("itinerary") or []
    if len(itin) != days:
        errors.append(f"行程天数应为 {days} 天，实际 {len(itin)} 天")
    known = {c["name"] for c in candidates}
    for i, d in enumerate(itin, 1):
        items = d.get("items") or []
        if not items:
            errors.append(f"第 {i} 天没有任何景点")
        elif len(items) < 2:
            warnings.append(f"第 {i} 天仅 {len(items)} 个景点，节奏偏松")
        for it in items:
            if not it.get("time"):
                warnings.append(f"第 {i} 天有景点缺少时间")
            if not it.get("name"):
                errors.append(f"第 {i} 天有景点缺少名称")
            elif it["name"] not in known:
                errors.append(f"第 {i} 天景点「{it['name']}」不在候选池中（疑似编造）")
        if not d.get("meals"):
            warnings.append(f"第 {i} 天缺少餐饮安排")

    # 景点重复检测：候选池够用时重复视为硬伤
    counter = Counter(it.get("name") for d in itin for it in (d.get("items") or []))
    enough = len(candidates) >= days * 2
    for name, cnt in counter.items():
        if name and cnt > 1:
            msg = f"景点「{name}」被重复安排 {cnt} 次"
            (errors if enough else warnings).append(msg + ("，应换其他候选" if enough else ""))

    total = plan.get("budget", {}).get("total") if isinstance(plan.get("budget"), dict) else None
    if not isinstance(total, (int, float)):
        errors.append("budget.total 必须是数字")
    return errors, warnings


async def review_node(state: PlanState) -> PlanState:
    plan = state.get("plan") or {}
    days = state["brief"]["days"]
    _emit(state, type="step", key="review", status="start", label="质量校验",
          detail="检查天数、景点真实性、餐饮完整性")
    errors, warnings = validate(plan, days, state["candidates"])
    retries = state.get("retries", 0)

    # 第一道：规则层确定性修补（毫秒级，无需模型）
    if errors:
        _emit(state, type="step", key="review", status="warn", label="质量校验",
              detail=f"发现 {len(errors)} 处硬伤，规则层就地修补")
        repaired = _rule_repair(copy.deepcopy(plan), state["candidates"],
                                state.get("city") or {}, days)
        e2, w2 = validate(repaired, days, state["candidates"])
        if len(e2) <= len(errors):
            plan, errors, warnings = repaired, e2, w2

    # 第二道：仍有问题才动用模型兜底
    if errors and retries < 1 and state.get("raw"):
        _emit(state, type="step", key="review", status="warn", label="质量校验",
              detail=f"规则修补后仍有 {len(errors)} 处，调用模型二次修正")
        try:
            msg = await ainvoke(get_fast_llm(0.1), [
                {"role": "system", "content": "你是 JSON 修复器，只输出修正后的完整 JSON。"},
                {"role": "user", "content": REVIEW_PROMPT.format(errors="\n".join(errors[:8]),
                                                                 raw=state["raw"][:12000])},
            ])
            fixed = _json_from_text(str(msg.content))
            _fix_budget(fixed)
            for i, d in enumerate(fixed.get("itinerary", [])):
                d["day"] = i + 1
                if not d.get("date"):
                    d["date"] = (date.today() + timedelta(days=1 + i)).isoformat()
            new_errors, new_warnings = validate(fixed, days, state["candidates"])
            if len(new_errors) <= len(errors):
                plan, errors, warnings = fixed, new_errors, new_warnings
        except Exception:  # noqa: BLE001
            pass

    ok = len(errors) == 0
    if ok:
        detail = "结构完整，可交付" if not warnings else f"可交付，{len(warnings)} 条节奏提示"
        _emit(state, type="step", key="review", status="done", label="质量校验", detail=detail)
    else:
        _emit(state, type="step", key="review", status="warn", label="质量校验",
              detail=f"仍有 {len(errors)} 处问题：{errors[0]}")

    return {"plan": plan, "errors": errors, "warnings": warnings,
            "retries": retries + 1, "ok": ok}


def route_after_review(state: PlanState) -> str:
    """review 节点内部已完成一次修复，正常直接交付；仅在行程为空时重排一次。"""
    plan = state.get("plan") or {}
    if not plan.get("itinerary") and state.get("retries", 0) < 2:
        return "compose"
    return END


# ---------------------------------------------------------------- graph
_graph = None


def build_graph():
    global _graph
    if _graph is not None:
        return _graph
    g = StateGraph(PlanState)
    g.add_node("intake", intake_node)
    g.add_node("context", context_node)
    g.add_node("compose", compose_node)
    g.add_node("review", review_node)
    g.add_edge(START, "intake")
    g.add_edge("intake", "context")
    g.add_edge("context", "compose")
    g.add_edge("compose", "review")
    g.add_conditional_edges("review", route_after_review, {"compose": "compose", END: END})
    _graph = g.compile()
    return _graph


async def run_plan(query: str, emit: Emit, origin: str = "") -> dict[str, Any]:
    """执行图，过程中通过 emit 回调节点事件。"""
    graph = build_graph()
    state = await graph.ainvoke({"query": query, "emit": emit, "errors": [], "retries": 0,
                                 "origin_hint": origin})
    return {
        "ok": state.get("ok", False),
        "plan": state.get("plan", {}),
        "brief": state.get("brief", {}),
        "city": {k: v for k, v in (state.get("city") or {}).items() if k != "poi_count"},
        "weather": state.get("weather", {}),
        "errors": state.get("errors", []),
        "warnings": state.get("warnings", []),
        "candidates": state.get("candidates", []),
    }
