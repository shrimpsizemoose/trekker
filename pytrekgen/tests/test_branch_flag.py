"""Tests for branch_flag check type."""

import pytest
from pydantic import ValidationError

from pytrekgen.config import (
    BranchFlagCheck,
    Flag,
    WaitCheck,
)
from pytrekgen.generator import Generator
from conftest import minimal_config


# ---------------------------------------------------------------------------
# Config model tests
# ---------------------------------------------------------------------------


def test_branch_flag_basic_model():
    check = BranchFlagCheck(flag="small", if_set="a", if_not_set="b")
    assert check.type == "branch_flag"
    assert check.flag == "small"
    assert check.if_set == "a"
    assert check.if_not_set == "b"


def test_branch_flag_next_alias():
    data = {"flag": "x", "_next": "final"}
    check = BranchFlagCheck.model_validate(data)
    assert check.next == "final"


def test_branch_only_alias_on_base_check():
    data = {
        "type": "wait",
        "seconds": 1,
        "_branch_only": True,
    }
    check = WaitCheck.model_validate(data)
    assert check.branch_only is True


def test_branch_only_defaults_false():
    check = WaitCheck(seconds=1)
    assert check.branch_only is False


def _branch_config(**overrides):
    """Helper to build a config with branch_flag + branch targets."""
    defaults = dict(
        flags=[Flag(name="small")],
        checks=[
            {
                "type": "branch_flag",
                "name": "check_mode",
                "flag": "small",
                "if_set": "verify_small",
                "if_not_set": "verify_full",
            },
            {
                "type": "wait",
                "name": "verify_small",
                "seconds": 1,
                "_branch_only": True,
            },
            {
                "type": "wait",
                "name": "verify_full",
                "seconds": 5,
                "_branch_only": True,
            },
        ],
    )
    defaults.update(overrides)
    return minimal_config(**defaults)


def test_valid_branch_config():
    config = _branch_config()
    assert config.checks[0].type == "branch_flag"


def test_get_check_by_name():
    config = _branch_config()
    found = config.get_check_by_name("verify_small")
    assert found.type == "wait"
    assert found.name == "verify_small"


def test_get_check_by_name_not_found():
    config = _branch_config()
    with pytest.raises(ValueError, match="not found"):
        config.get_check_by_name("nonexistent")


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_validation_flag_not_in_flags_list():
    with pytest.raises(ValidationError, match="flag 'missing'.*not found"):
        minimal_config(
            flags=[Flag(name="other")],
            checks=[
                {
                    "type": "branch_flag",
                    "name": "b",
                    "flag": "missing",
                    "if_set": "t",
                    "if_not_set": "",
                },
                {"type": "wait", "name": "t", "seconds": 1, "_branch_only": True},
            ],
        )


def test_validation_if_set_references_unknown_check():
    with pytest.raises(ValidationError, match="unknown check 'ghost'"):
        minimal_config(
            flags=[Flag(name="x")],
            checks=[
                {
                    "type": "branch_flag",
                    "name": "b",
                    "flag": "x",
                    "if_set": "ghost",
                },
            ],
        )


def test_validation_target_must_have_branch_only():
    with pytest.raises(ValidationError, match="must have _branch_only"):
        minimal_config(
            flags=[Flag(name="x")],
            checks=[
                {
                    "type": "branch_flag",
                    "name": "b",
                    "flag": "x",
                    "if_set": "t",
                },
                {"type": "wait", "name": "t", "seconds": 1},
            ],
        )


def test_validation_target_cannot_be_branch_flag():
    with pytest.raises(ValidationError, match="cannot be another branch_flag"):
        minimal_config(
            flags=[Flag(name="x"), Flag(name="y")],
            checks=[
                {
                    "type": "branch_flag",
                    "name": "b1",
                    "flag": "x",
                    "if_set": "b2",
                },
                {
                    "type": "branch_flag",
                    "name": "b2",
                    "flag": "y",
                    "_branch_only": True,
                },
            ],
        )


