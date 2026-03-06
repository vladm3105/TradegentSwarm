"""Tests for ADK contract version compatibility helpers."""

import pytest

from adk_runtime.versioning import (
    ensure_compatible_contract_version,
    is_compatible_contract_version,
    parse_semver,
)


def test_parse_semver_accepts_strict_semver() -> None:
    assert parse_semver("2.6.1") == (2, 6, 1)


def test_parse_semver_rejects_non_semver() -> None:
    with pytest.raises(ValueError, match="Invalid contract_version"):
        parse_semver("v2")


def test_contract_compatibility_allows_n_and_n_minus_1() -> None:
    assert is_compatible_contract_version("2.1.0", "2.9.9") is True
    assert is_compatible_contract_version("1.5.0", "2.0.0") is True
    assert is_compatible_contract_version("0.9.0", "2.0.0") is False


def test_ensure_contract_compatibility_raises_for_unsupported_major() -> None:
    with pytest.raises(RuntimeError, match="UNSUPPORTED_CONTRACT_VERSION"):
        ensure_compatible_contract_version("4.0.0", "2.3.1")
