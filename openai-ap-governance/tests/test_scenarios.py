from apdemo.scenarios import prompt_for


def test_every_version_has_both_modes():
    for n in range(0, 7):
        assert prompt_for(n, "happy")
        assert prompt_for(n, "governed")
