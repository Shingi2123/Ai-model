from __future__ import annotations

from pathlib import Path


def clean_image_export(source_path: str, target_path: str) -> str:
    """Create clean export without metadata; fallback to byte copy when Pillow unavailable."""
    src = Path(source_path)
    dst = Path(target_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image

        with Image.open(src) as img:
            image = img.convert("RGB") if img.mode not in {"RGB", "L"} else img.copy()
            image.save(dst, format="JPEG", quality=95, optimize=True)
    except Exception:
        dst.write_bytes(src.read_bytes())
    return str(dst)
