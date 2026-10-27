"""The mutation score gate used by `make mutation` and CI."""
import json

import pytest

from qualitylens import mutation as mutation_score

pytestmark = pytest.mark.unit

STATS = {"killed": 90, "survived": 6, "no_tests": 2, "timeout": 2, "total": 100,
         "skipped": 0, "suspicious": 0, "segfault": 0, "check_was_interrupted_by_user": 0}


def test_score_counts_every_unkilled_mutant_against_the_suite():
    assert mutation_score.score(STATS) == 90.0
    assert mutation_score.score({**STATS, "survived": 0, "no_tests": 0, "timeout": 0}) == 100.0
    assert mutation_score.score({"killed": 0, "survived": 0, "no_tests": 0, "timeout": 0}) == 0.0


def test_report():
    assert mutation_score.report(STATS, 85).splitlines()[:5] == [
        "## Mutation testing: ✅ 90.0 % (minimum 85 %)", "",
        "| Mutants | Killed | Survived | No tests | Timeout |", "|---:|---:|---:|---:|---:|",
        "| 100 | 90 | 6 | 2 | 2 |"]
    assert mutation_score.report(STATS, 90.5).startswith("## Mutation testing: ❌ 90.0 % (minimum 90 %)")


@pytest.mark.parametrize("minimum, code", [(90, 0), (90.1, 1)])
def test_gate(tmp_path, capsys, minimum, code):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps(STATS))
    assert mutation_score.main([str(path), "--min", str(minimum)]) == code
    assert "Mutation testing" in capsys.readouterr().out


def test_default_minimum_is_90(tmp_path, capsys):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps({**STATS, "killed": 89, "total": 99}))
    assert mutation_score.main([str(path)]) == 1
    assert "(minimum 90 %)" in capsys.readouterr().out