def test_validation_empty_if_set_is_ok():
    """Empty if_set/if_not_set means 'do nothing' — should pass validation."""
    config = minimal_config(
        flags=[Flag(name="x")],
        checks=[
            {
                "type": "branch_flag",
                "name": "b",
                "flag": "x",
                "if_set": "",
                "if_not_set": "t",
            },
            {"type": "wait", "name": "t", "seconds": 1, "_branch_only": True},
        ],
    )
    assert config.checks[0].if_set == ""


# ---------------------------------------------------------------------------
# Code generation tests
# ---------------------------------------------------------------------------


def test_branch_flag_generates_if_else():
    gen = Generator()
    config = _branch_config()
    code = gen.generate(config)
    assert "if *flagSmall {" in code
    assert "} else {" in code


def test_branch_only_checks_skipped_in_main_loop():
    gen = Generator()
    config = _branch_config()
    code = gen.generate(config)
    # The wait checks should appear inside the if/else, not standalone
    # Count occurrences of time.Sleep — should be exactly 2 (inside branches)
    assert code.count("time.Sleep") == 2


def test_branch_targets_inline_correct_code():
    gen = Generator()
    config = _branch_config()
    code = gen.generate(config)
    assert "time.Sleep(1 * time.Second)" in code
    assert "time.Sleep(5 * time.Second)" in code


def test_branch_with_empty_if_set():
    gen = Generator()
    config = minimal_config(
        flags=[Flag(name="x")],
        checks=[
            {
                "type": "branch_flag",
                "name": "b",
                "flag": "x",
                "if_set": "",
                "if_not_set": "t",
            },
            {"type": "wait", "name": "t", "seconds": 3, "_branch_only": True},
        ],
    )
    code = gen.generate(config)
    assert "if *flagX {" in code
    assert "time.Sleep(3 * time.Second)" in code


# ---------------------------------------------------------------------------
# --checks output tests
# ---------------------------------------------------------------------------


def test_checks_output_shows_branch_flag():
    gen = Generator()
    config = _branch_config()
    code = gen.generate(config)
    assert "branch_flag" in code
    assert "verify_small" in code
    assert "verify_full" in code


def test_checks_output_skips_branch_only():
    gen = Generator()
    config = _branch_config()
    code = gen.generate(config)
    # branch_only checks should not appear as separate numbered items
    # in the --checks output section
    checks_section = code.split("flagChecks")[1].split("return")[0]
    # verify_small and verify_full appear only as branch targets, not as
    # standalone numbered items
    assert "[wait] verify_small" not in checks_section
    assert "[wait] verify_full" not in checks_section


# ---------------------------------------------------------------------------
# Visualization tests
# ---------------------------------------------------------------------------


def test_check_detail_branch_flag():
    check = BranchFlagCheck(flag="small", if_set="a", if_not_set="b")
    detail = Generator._check_detail(check)
    assert "-small" in detail
    assert "a" in detail
    assert "b" in detail


def test_ascii_skips_branch_only_checks():
    gen = Generator()
    config = _branch_config()
    ascii_out = gen.generate_flow(config, fmt="ascii")
    # branch_only checks should not appear as separate panels
    assert "verify_small" not in ascii_out or "branch_flag" in ascii_out


def test_ascii_shows_branch_flag_panel():
    gen = Generator()
    config = _branch_config()
    ascii_out = gen.generate_flow(config, fmt="ascii")
    assert "check_mode" in ascii_out
    assert "branch_flag" in ascii_out


def test_mermaid_renders_diamond_for_branch():
    gen = Generator()
    config = _branch_config()
    mermaid = gen.generate_mermaid(config)
    assert "-small?" in mermaid
    assert "yes" in mermaid
    assert "no" in mermaid
    assert "verify_small" in mermaid
    assert "verify_full" in mermaid


def test_mermaid_skips_branch_only_as_top_level():
    gen = Generator()
    config = _branch_config()
    mermaid = gen.generate_mermaid(config)
    # branch_only checks should not appear as top-level numbered nodes (C2, C3)
    # but should appear inside branch target nodes (C1_yes, C1_no)
    assert "C2[" not in mermaid  # no top-level node for branch_only checks
    assert "C1_yes" in mermaid   # branch target nodes exist
    assert "C1_no" in mermaid
    # branch targets should show their type label
    assert "[wait]" in mermaid
