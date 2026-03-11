from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any, Dict, List

from virtual_persona.models.domain import DailyPackage, DayScene, PublishingPlanItem


DEFAULT_POSTING_RULES = [
    {
        "rule_id": "default-photo-morning",
        "platform": "Instagram",
        "content_type": "photo",
        "preferred_time": "09:30",
        "enabled": "true",
        "priority": "10",
        "min_per_day": "1",
        "max_per_day": "1",
        "day_type_filter": "",
        "narrative_phase_filter": "",
        "city_filter": "",
        "weekday_filter": "",
        "notes": "Guaranteed daily visual post",
    },
    {
        "rule_id": "default-video-evening",
        "platform": "Instagram",
        "content_type": "video",
        "preferred_time": "18:30",
        "enabled": "true",
        "priority": "5",
        "min_per_day": "0",
        "max_per_day": "1",
        "day_type_filter": "work_day,travel_day",
        "narrative_phase_filter": "",
        "city_filter": "",
        "weekday_filter": "",
        "notes": "Optional evening motion content",
    },
]


class PublishingPlanEngine:
    def __init__(self, state_store) -> None:
        self.state = state_store

    def generate(self, package: DailyPackage) -> List[PublishingPlanItem]:
        rules = self._load_rules()
        matched_rules = [r for r in rules if self._rule_matches_package(r, package)]
        if not matched_rules:
            matched_rules = [r for r in DEFAULT_POSTING_RULES if self._rule_matches_package(r, package)]

        matched_rules.sort(key=lambda row: int(self._as_int(row.get("priority"), 0)), reverse=True)

        items: List[PublishingPlanItem] = []
        used_signatures: set[str] = set()
        publish_windows = package.content.publish_windows or ["09:30"]

        for idx, rule in enumerate(matched_rules):
            min_per_day = max(0, self._as_int(rule.get("min_per_day"), 0))
            max_per_day = max(1, self._as_int(rule.get("max_per_day"), 1))
            count = max(min_per_day, 1 if idx == 0 else 0)
            count = min(count, max_per_day)
            for _ in range(count):
                scene = self._pick_scene(package.scenes, used_signatures)
                if not scene:
                    continue
                used_signatures.add(scene.moment_signature or scene.scene_moment or scene.description)
                content_type = str(rule.get("content_type") or "photo").strip().lower()
                prompt_text = self._pick_prompt_text(package, scene, content_type)
                caption = package.content.post_caption
                preferred_time = str(rule.get("preferred_time") or "").strip()
                post_time = preferred_time or publish_windows[min(len(items), len(publish_windows) - 1)]
                item = PublishingPlanItem(
                    publication_id=f"{package.date.isoformat()}-{len(items)+1:02d}",
                    date=package.date,
                    platform=str(rule.get("platform") or "Instagram"),
                    post_time=post_time,
                    content_type=content_type,
                    city=package.city,
                    day_type=package.day_type,
                    narrative_phase=getattr(package.life_state, "narrative_phase", "routine_stability") if package.life_state else "routine_stability",
                    scene_moment=scene.scene_moment or scene.description,
                    scene_source=scene.scene_source or scene.source,
                    scene_moment_type=scene.scene_moment_type,
                    moment_signature=scene.moment_signature,
                    visual_focus=scene.visual_focus,
                    activity_type=scene.activity,
                    outfit_ids=list(package.outfit.item_ids),
                    prompt_type=content_type,
                    prompt_text=prompt_text,
                    caption_text=caption,
                    short_caption=self._short_caption(caption),
                    delivery_status="planned",
                    notes=str(rule.get("notes") or ""),
                )
                items.append(item)
                if len(items) >= 2 and idx > 0:
                    break

        if not items:
            scene = package.scenes[-1] if package.scenes else DayScene(block="day", location=package.city, description=package.summary, mood="calm", time_of_day="day")
            items.append(
                PublishingPlanItem(
                    publication_id=f"{package.date.isoformat()}-01",
                    date=package.date,
                    platform="Instagram",
                    post_time=publish_windows[0] if publish_windows else "09:30",
                    content_type="photo",
                    city=package.city,
                    day_type=package.day_type,
                    narrative_phase=getattr(package.life_state, "narrative_phase", "routine_stability") if package.life_state else "routine_stability",
                    scene_moment=scene.scene_moment or scene.description,
                    scene_source=scene.scene_source or scene.source,
                    scene_moment_type=scene.scene_moment_type,
                    moment_signature=scene.moment_signature,
                    visual_focus=scene.visual_focus,
                    activity_type=scene.activity,
                    outfit_ids=list(package.outfit.item_ids),
                    prompt_type="photo",
                    prompt_text=self._pick_prompt_text(package, scene, "photo"),
                    caption_text=package.content.post_caption,
                    short_caption=self._short_caption(package.content.post_caption),
                    delivery_status="planned",
                    notes="fallback-guaranteed-post",
                )
            )

        package.publishing_plan = items
        for item in items:
            if hasattr(self.state, "append_publishing_plan"):
                self.state.append_publishing_plan(self._item_to_row(item))
        return items

    def _load_rules(self) -> List[Dict[str, Any]]:
        if hasattr(self.state, "load_posting_rules"):
            rules = self.state.load_posting_rules() or []
            if rules:
                return [r for r in rules if self._enabled(r)]
        return [r for r in DEFAULT_POSTING_RULES if self._enabled(r)]

    @staticmethod
    def _enabled(rule: Dict[str, Any]) -> bool:
        return str(rule.get("enabled", "true")).strip().lower() in {"1", "true", "yes", "y"}

    def _rule_matches_package(self, rule: Dict[str, Any], package: DailyPackage) -> bool:
        if not self._enabled(rule):
            return False
        return (
            self._match_filter(rule.get("day_type_filter"), package.day_type)
            and self._match_filter(rule.get("narrative_phase_filter"), getattr(package.life_state, "narrative_phase", "routine_stability") if package.life_state else "routine_stability")
            and self._match_filter(rule.get("city_filter"), package.city)
            and self._match_filter(rule.get("weekday_filter"), package.date.strftime("%A").lower())
        )

    @staticmethod
    def _match_filter(filter_value: Any, actual: str) -> bool:
        raw = str(filter_value or "").strip()
        if not raw:
            return True
        options = [x.strip().lower() for x in raw.split(",") if x.strip()]
        return actual.lower() in options

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            return default

    @staticmethod
    def _short_caption(text: str, limit: int = 120) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    @staticmethod
    def _pick_scene(scenes: List[DayScene], used_signatures: set[str]) -> DayScene | None:
        for scene in scenes:
            signature = scene.moment_signature or scene.scene_moment or scene.description
            if signature not in used_signatures:
                return scene
        return scenes[0] if scenes else None

    @staticmethod
    def _pick_prompt_text(package: DailyPackage, scene: DayScene, content_type: str) -> str:
        index = next((i for i, s in enumerate(package.scenes) if s == scene), 0)
        if content_type in {"video", "reel"} and package.content.video_prompts:
            return package.content.video_prompts[min(index, len(package.content.video_prompts) - 1)]
        if content_type in {"story", "stories", "text_note", "text"} and package.content.story_lines:
            return package.content.story_lines[min(index, len(package.content.story_lines) - 1)]
        if package.content.photo_prompts:
            return package.content.photo_prompts[min(index, len(package.content.photo_prompts) - 1)]
        return scene.scene_moment or scene.description

    @staticmethod
    def _item_to_row(item: PublishingPlanItem) -> Dict[str, Any]:
        row = asdict(item)
        row["date"] = item.date.isoformat()
        row["outfit_ids"] = ", ".join(item.outfit_ids)
        return row
