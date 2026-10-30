"""Vendor engine — pure functions, dicts in / out.

Covers: compliance vs fest window, dietary coverage matrix, interruption reroute
and settlement with manual rates (rates are not in the pack).
"""
from __future__ import annotations

from datetime import date, datetime

from app import config as C


def _d(v) -> date | None:
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    return None


def compliance(vendors: list[dict], fest_start: str, fest_end: str) -> dict:
    """Cert expiry vs fest days. EXPIRED and EXPIRING_MID_FEST are hard findings."""
    fs, fe = _d(fest_start), _d(fest_end)
    out = []
    for v in vendors:
        expiry = _d(v.get("hygiene_cert_expiry"))
        entry = {"vendor_id": v["id"], "raw_id": v.get("raw_id"), "name": v.get("name"),
                 "expiry": expiry.isoformat() if expiry else None,
                 "status_code": "UNKNOWN",
                 "action_required": "obtain the certificate date; a vendor without "
                                    "verifiable compliance cannot be relied on"}
        if expiry is None:
            entry["status_code"] = "MISSING_CERT_DATE"
        elif fe and fs and expiry < fs:
            entry["status_code"] = "EXPIRED"
        elif fe and expiry <= fe:
            entry["status_code"] = "EXPIRING_MID_FEST"
        else:
            entry["status_code"] = "OK"
            entry["action_required"] = None
        out.append(entry)
    return {"fest_start": fs.isoformat() if fs else None,
            "fest_end": fe.isoformat() if fe else None, "vendors": out,
            "expired": [e["raw_id"] for e in out if e["status_code"] == "EXPIRED"],
            "expiring": [e["raw_id"] for e in out if e["status_code"]
                         == "EXPIRING_MID_FEST"]}


def normalize_tag(tag: str | None) -> str | None:
    if not tag:
        return None
    t = tag.strip().lower()
    if t in C.VENDORS["PARTICIPANT_TAG_MAP"]:
        return C.VENDORS["PARTICIPANT_TAG_MAP"][t]
    if t in C.VENDORS["DIET_TAGS"]:
        return t
    return None


def coverage_matrix(vendors: list[dict], participants: list[dict],
                    fest_days: list[str]) -> dict:
    """Dietary demand per day vs vendor coverage; uncovered diet tags are findings."""
    demand: dict[str, int] = {}
    for p in participants:
        for tag in (p.get("dietary_tags") or []):
            t = normalize_tag(tag)
            if t:
                demand[t] = demand.get(t, 0) + 1
    covers: dict[str, set[str]] = {}
    for v in vendors:
        tags = {normalize_tag(t) or str(t).lower() for t in (v.get("dietary_coverage") or [])}
        covers[v["id"]] = tags
    matrix = {}
    for tag, n in sorted(demand.items()):
        serving = [v["id"] for v in vendors if tag in covers.get(v["id"], set())]
        matrix[tag] = {"demand": n, "vendors": serving,
                       "unmet": n if not serving else 0}
    return {"days": fest_days, "matrix": matrix,
            "uncovered_tags": [t for t, m in matrix.items() if not m["vendors"]]}


def reroute_on_interruption(vendor_id: int, vendors: list[dict], orders: list[dict],
                            fest_days: list[str]) -> dict:
    """Vendor goes interrupted: affected orders move to other vendors with menu
    coverage; impossible moves surface as unmet_with_reason (never silently dropped)."""
    affected = [o for o in orders if o.get("vendor_id") == vendor_id]
    others = [v for v in vendors if v["id"] != vendor_id
              and (v.get("status") or "active") == "active"]
    plan = {"interrupted_vendor": vendor_id, "moves": [], "unmet": []}
    for o in affected:
        tag = o.get("dietary_tag")
        candidates = [v for v in others
                      if tag is None or tag in
                      {normalize_tag(t) for t in (v.get("dietary_coverage") or [])}]
        if not candidates:
            plan["unmet"].append({"order": o.get("id"), "day": o.get("day"),
                                  "meal": o.get("meal"), "dietary_tag": tag,
                                  "reason": "no active vendor covers this diet tag"})
            continue
        candidates.sort(key=lambda v: ((v.get("capacity_per_day") or 0) * -1,
                                       int(v.get("rate") or 0)))
        v = candidates[0]
        plan["moves"].append({"order": o.get("id"), "day": o.get("day"),
                              "meal": o.get("meal"), "dietary_tag": tag,
                              "to_vendor": v["id"], "to_vendor_raw_id": v.get("raw_id"),
                              "note": "food safety first: certificate-compliant vendor "
                                      "required before serving"})
    return plan


def settlement(vendors: list[dict], orders: list[dict]) -> dict:
    """qty x rate per vendor; missing rate -> needs_entry (never guessed, A-13)."""
    rows = []
    for v in vendors:
        mine = [o for o in orders if o.get("vendor_id") == v["id"]]
        known = [o for o in mine if o.get("qty") is not None]
        needs_entry = [o.get("id") for o in mine if o.get("qty") is None]
        rate = v.get("rate")
        amount = None
        if rate is not None and known:
            amount = sum(int(o.get("qty") or 0) * int(rate) for o in known)
        rows.append({
            "vendor_id": v["id"], "raw_id": v.get("raw_id"), "name": v.get("name"),
            "orders": len(mine), "qty": sum(int(o.get("qty") or 0) for o in known),
            "rate": rate, "amount": amount,
            "paid": all(o.get("paid") for o in mine) if mine else False,
            "needs_manual_entry": rate is None or bool(needs_entry),
            "notes": [] if rate is not None else
                     ["rate is not in the pack (A-13): enter the negotiated rate "
                      "before settlement"] })
    total_known = sum(r["amount"] or 0 for r in rows)
    return {"rows": rows, "total_estimated": total_known,
            "pending_entries": [r["raw_id"] for r in rows if r["needs_manual_entry"]]}
