#!/usr/bin/env python3
"""Fetch live observations and forecasts from Zhejiang's public typhoon API."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

API = "https://typhoon.slt.zj.gov.cn/Api"
HEADERS = ["-H", "Referer: https://typhoon.slt.zj.gov.cn/", "-H", "Accept: application/json"]


def fetch(url):
    result = subprocess.run(["curl", "--fail", "--silent", "--show-error", "--max-time", "25", *HEADERS, url], check=True, capture_output=True, timeout=30)
    return json.loads(result.stdout.decode("utf-8-sig"))


def num(value):
    try:
        return float(value) if value not in (None, "", "--", "-") else None
    except (TypeError, ValueError):
        return None


listing = fetch(API + "/TyhoonActivity")
if not isinstance(listing, list):
    raise SystemExit("Unexpected active typhoon response")
storms = []
for item in listing:
    sid = item.get("tfid") or item.get("id")
    if not sid:
        continue
    detail = fetch(API + "/TyphoonInfo/" + str(sid))
    raw_points = detail.get("points", []) if isinstance(detail, dict) else []
    history = []
    for p in raw_points:
        lat, lng = num(p.get("lat")), num(p.get("lng"))
        if lat is not None and lng is not None:
            history.append({"time": p.get("time"), "lat": lat, "lng": lng, "windLevel": num(p.get("power")), "windSpeed": num(p.get("speed")), "pressure": num(p.get("pressure")), "moveDirection": p.get("movedirection"), "moveSpeed": num(p.get("movespeed"))})
    current = {"time": item.get("time"), "lat": num(item.get("lat")), "lng": num(item.get("lng")), "windLevel": num(item.get("power")), "windSpeed": num(item.get("speed")), "pressure": num(item.get("pressure")), "moveDirection": item.get("movedirection"), "moveSpeed": num(item.get("movespeed"))}
    if current["lat"] is None and history:
        current = history[-1]
    blocks = raw_points[-1].get("forecast", []) if raw_points else []
    china = next((x for x in blocks if str(x.get("tm", "")).startswith("中国") and x.get("tm") == "中国"), None)
    forecast = []
    for p in (china or {}).get("forecastpoints", []):
        lat, lng = num(p.get("lat")), num(p.get("lng"))
        if lat is not None and lng is not None:
            forecast.append({"agency": "中国", "time": p.get("time"), "lat": lat, "lng": lng, "windLevel": num(p.get("power")), "windSpeed": num(p.get("speed")), "pressure": num(p.get("pressure"))})
    storms.append({"id": str(sid), "number": str(item.get("tfid", sid)), "name": detail.get("name", item.get("name")), "englishName": detail.get("enname", item.get("enname")), "active": str(detail.get("isactive", "1")) != "0", "intensity": item.get("strong"), "warningLevel": detail.get("warnlevel", item.get("warnlevel")), "current": current, "history": history, "forecast": forecast})

result = {"schemaVersion": 1, "mode": "live", "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": "浙江省水利厅·实时台风路径发布系统", "sourceUrl": "https://typhoon.slt.zj.gov.cn/", "storms": storms, "warnings": [], "warningNote": "此接口未提供可验证的市县级官方预警明细；请查看所在地气象台发布。"}
Path("data/typhoon.json").parent.mkdir(parents=True, exist_ok=True)
Path("data/typhoon.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Fetched", len(storms), "active storm(s)")
