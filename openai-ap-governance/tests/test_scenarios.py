import re
from apdemo.scenarios import SCENARIOS, prompt_for, LONG_PROMPT


def test_every_version_has_happy_and_governed():
    for v in range(0, 12):
        assert "happy" in SCENARIOS[v] and "governed" in SCENARIOS[v]


def test_v2_governed_triggers_banned_word():
    assert re.search(r"(?i)voldemort|enron", SCENARIOS[2]["governed"])


def test_v3_governed_drives_repeated_reminders():
    assert SCENARIOS[3]["governed"].lower().count("reminder") >= 1


def test_v9_governed_exports_restricted_asset():
    assert "vendor_bank_accounts" in prompt_for(9, "governed").lower()


def test_v10_governed_contains_injection_attempt():
    assert "ignore all previous instructions" in prompt_for(10, "governed").lower()


def test_v11_governed_contains_pii():
    assert "ssn" in prompt_for(11, "governed").lower()


def test_long_prompt_present():
    assert "month-end" in LONG_PROMPT.lower()


def test_prompt_for_long_mode():
    assert prompt_for(6, "long") == LONG_PROMPT
