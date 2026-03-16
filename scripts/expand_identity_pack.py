from __future__ import annotations

import argparse
import json
from pathlib import Path


ORDERED_STEPS = [
    "half_body_reference",
    "full_body_reference",
    "expressions_pack",
    "angles_pack",
    "walking_pose_reference",
    "seated_pose_reference",
    "lighting_neutral_reference",
    "style_neutral_reference",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Expand identity pack references (semi-automatic)")
    parser.add_argument("--identity-root", default="data/character_identity")
    args = parser.parse_args()

    root = Path(args.identity_root)
    manifest_path = root / "character_identity_profile.json"
    if not manifest_path.exists():
        raise SystemExit("Manifest not found. Run bootstrap_identity_pack.py first")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    refs = payload.setdefault("reference_pack", {})

    check_list = []
    for step in ORDERED_STEPS:
        status = "ready" if refs.get(step) else "manual_required"
        check_list.append({"reference": step, "status": status, "path": refs.get(step, "")})

    payload["expansion_workflow"] = {
        "status": "in_progress" if any(row["status"] == "manual_required" for row in check_list) else "complete",
        "steps": check_list,
        "manual_notes": "User should validate pose/body consistency and reject artifacts before marking ready.",
    }

    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated expansion workflow: {manifest_path}")


if __name__ == "__main__":
    main()
