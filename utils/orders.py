"""模拟套餐工单：只落待办，不假装已开通。"""
import json
import os
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional

from .config import Config
from .plans import PLANS, _normalize_plan_name, dumps, overage_meta


def _load_orders() -> list:
    path = Config.ORDERS_FILE
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_orders(orders: list) -> None:
    path = Config.ORDERS_FILE
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)


def create_order_data(
    plan_name: str,
    user_id: str = "anonymous",
    thread_id: str = "default",
    campus_student: bool = False,
    note: str = "",
) -> dict:
    name = _normalize_plan_name(plan_name)
    if not name:
        return {
            "ok": False,
            "status": "rejected",
            "error_code": "unknown_plan",
            "activated": False,
            "message": "未识别套餐，无法生成工单。",
            "available": list(PLANS.keys()),
        }
    plan = PLANS[name]
    if plan["campus_only"] and not campus_student:
        return {
            "ok": False,
            "status": "rejected",
            "error_code": "campus_unverified",
            "activated": False,
            "plan": name,
            "message": "校园套餐需学生认证。本系统不能开通，请先在营业厅或官方 App 提交学生证。",
        }

    idempotency_key = hashlib.sha256(
        f"{user_id}:{thread_id}:{name}".encode("utf-8")
    ).hexdigest()
    orders = _load_orders()
    existing = next(
        (
            order for order in orders
            if order.get("idempotency_key") == idempotency_key
            and order.get("status") == "pending_offline"
        ),
        None,
    )
    from .bss_mock import provision as bss_provision

    if existing:
        bss = bss_provision(
            name,
            user_id=user_id,
            campus_student=campus_student,
            idempotency_key=f"bss:{idempotency_key}",
            order_id=existing["order_id"],
        )
        if bss.get("ticket_id") and existing.get("bss_ticket_id") != bss.get("ticket_id"):
            existing["bss_ticket_id"] = bss.get("ticket_id")
            existing["bss_status"] = bss.get("bss_status")
            _save_orders(orders)
        return {
            "ok": True,
            "duplicate": True,
            "status": existing["status"],
            "activated": bool(existing.get("activated")),
            "order_id": existing["order_id"],
            "plan": existing["plan"],
            "bss_ticket_id": existing.get("bss_ticket_id") or bss.get("ticket_id"),
            "bss_status": bss.get("bss_status") or existing.get("bss_status"),
            "message": "相同会话下已有该套餐的待办工单，本次未重复创建。套餐尚未开通。",
            **overage_meta(),
        }

    order = {
        "order_id": uuid.uuid4().hex[:10],
        "user_id": user_id,
        "thread_id": thread_id,
        "idempotency_key": idempotency_key,
        "plan": name,
        "monthly_fee": plan["monthly_fee"],
        "quota_gb": plan["quota_gb"],
        "status": "pending_offline",
        "activated": False,
        "note": note,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    bss = bss_provision(
        name,
        user_id=user_id,
        campus_student=campus_student,
        idempotency_key=f"bss:{idempotency_key}",
        order_id=order["order_id"],
    )
    order["bss_ticket_id"] = bss.get("ticket_id")
    order["bss_status"] = bss.get("bss_status")
    if not bss.get("ok"):
        order["bss_error_code"] = bss.get("error_code")
    orders.append(order)
    _save_orders(orders)
    activated = False
    return {
        "ok": True,
        "status": "pending_offline",
        "activated": activated,
        "order_id": order["order_id"],
        "plan": name,
        "bss_ticket_id": order.get("bss_ticket_id"),
        "bss_status": order.get("bss_status"),
        "bss_error_code": bss.get("error_code"),
        "message": (
            "已生成待办工单并提交模拟业支受理。"
            "套餐尚未开通（bss_status=provisioning）。"
            "请到营业厅或官方 App 完成实名；沙箱进度请查询业支工单。"
            "禁止理解为生产开通成功。"
        ),
        **overage_meta(),
    }


def mark_activated_by_bss_ticket(ticket_id: str) -> None:
    if not ticket_id:
        return
    orders = _load_orders()
    changed = False
    for order in orders:
        if order.get("bss_ticket_id") == ticket_id:
            order["activated"] = True
            order["bss_status"] = "success"
            order["status"] = "bss_success"
            changed = True
    if changed:
        _save_orders(orders)


def list_orders(user_id: Optional[str] = None) -> dict:
    orders = _load_orders()
    if user_id:
        orders = [o for o in orders if o.get("user_id") == user_id]
    return {"orders": orders}


def dumps_order(data: dict) -> str:
    return dumps(data)
