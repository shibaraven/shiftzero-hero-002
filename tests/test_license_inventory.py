import json
from pathlib import Path

from shiftzero.license_inventory import build_license_inventory

ROOT = Path(__file__).resolve().parents[1]


def test_license_inventory_covers_every_resolved_package(tmp_path: Path) -> None:
    report = build_license_inventory(
        root=ROOT,
        output_path=tmp_path / "THIRD_PARTY_LICENSES.json",
        notices_path=tmp_path / "THIRD_PARTY_NOTICES.md",
        requirements_lock_path=tmp_path / "requirements.lock",
    )
    assert report["summary"]["python_packages"] >= 20
    assert report["summary"]["npm_packages"] >= 100
    assert report["summary"]["total_packages"] == len(report["packages"])
    assert report["summary"]["missing_version"] == 0
    assert report["summary"]["missing_license"] == 0
    assert report["summary"]["missing_source"] == 0
    assert all(row["version"] and row["license"] and row["source"] for row in report["packages"])


def test_checked_in_inventory_matches_current_locks() -> None:
    inventory = json.loads((ROOT / "THIRD_PARTY_LICENSES.json").read_text(encoding="utf-8"))
    npm_lock = json.loads((ROOT / "apps/web/package-lock.json").read_text(encoding="utf-8"))
    assert inventory["summary"]["npm_packages"] == len(npm_lock["packages"]) - 1
    assert inventory["summary"]["total_packages"] == len(inventory["packages"])
    assert inventory["summary"]["missing_version"] == 0
    assert inventory["summary"]["missing_license"] == 0
    assert inventory["summary"]["missing_source"] == 0
