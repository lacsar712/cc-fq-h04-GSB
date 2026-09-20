"""BUG: reverse stage_order on create and on read."""
from __future__ import annotations

REVERSE_ON_CREATE = True
REVERSE_ON_READ = True


def create_order_index(chain_len: int, logical_index: int) -> int:
    if REVERSE_ON_CREATE:
        return chain_len - 1 - logical_index
    return logical_index


def order_stages(stages: list) -> list:
    items = list(stages)
    if REVERSE_ON_READ:
        return sorted(items, key=lambda s: getattr(s, "stage_order", 0), reverse=True)
    return sorted(items, key=lambda s: getattr(s, "stage_order", 0))
