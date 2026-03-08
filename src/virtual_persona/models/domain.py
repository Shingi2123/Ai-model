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

    def to_dict(self) -> dict:
        return asdict(self)
