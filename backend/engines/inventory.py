"""Inventory + merch engine — pure functions, dicts in / out.

Stock is derived from the movement ledger (never a stored total):
  stock = SUM(initial/arrivals) - SUM(outflows) mapped per movement direction.

Merch issuing is once per participant per item (canonical dup clusters included).
"""
from __future__ import annotations


def stock_levels(items: list[dict], movements: list[dict]) -> dict[int, int]:
    """item_id -> derived available quantity from the ledger.

    Movement semantics (importer convention):
      qty > 0  -> stock IN  (to_location e.g. 'store'/'venue')
      qty < 0  -> stock OUT (issued/reserved/lost)
      damaged/awaiting_return entries count as out of circulation
    """
    items_by_id = {i["id"]: i for i in items}
    levels: dict[int, int] = {i["id"]: 0 for i in items}
    for m in sorted(movements, key=lambda x: (x.get("at") or "", x.get("id") or 0)):
        item_id = m.get("item_id")
        if item_id not in items_by_id:
            continue
        qty = int(m.get("qty") or 0)
        status = (m.get("status") or "available").lower()
        # status which removes from circulation other than an explicit damage note
        if status == "damaged" and qty > 0:
            qty = 0            # a damaged repair entry never adds stock
        levels[item_id] = levels.get(item_id, 0) + qty
    return levels


def merch_demand(participants: list[dict], canonical_of: dict[int, int] | None = None
                 ) -> dict[str, int]:
    """size -> count of active participants wanting merch (canonical collapsed)."""
    canonical_of = canonical_of or {}
    demand: dict[str, int] = {}
    for p in participants:
        if p.get("merged_into"):
            continue
        if str(p.get("accommodation_requested") or "").strip().lower() not in ("yes", "no"):
            # nobody is excluded from merch by accommodation; keep everyone active
            pass
        if p.get("status") not in ("active", "flagged"):
            continue
        size = (p.get("tshirt_size") or "").strip() or "UNKNOWN"
        demand[size] = demand.get(size, 0) + 1
    return demand


def merch_shortfall(items: list[dict], movements: list[dict],
                    participants: list[dict], issued_pairs: set[tuple[int, int]] | None = None
                    ) -> dict:
    """T-shirt demand vs derived stock; flags sizes short of demand."""
    sizes_items = [i for i in items if (i.get("kind") or "") == "merch"]
    stock = {}
    for it in sizes_items:
        key = it.get("size") or "UNKNOWN"
        stock[key] = stock.get(key, 0) + 1     # each merch row = one physical unit
    # issued pairs guard: already-issued (canonical participant, size) removed from need
    issued_pairs = issued_pairs or set()
    demand = merch_demand(participants)
    need = {}
    for p in participants:
        if p.get("merged_into") or p.get("status") not in ("active", "flagged"):
            continue
        size = (p.get("tshirt_size") or "").strip() or "UNKNOWN"
        if (p["id"], size) in issued_pairs:
            continue
        need[size] = need.get(size, 0) + 1
    shortfall = {}
    for size, n in sorted(need.items()):
        have = stock.get(size, 0)
        if n > have:
            shortfall[size] = {"needed": n, "stock": have, "missing": n - have}
    return {"demand": demand, "stock": stock, "shortfall": shortfall,
            "issued_guard": len(issued_pairs)}


def can_issue_participant(existing_for_canonical: set[str], item_name: str
                          ) -> tuple[bool, str]:
    """Issue-once rule: a participant (canonical cluster) receives a given item once."""
    if item_name in existing_for_canonical:
        return False, f"already issued {item_name} to this participant's cluster"
    return True, ""
