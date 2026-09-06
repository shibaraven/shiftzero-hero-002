from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_video_plan_matches_competition_timing_constraints() -> None:
    shotlist = (ROOT / "docs/VIDEO_SHOTLIST.md").read_text(encoding="utf-8")
    assert "Encoded target: 2:58" in shotlist
    assert "0:00-0:15" in shotlist
    assert "0:15-0:35" in shotlist
    assert "Continuous key-module simulation segment: 65 seconds" in shotlist
    assert "0:58-2:03" in shotlist
    assert "DIGITAL TWIN / SIMULATION" in shotlist
    assert "no-hardware" in shotlist


def test_devpost_has_explicit_existing_work_section() -> None:
    devpost = (ROOT / "docs/DEVPOST_DRAFT.md").read_text(encoding="utf-8")
    assert "## Existing work" in devpost
    assert "2026-08-26" in devpost
    assert "PRE_EXISTING_WORK.md" in devpost
