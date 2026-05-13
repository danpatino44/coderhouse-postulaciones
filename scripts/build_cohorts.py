#!/usr/bin/env python3
"""
Fetches NOT_STARTED cohorts from Coderhouse backoffice M2M API,
filters those without a PROFESOR/INSTRUCTOR assigned, enriches with
product title, and writes cohorts.json next to index.html.

Required env vars:
  BACKOFFICE_API_URL
  CLAUDE_STUDENT_API_KEY
  CLAUDE_FINANCE_API_KEY
"""
import http.client
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_URL = os.environ["BACKOFFICE_API_URL"].rstrip("/")
STUDENT_KEY = os.environ["CLAUDE_STUDENT_API_KEY"]
FINANCE_KEY = os.environ["CLAUDE_FINANCE_API_KEY"]

TEACHER_ROLES = {"PROFESOR", "INSTRUCTOR"}
OUT_PATH = Path(__file__).resolve().parent.parent / "cohorts.json"
# Only publish cohorts starting within this window from "today".
DAYS_AHEAD = int(os.environ.get("DAYS_AHEAD", "60"))


def fetch(path: str, key: str, *, retries: int = 3) -> dict:
    headers = {
        "X-API-Key": key,
        "Accept": "application/json",
        "User-Agent": "coderhouse-postulaciones/1.0",
    }
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(API_URL + path, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.HTTPException) as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed after {retries} retries: {path}") from last_err


def fetch_all_pages(path_base: str, key: str, items_key: str = "items", page_key: str = "totalPages", limit: int = 100) -> list:
    out: list = []
    sep = "&" if "?" in path_base else "?"
    first = fetch(f"{path_base}{sep}page=1&limit={limit}", key)
    if items_key in first:
        out.extend(first[items_key])
        total_pages = first.get(page_key) or (first.get("pagination") or {}).get("totalPages") or 1
    elif "data" in first:
        out.extend(first["data"])
        total_pages = (first.get("pagination") or {}).get("totalPages") or 1
    else:
        raise RuntimeError(f"unexpected shape for {path_base}: {list(first)[:5]}")
    for p in range(2, total_pages + 1):
        r = fetch(f"{path_base}{sep}page={p}&limit={limit}", key)
        out.extend(r.get(items_key) or r.get("data") or [])
    return out


def fetch_not_started_cohorts() -> list:
    return fetch_all_pages(
        "/student/enrollment/m2m/admin/cohorts?status=NOT_STARTED", STUDENT_KEY, limit=100
    )


def fetch_active_assignments() -> list:
    return fetch_all_pages(
        "/platform/staff/m2m/admin/assignments?status=ACTIVE", STUDENT_KEY, limit=100
    )


def fetch_product_title(product_id: str) -> str:
    """Return the default localization title, falling back to slug."""
    try:
        p = fetch(f"/finance/product/m2m/products/{product_id}", FINANCE_KEY)
        for loc in p.get("localizations") or []:
            if loc.get("isDefault") and loc.get("title"):
                return loc["title"]
        for loc in p.get("localizations") or []:
            if loc.get("title"):
                return loc["title"]
        return p.get("slug", "")
    except Exception:
        return ""


DAY_NAMES_ES = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]


def fmt_schedule(start_iso: str | None, week_days: list[int] | None) -> str:
    """Return e.g. 'Lun y Mié — 20:30 ART'. Times are converted from UTC to ART (UTC-3)."""
    if not start_iso:
        return ""
    try:
        s_utc = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        s_art = s_utc - timedelta(hours=3)
        time_str = s_art.strftime("%H:%M")
    except Exception:
        time_str = ""
    if not week_days:
        return f"{time_str} ART" if time_str else ""
    days = [DAY_NAMES_ES[d] for d in week_days if 0 <= d <= 6]
    if len(days) == 1:
        days_str = days[0]
    elif len(days) == 2:
        days_str = f"{days[0]} y {days[1]}"
    else:
        days_str = ", ".join(days[:-1]) + f" y {days[-1]}"
    return f"{days_str} — {time_str} ART" if time_str else days_str


def fmt_date_dmy(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return d.strftime("%d/%m/%Y")
    except Exception:
        return ""


def main() -> int:
    print("[1/4] Fetching NOT_STARTED cohorts...", flush=True)
    cohorts = fetch_not_started_cohorts()
    print(f"      -> {len(cohorts)} NOT_STARTED cohorts", flush=True)

    print("[2/4] Fetching ACTIVE staff assignments...", flush=True)
    assignments = fetch_active_assignments()
    print(f"      -> {len(assignments)} ACTIVE assignments", flush=True)

    cohorts_with_teacher = {
        a["cohortId"] for a in assignments
        if a.get("cohortRole") in TEACHER_ROLES and a.get("status") == "ACTIVE"
    }
    print(f"      -> {len(cohorts_with_teacher)} cohorts already have PROFESOR/INSTRUCTOR", flush=True)

    needs_teacher_all = [c for c in cohorts if c["id"] not in cohorts_with_teacher]
    print(f"[3/4] Cohorts NOT_STARTED without teacher (all): {len(needs_teacher_all)}", flush=True)

    today = datetime.now(timezone.utc)
    window_end = today + timedelta(days=DAYS_AHEAD)
    needs_teacher = []
    for c in needs_teacher_all:
        sd = c.get("startDate")
        if not sd:
            continue
        try:
            dt = datetime.fromisoformat(sd.replace("Z", "+00:00"))
        except ValueError:
            continue
        if today <= dt <= window_end:
            needs_teacher.append(c)
    print(f"      -> within next {DAYS_AHEAD} days: {len(needs_teacher)}", flush=True)

    product_ids = sorted({c.get("productId") for c in needs_teacher if c.get("productId")})
    print(f"      -> resolving {len(product_ids)} product titles...", flush=True)
    titles: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_product_title, pid): pid for pid in product_ids}
        for f in as_completed(futures):
            titles[futures[f]] = f.result()

    print("[4/4] Writing cohorts.json...", flush=True)
    out = []
    for c in needs_teacher:
        pid = c.get("productId", "")
        title = titles.get(pid, "").strip() or c.get("name", "")
        out.append({
            "id": c["id"],
            "title": title,
            "schedule": fmt_schedule(c.get("startDate"), c.get("weekDays")),
            "start": fmt_date_dmy(c.get("startDate")),
            "end": fmt_date_dmy(c.get("endDate")),
            "cid": str(c.get("commissionNumber") or ""),
            "modality": c.get("modality", ""),
            "country": c.get("country", ""),
            "active": True,
        })

    out.sort(key=lambda r: (r["start"][6:10] + r["start"][3:5] + r["start"][0:2]) if r["start"] else "9999")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(out),
        "cohorts": out,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"      -> {OUT_PATH}  ({len(out)} cohorts published)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
