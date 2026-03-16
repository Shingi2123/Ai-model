from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from virtual_persona.pipeline.identity import CharacterIdentityManager, default_identity_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap character identity pack (semi-automatic workflow)")
    parser.add_argument("--input-dir", required=True, help="Directory with 3-8 source photos selected by user")
    parser.add_argument("--identity-root", default="data/character_identity", help="Identity pack root")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    photos = [p for p in sorted(input_dir.glob("*")) if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    if len(photos) < 3:
        raise SystemExit("Need at least 3 source photos for bootstrap workflow")

    mgr = CharacterIdentityManager(args.identity_root)
    mgr.ensure_structure()
    manifest = default_identity_manifest()
    manifest["bootstrap"] = {
        "input_photo_count": len(photos),
        "input_photos": [str(p) for p in photos],
        "status": "manual_selection_required",
        "next_steps": [
            "Generate 10-20 synthetic candidates manually or via your generator.",
            "Select best candidate as face_reference and update manifest.reference_pack.face_reference.",
            "Run scripts/expand_identity_pack.py to collect half-body/full-body/expression references.",
        ],
    }
    manifest_path = Path(args.identity_root) / "character_identity_profile.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Identity manifest bootstrapped at {manifest_path}")


if __name__ == "__main__":
    main()
