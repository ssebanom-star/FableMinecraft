"""
furnace.py - 화로 제련 시스템.

화로 상태는 world.containers 의 dict 로 관리된다:
  {"type": "furnace", "input": stack, "fuel": stack, "output": stack,
   "burn_time": float, "burn_total": float, "progress": float}

- 연료의 fuel_time 만큼 연소하며, SMELT_TIME 마다 재료 1개를 제련한다.
- 결과 슬롯이 가득 차거나 다른 아이템이면 제련이 멈춘다.
"""

import items as I

SMELT_TIME = 5.0   # 아이템 1개 제련 시간 (초)


def get_smelt_result(stack):
    """재료 스택의 제련 결과 (item_id, count) 또는 None."""
    if not stack:
        return None
    item = I.get_item(stack["id"])
    if item is None or item.smelt_result is None:
        return None
    return item.smelt_result


def can_smelt(state):
    """현재 재료를 제련해 결과 슬롯에 넣을 수 있는지."""
    result = get_smelt_result(state.get("input"))
    if result is None:
        return False
    out = state.get("output")
    if out is None:
        return True
    rid, rcount = result
    if out["id"] != rid:
        return False
    item = I.get_item(rid)
    return out["count"] + rcount <= (item.stack_size if item else 64)


def is_fuel(stack):
    if not stack:
        return False
    item = I.get_item(stack["id"])
    return item is not None and item.fuel_time > 0


def start_burning(state):
    """연료 1개를 소모해 연소를 시작한다. 성공 여부 반환."""
    fuel = state.get("fuel")
    if not is_fuel(fuel):
        return False
    item = I.get_item(fuel["id"])
    state["burn_time"] = float(item.fuel_time)
    state["burn_total"] = float(item.fuel_time)
    fuel["count"] -= 1
    if fuel["count"] <= 0:
        state["fuel"] = None
    return True


def finish_smelt(state):
    """재료 1개를 결과로 변환한다."""
    result = get_smelt_result(state.get("input"))
    if result is None:
        return
    rid, rcount = result
    inp = state["input"]
    inp["count"] -= 1
    if inp["count"] <= 0:
        state["input"] = None
    out = state.get("output")
    if out is None:
        state["output"] = I.make_stack(rid, rcount)
    else:
        out["count"] += rcount
    state["progress"] = 0.0


def update_furnace(state, dt):
    """
    화로 갱신. 반환: 상태 변화 여부 (UI 갱신용).
    """
    changed = False
    burning = state.get("burn_time", 0.0) > 0.0

    if burning:
        state["burn_time"] = max(0.0, state["burn_time"] - dt)
        changed = True

    if can_smelt(state):
        # 불이 꺼져 있으면 연료 소모 시도
        if state.get("burn_time", 0.0) <= 0.0:
            if start_burning(state):
                changed = True
            else:
                if state.get("progress", 0.0) > 0.0:
                    state["progress"] = 0.0
                    changed = True
                return changed
        state["progress"] = state.get("progress", 0.0) + dt
        changed = True
        if state["progress"] >= SMELT_TIME:
            finish_smelt(state)
    else:
        if state.get("progress", 0.0) > 0.0:
            state["progress"] = 0.0
            changed = True
    return changed


def is_burning(state):
    return state.get("burn_time", 0.0) > 0.0


def burn_ratio(state):
    total = state.get("burn_total", 0.0)
    if total <= 0:
        return 0.0
    return state.get("burn_time", 0.0) / total


def progress_ratio(state):
    return min(1.0, state.get("progress", 0.0) / SMELT_TIME)
