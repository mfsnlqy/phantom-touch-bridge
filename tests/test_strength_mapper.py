from __future__ import annotations

import pytest

from intiface_bridge.errors import BridgeError, ErrorCode
from intiface_bridge.mappers.strength import (
    is_stop_strength,
    map_to_continuous_strength,
    map_to_discrete_level,
    validate_strength,
)


def test_validate_strength_accepts_integer_range_and_detects_stop():
    assert validate_strength(0) == 0
    assert validate_strength(100) == 100
    assert is_stop_strength(0) is True
    assert is_stop_strength(1) is False


def test_validate_strength_rejects_bool_and_out_of_range_values():
    with pytest.raises(BridgeError) as bool_error:
        validate_strength(True)

    assert bool_error.value.code == ErrorCode.INVALID_STRENGTH

    with pytest.raises(BridgeError) as range_error:
        validate_strength(101)

    assert range_error.value.code == ErrorCode.INVALID_STRENGTH
    assert range_error.value.details == {"value": 101}


def test_map_to_continuous_strength_uses_shared_zero_to_one_scale():
    assert map_to_continuous_strength(0) == 0.0
    assert map_to_continuous_strength(25) == 0.25
    assert map_to_continuous_strength(100) == 1.0


def test_map_to_discrete_level_supports_stop_and_quantized_mapping():
    assert map_to_discrete_level(0, 5) == 0
    assert map_to_discrete_level(1, 5) == 1
    assert map_to_discrete_level(50, 5) == 3
    assert map_to_discrete_level(100, 5) == 5


def test_map_to_discrete_level_rejects_invalid_level_counts():
    with pytest.raises(BridgeError) as bool_error:
        map_to_discrete_level(50, True)

    assert bool_error.value.code == ErrorCode.INVALID_STRENGTH
    assert bool_error.value.details == {"levels": True}

    with pytest.raises(BridgeError) as zero_error:
        map_to_discrete_level(50, 0)

    assert zero_error.value.code == ErrorCode.INVALID_STRENGTH
    assert zero_error.value.details == {"levels": 0}
