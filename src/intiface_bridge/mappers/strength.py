from __future__ import annotations

from math import ceil

from intiface_bridge.errors import BridgeError, ErrorCode


def validate_strength(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BridgeError(
            ErrorCode.INVALID_STRENGTH,
            "强度必须是 0 到 100 之间的整数。",
        )

    if value < 0 or value > 100:
        raise BridgeError(
            ErrorCode.INVALID_STRENGTH,
            "强度必须在 0 到 100 之间。",
            details={"value": value},
        )

    return value


def is_stop_strength(value: int) -> bool:
    return validate_strength(value) == 0


def map_to_continuous_strength(value: int) -> float:
    normalized = validate_strength(value)
    return round(normalized / 100, 4)


def map_to_discrete_level(value: int, levels: int) -> int:
    normalized = validate_strength(value)

    if isinstance(levels, bool) or not isinstance(levels, int):
        raise BridgeError(
            ErrorCode.INVALID_STRENGTH,
            "离散档位数量必须是正整数。",
            details={"levels": levels},
        )

    if levels <= 0:
        raise BridgeError(
            ErrorCode.INVALID_STRENGTH,
            "离散档位数量必须大于 0。",
            details={"levels": levels},
        )

    if normalized == 0:
        return 0

    return min(levels, ceil((normalized / 100) * levels))
