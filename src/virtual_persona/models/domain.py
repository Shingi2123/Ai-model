from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import List, Optional


@dataclass
class Appearance:
    hair_color: str
    hair_length: str
    eye_color: str
    skin_tone: str
    body_type: str


@dataclass
class StyleProfile:
    preferred: List[str]
    disliked: List[str]
    palette: List[str]


@dataclass
class CharacterBible:
    name: str
    age: int
    bio: str
    appearance: Appearance
    personality: List[str]
    interests: List[str]
    favorite_places: List[str]
    style: StyleProfile
    canon_rules: List[str]
    boundaries: List[str]

    @classmethod
    def from_dict(cls, payload: dict) -> "CharacterBible":
        return cls(
            name=payload["name"],
            age=payload["age"],
            bio=payload["bio"],
            appearance=Appearance(**payload["appearance"]),
            personality=payload["personality"],
            interests=payload["interests"],
            favorite_places=payload["favorite_places"],
            style=StyleProfile(**payload["style"]),
            canon_rules=payload["canon_rules"],
            boundaries=payload["boundaries"],
        )


@dataclass
class WardrobeItem:
    id: str
    category: str
    name: str
    styles: List[str]
    colors: List[str]
    season: List[str]
    temp_min_c: int
    temp_max_c: int
    weather_tags: List[str]
    cooldown_days: int = 2
    last_used: Optional[date] = None


@dataclass
class WardrobeRules:
    required_categories: List[str]
    optional_categories: List[str]
    forbidden_color_pairs: List[List[str]]


@dataclass
class WardrobeCatalog:
    items: List[WardrobeItem]
    combination_rules: WardrobeRules

    @classmethod
    def from_dict(cls, payload: dict) -> "WardrobeCatalog":
        items = []
        for item in payload["items"]:
            last_used = date.fromisoformat(item["last_used"]) if item.get("last_used") else None
            items.append(WardrobeItem(**{**item, "last_used": last_used}))
        return cls(items=items, combination_rules=WardrobeRules(**payload["combination_rules"]))


@dataclass
class WeatherSnapshot:
    city: str
    temp_c: float
    condition: str
    humidity: int
    wind_speed: float
    cloudiness: int
    source: str = "api"


@dataclass
class SunSnapshot:
    sunrise_local: datetime
    sunset_local: datetime
    source: str = "api"


@dataclass
class DayScene:
    block: str
    location: str
    description: str
    mood: str
    time_of_day: str
    activity: str = ""
    source: str = "library"
    scene_moment: str = ""
    scene_moment_type: str = ""
    scene_source: str = ""
    moment_signature: str = ""
    moment_reason: str = ""
    visual_focus: str = ""
    publish_score: float | None = None
    publish_decision: str = ""
    decision_reason: str = ""


@dataclass
class OutfitSelection:
    item_ids: List[str]
    summary: str


@dataclass
class GeneratedContent:
    post_caption: str
    story_lines: List[str]
    photo_prompts: List[str]
    video_prompts: List[str]
    publish_windows: List[str]
    creative_notes: List[str]
    prompt_packages: List[dict] = field(default_factory=list)


@dataclass
class PublishingPlanItem:
    publication_id: str
    date: date
    platform: str
    post_time: str
    content_type: str
    city: str
    day_type: str
    narrative_phase: str
    scene_moment: str
    scene_source: str
    scene_moment_type: str
    moment_signature: str
    visual_focus: str
    activity_type: str
    outfit_ids: List[str]
    prompt_type: str
    prompt_text: str
    negative_prompt: str = ""
    prompt_package_json: str = ""
    shot_archetype: str = ""
    platform_intent: str = ""
    caption_text: str = ""
    short_caption: str = ""
    post_timezone: str = ""
    publish_score: float | None = None
    selection_reason: str = ""
    delivery_status: str = "planned"
    notes: str = ""
    selected_image_path: str = ""
    clean_image_export_path: str = ""
    generation_diagnostics: str = ""
    identity_mode: str = ""
    reference_pack_type: str = ""
    face_similarity_score: float | None = None


@dataclass
class PublishingPackage:
    selected_image_path: str
    clean_image_export_path: str
    caption: str
    short_caption: str
    post_time: str
    platform: str
    hashtags: str = ""
    publishing_notes: str = ""
    generation_diagnostics: str = ""


@dataclass
class ContinuityIssue:
    level: str
    code: str
    message: str


@dataclass
class DailyPackage:
    generated_at: datetime
    date: date
    city: str
    day_type: str
    summary: str
    weather: WeatherSnapshot
    sun: SunSnapshot
    outfit: OutfitSelection
    scenes: List[DayScene]
    content: GeneratedContent
    continuity_issues: List[ContinuityIssue] = field(default_factory=list)
    life_state: Optional["LifeState"] = None
    publishing_plan: List[PublishingPlanItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LifeState:
    date: date
    weekday: str
    month: int
    season: str
    is_holiday: bool
    holiday_name: str
    home_city: str
    current_city: str
    day_type: str
    day_type_reason: str
    fatigue_level: int
    mood_base: str
    continuity_note: str = ""
    narrative_phase: str = "routine_stability"
    energy_state: str = "medium"
    rhythm_state: str = "stable"
    novelty_pressure: float = 0.0
    recovery_need: float = 0.0


@dataclass
class RouteDecision:
    current_city: str
    day_type: str
    reason: str
