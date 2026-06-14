from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

from intiface_bridge.errors import BridgeError, ErrorCode

T = TypeVar("T")


def normalize_name(value: str) -> str:
    return value.strip().casefold()


def find_name_matches(
    items: Sequence[T],
    query: str,
    name_getter: Callable[[T], str],
) -> list[T]:
    normalized_query = normalize_name(query)
    if not normalized_query:
        return []

    return [
        item
        for item in items
        if normalized_query in normalize_name(name_getter(item))
    ]


def require_single_name_match(
    items: Sequence[T],
    query: str,
    name_getter: Callable[[T], str],
    *,
    backend: str | None = None,
) -> T:
    normalized_query = normalize_name(query)
    if not normalized_query:
        raise BridgeError(
            ErrorCode.DEVICE_NOT_FOUND,
            "设备名称不能为空。",
            backend=backend,
        )

    matches = find_name_matches(items, query, name_getter)
    candidate_names = [name_getter(item) for item in items]

    if not matches:
        raise BridgeError(
            ErrorCode.DEVICE_NOT_FOUND,
            f'未找到名称包含 "{query}" 的设备。',
            backend=backend,
            details={"query": query, "candidates": candidate_names},
        )

    if len(matches) > 1:
        raise BridgeError(
            ErrorCode.MULTIPLE_DEVICES_MATCHED,
            f'找到多个名称包含 "{query}" 的设备，请缩小名称范围。',
            backend=backend,
            details={
                "query": query,
                "matched_candidates": [name_getter(item) for item in matches],
            },
        )

    return matches[0]
