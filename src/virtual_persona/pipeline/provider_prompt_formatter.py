from __future__ import annotations

from typing import Dict


class ReferenceAwarePromptFormatter:
    def format_for_provider(self, package: Dict[str, str], provider: str) -> str:
        provider_key = (provider or "").lower()
        base = package.get("final_prompt", "")
        negative = package.get("negative_prompt", "")
        refs = package.get("reference_bundle", "")

        if provider_key in {"ideogram", "flux"}:
            return f"{base}\n\nReferences: {refs}\nNegative: {negative}".strip()
        if provider_key in {"midjourney", "mj"}:
            return f"{base} --no {negative}".strip()
        if provider_key in {"image_to_video", "i2v", "runway"}:
            motion = package.get("video_motion", "natural small body motion")
            camera_motion = package.get("video_camera_motion", "light handheld")
            return f"{base}\nMotion: {motion}\nCamera motion: {camera_motion}\nNegative: {negative}".strip()
        return base
