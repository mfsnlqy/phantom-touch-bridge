from __future__ import annotations

from types import SimpleNamespace

import pytest

from intiface_bridge.errors import BridgeError, ErrorCode
from intiface_bridge.utils.matching import find_name_matches, normalize_name, require_single_name_match


def test_normalize_name_and_find_matches_are_case_insensitive():
    items = [
        SimpleNamespace(name="Demo Device"),
        SimpleNamespace(name="Other Device"),
        SimpleNamespace(name="demo mini"),
    ]

    assert normalize_name("  DeMo  ") == "demo"
    matches = find_name_matches(items, "DeMo", lambda item: item.name)

    assert [item.name for item in matches] == ["Demo Device", "demo mini"]


def test_require_single_name_match_returns_single_match():
    items = [
        SimpleNamespace(name="Demo Device"),
        SimpleNamespace(name="Other Device"),
    ]

    matched = require_single_name_match(items, "demo", lambda item: item.name, backend="custom")

    assert matched.name == "Demo Device"


def test_require_single_name_match_raises_device_not_found_for_blank_or_missing_query():
    items = [SimpleNamespace(name="Demo Device")]

    with pytest.raises(BridgeError) as blank_error:
        require_single_name_match(items, "   ", lambda item: item.name, backend="custom")

    assert blank_error.value.code == ErrorCode.DEVICE_NOT_FOUND
    assert blank_error.value.backend == "custom"

    with pytest.raises(BridgeError) as missing_error:
        require_single_name_match(items, "missing", lambda item: item.name, backend="custom")

    assert missing_error.value.code == ErrorCode.DEVICE_NOT_FOUND
    assert missing_error.value.details == {
        "query": "missing",
        "candidates": ["Demo Device"],
    }


def test_require_single_name_match_raises_when_multiple_candidates_match():
    items = [
        SimpleNamespace(name="Demo Device"),
        SimpleNamespace(name="Demo Mini"),
    ]

    with pytest.raises(BridgeError) as error:
        require_single_name_match(items, "demo", lambda item: item.name, backend="custom")

    assert error.value.code == ErrorCode.MULTIPLE_DEVICES_MATCHED
    assert error.value.details == {
        "query": "demo",
        "matched_candidates": ["Demo Device", "Demo Mini"],
    }
