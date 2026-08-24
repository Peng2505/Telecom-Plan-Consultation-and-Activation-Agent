"""模拟业支：受理开通与查单。结果以本模块 JSON 为准，不是生产 BOSS。"""
import json
import os
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional

from .config import Config
from .plans import PLANS, _normalize_plan_name


def _store_path() -> str:
    return Config.BSS_STORE


def _load_tickets() -> list:
    path = _store_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_tickets(tickets: list) -> None:
    path = _store_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)


def _public(ticket: dict) -> dict:
    return {
        "ok": ticket.get("ok", True),
        "accepted": ticket.get("bss_status") in ("provisioning", "success"),
        "duplicate": bool(ticket.get("duplicate")),
        "ticket_id": ticket.get("ticket_id"),
        "plan": ticket.get("plan"),
        "user_id": ticket.get("user_id"),
        "bss_status": ticket.get("bss_status"),
        "activated": ticket.get("bss_status") == "success",
        "query_count": ticket.get("query_count", 0),
        "error_code": ticket.get("error_code"),
        "message": ticket.get("message"),
        "order_id": ticket.get("order_id"),
        "created_at": ticket.get("created_at"),
    }


def provision(
    plan_name: str,
    user_id: str = "anonymous",
    campus_student: bool = False,
    idempotency_key: Optional[str] = None,
    order_id: Optional[str] = None,
) -> dict:
    name = _normalize_plan_name(plan_name)
    if not name:
        return {
            "ok": False,
            "accepted": False,
            "bss_status": "rejected",
            "activated": False,
            "error_code": "UNKNOWN_PLAN",
            "message": "未识别套餐，模拟业支拒绝受理。",
            "available": list(PLANS.keys()),
        }
    plan = PLANS[name]
    if plan["campus_only"] and not campus_student:
        return {
            "ok": False,
            "accepted": False,
            "bss_status": "rejected",
            "activated": False,
            "error_code": "CAMPUS_UNVERIFIED",
            "plan": name,
            "message": "校园套餐未完成学生认证，模拟业支拒绝开通。",
        }

    key = idempotency_key or hashlib.sha256(
        f"bss:{user_id}:{name}".encode("utf-8")
    ).hexdigest()
    tickets = _load_tickets()
    existing = next((t for t in tickets if t.get("idempotency_key") == key), None)
    if existing:
        existing["duplicate"] = True
        if order_id and not existing.get("order_id"):
            existing["order_id"] = order_id
        _save_tickets(tickets)
        existing = dict(existing)
        existing["message"] = (
            "模拟业支已有相同幂等开通单，未重复受理。当前尚未以 success 回执为准开通。"
            if existing.get("bss_status") != "success"
            else "模拟业支查到该套餐已有成功回执，未重复受理。"
        )
        return _public(existing)

    ticket = {
        "ok": True,
        "ticket_id": uuid.uuid4().hex[:12],
        "user_id": user_id,
        "plan": name,
        "order_id": order_id,
        "idempotency_key": key,
        "bss_status": "provisioning",
        "query_count": 0,
        "error_code": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "message": "模拟业支已受理，状态 provisioning，套餐尚未开通。请使用 query_ticket 查询回执。",
    }
    tickets.append(ticket)
    _save_tickets(tickets)
    return _public(ticket)


def query_ticket(ticket_id: str = "", user_id: Optional[str] = None) -> dict:
    tickets = _load_tickets()
    ticket = None
    tid = (ticket_id or "").strip()
    if tid:
        ticket = next((t for t in tickets if t.get("ticket_id") == tid), None)
    elif user_id:
        owned = [t for t in tickets if t.get("user_id") == user_id]
        ticket = owned[-1] if owned else None
    if not ticket:
        return {
            "ok": False,
            "bss_status": "rejected",
            "activated": False,
            "error_code": "TICKET_NOT_FOUND",
            "message": "未找到模拟业支工单。请先确认办理生成待办并受理。",
        }

    if ticket.get("bss_status") == "rejected":
        return _public(ticket)

    ticket["query_count"] = int(ticket.get("query_count") or 0) + 1
    if ticket["query_count"] >= 2 and ticket.get("bss_status") != "success":
        ticket["bss_status"] = "success"
        ticket["message"] = "模拟业支回执 success。仅表示沙箱开通成功，不是生产运营商开通。"
        from .orders import mark_activated_by_bss_ticket

        mark_activated_by_bss_ticket(ticket["ticket_id"])
    elif ticket.get("bss_status") == "success":
        ticket["message"] = "模拟业支回执 success。仅表示沙箱开通成功，不是生产运营商开通。"
    else:
        ticket["bss_status"] = "provisioning"
        ticket["message"] = "模拟业支处理中（provisioning），套餐尚未开通。再次查询才可能变为 success。"
    _save_tickets(tickets)
    return _public(ticket)
