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
class CharacterBehaviorProfile:
    baseline_temperament: str = "soft_observant"
    social_openness: float = 0.42
    organization_level: float = 0.74
    comfort_with_haste: float = 0.32
    ritual_need: float = 0.78
    solitude_preference: float = 0.68
    city_wandering_affinity: float = 0.58
    coffee_affinity: float = 0.71
    window_pause_affinity: float = 0.8
    morning_pause_affinity: float = 0.82
    work_uniform_alignment: float = 0.76
    orderliness_with_items: float = 0.79
    self_photography_affinity: float = 0.41
    environment_photography_affinity: float = 0.64
    improvisation_tolerance: float = 0.43
    aesthetic_attention: float = 0.81
    repeat_place_affinity: float = 0.75
    preferred_repeat_routes: float = 0.72
    quiet_caption_restraint: float = 0.78
    caption_openness: float = 0.34
    caption_length_preference: float = 0.42
    reflective_bias: float = 0.72
    visual_consistency_need: float = 0.8
    familiar_space_bias: float = 0.74
    travel_lightness_preference: float = 0.76
    prefers_quiet_mornings: bool = True
    keeps_small_rituals: bool = True
    often_pauses_by_window: bool = True
    likes_light_travel_routine: bool = True
    not_overly_social_on_workdays: bool = True
    more_reflective_after_flights: bool = True
    keeps_outfit_neat_even_off_duty: bool = True
    avoids_overly_party_scenes_without_reason: bool = True
    uses_familiar_gestures_more_than_dramatic_posing: bool = True
    stable_caption_voice: str = "quiet_observational"
    favorite_habits: List[str] = field(default_factory=list)
    favorite_place_archetypes: List[str] = field(default_factory=list)
    recurring_objects: List[str] = field(default_factory=list)


@dataclass
class SlowBehaviorState:
    city_adaptation: float = 0.5
    accumulated_fatigue: float = 0.35
    sense_of_home: float = 0.45
    route_familiarity: float = 0.4
    emotional_comfort: float = 0.52
    social_reserve: float = 0.58
    city_confidence: float = 0.48
    settledness: float = 0.44
    location_comfort: float = 0.48
    familiarity_weight: float = 0.46
    recent_transition_load: float = 0.28


@dataclass
class DailyBehaviorState:
    energy_level: float = 0.56
    social_openness: float = 0.42
    routine_stability: float = 0.64
    transit_fatigue: float = 0.24
    comfort_in_city: float = 0.52
    desire_for_quiet: float = 0.63
    desire_for_movement: float = 0.47
    emotional_tone: str = "grounded"
    mental_load: float = 0.48
    hurry_level: float = 0.34
    internal_coherence: float = 0.64
    softness: float = 0.58
    self_presentation_mode: str = "soft_neat"
    internal_focus: str = "gentle"
    social_presence_mode: str = "alone_but_in_public"
    caption_voice_mode: str = "quiet_observational"
    emotional_tone_family: str = "grounded_daily"


@dataclass
class BehavioralContext:
    profile: CharacterBehaviorProfile
    slow_state: SlowBehaviorState
    daily_state: DailyBehaviorState
    emotional_arc: str
    selected_habit: str
    habit_family: str
    habit_context: str
    recurring_habit_summary: str
    familiar_place_anchor: str
    familiar_place_label: str
    familiar_place_family: str
    familiarity_score: float
    recurring_objects: List[str]
    object_presence_mode: str
    outfit_behavior_mode: str
    transition_hint: str
    transition_context: str
    allowed_scene_families: List[str]
    likely_actions: List[str]
    action_family: str
    gesture_bias: List[str]
    social_context_hint: str
    social_presence_detail: str
    caption_voice_constraints: List[str] = field(default_factory=list)
    caption_opening_guard: List[str] = field(default_factory=list)
    anti_repetition_flags: List[str] = field(default_factory=list)
    debug_summary: str = ""


@dataclass
class BehaviorState:
    energy_level: str
    social_mode: str
    emotional_arc: str
    habit: str
    place_anchor: str
    objects: List[str]
    self_presentation: str

    @property
    def selected_habit(self) -> str:
        return self.habit

    @property
    def recurring_objects(self) -> List[str]:
        return list(self.objects)

    @property
    def familiar_place_anchor(self) -> str:
        return self.place_anchor

    @property
    def familiar_place_label(self) -> str:
        labels = {
            "hotel_window": "hotel window",
            "kitchen_corner": "kitchen corner",
            "terminal_gate": "terminal gate",
            "cafe_corner": "cafe corner",
        }
        return labels.get(self.place_anchor, self.place_anchor.replace("_", " "))

    @property
    def familiar_place_family(self) -> str:
        families = {
            "hotel_window": "private_anchor",
            "kitchen_corner": "domestic_anchor",
            "terminal_gate": "transit_anchor",
            "cafe_corner": "public_anchor",
        }
        return families.get(self.place_anchor, "daily_anchor")

    @property
    def habit_family(self) -> str:
        families = {
            "window_pause": "pause",
            "coffee_moment": "ritual",
            "packing": "transition",
            "slow_walk": "movement",
            "none": "neutral",
        }
        return families.get(self.habit, "neutral")

    @property
    def recurring_habit_summary(self) -> str:
        return f"{self.habit} linked to {self.place_anchor}"

    @property
    def object_presence_mode(self) -> str:
        return "anchored_objects" if self.objects else "no_objects"

    @property
    def self_presentation_mode(self) -> str:
        return self.self_presentation

    @property
    def social_presence_mode(self) -> str:
        return self.social_mode

    @property
    def caption_voice_mode(self) -> str:
        mapping = {
            "arrival": "observational_arrival",
            "routine": "grounded_daily",
            "reflection": "quiet_reflective",
            "transition": "transitional",
            "departure": "restrained_departure",
        }
        return mapping.get(self.emotional_arc, "grounded_daily")

    @property
    def emotional_tone_family(self) -> str:
        mapping = {
            "arrival": "fresh_place",
            "routine": "grounded_daily",
            "reflection": "quiet_softness",
            "transition": "departure_tension",
            "departure": "departure_focus",
        }
        return mapping.get(self.emotional_arc, "grounded_daily")

    @property
    def action_family(self) -> str:
        mapping = {
            "window_pause": "still_pause",
            "coffee_moment": "small_ritual",
            "packing": "luggage_handling",
            "slow_walk": "walking",
            "none": "stillness",
        }
        return mapping.get(self.habit, "stillness")

    @property
    def social_context_hint(self) -> str:
        mapping = {
            "alone": "no people in frame",
            "light_public": "soft background people",
            "social": "public life visible around her",
        }
        return mapping.get(self.social_mode, "no people in frame")

    @property
    def social_presence_detail(self) -> str:
        mapping = {
            "alone": "alone in frame",
            "light_public": "background people only",
            "social": "shared public atmosphere",
        }
        return mapping.get(self.social_mode, "alone in frame")

    @property
    def transition_hint(self) -> str:
        mapping = {
            "arrival": "new_place",
            "routine": "steady_day",
            "reflection": "pause_and_notice",
            "transition": "before_leaving",
            "departure": "ready_to_move",
        }
        return mapping.get(self.emotional_arc, "steady_day")

    @property
    def transition_context(self) -> str:
        mapping = {
            "arrival": "arrival",
            "routine": "routine",
            "reflection": "reflection",
            "transition": "transition",
            "departure": "departure",
        }
        return mapping.get(self.emotional_arc, "routine")

    @property
    def caption_voice_constraints(self) -> List[str]:
        constraints = ["keep it natural", "avoid dramatic language"]
        if self.emotional_arc == "transition":
            constraints.append("hint at movement without overexplaining")
        if self.habit == "coffee_moment":
            constraints.append("allow a small everyday detail")
        return constraints

    @property
    def caption_opening_guard(self) -> List[str]:
        return ["another day", "just vibes"]

    @property
    def allowed_scene_families(self) -> List[str]:
        families: List[str] = []
        if self.energy_level == "low":
            families.extend(["static", "interior", "pause"])
        elif self.energy_level == "high":
            families.extend(["movement", "street", "walk"])
        else:
            families.extend(["daily", "anchored"])
        if self.social_mode == "alone":
            families.append("private")
        elif self.social_mode == "light_public":
            families.append("quiet_public")
        else:
            families.append("social_public")
        return families

    @property
    def likely_actions(self) -> List[str]:
        actions = {
            "window_pause": ["touching window", "still posture"],
            "coffee_moment": ["holding cup", "natural pause moment"],
            "packing": ["handling luggage", "checking bag"],
            "slow_walk": ["slow relaxed movement", "walking"],
            "none": ["still posture"],
        }
        return list(actions.get(self.habit, ["still posture"]))

    @property
    def gesture_bias(self) -> List[str]:
        gestures = {
            "relaxed": ["soft hands", "loose shoulders"],
            "composed": ["upright posture", "measured gesture"],
            "focused": ["intent gaze", "precise movement"],
            "soft": ["gentle expression", "small pause"],
            "transitional": ["slight distance in gaze", "thoughtful pause"],
        }
        return list(gestures.get(self.self_presentation, ["natural posture"]))

    @property
    def familiarity_score(self) -> float:
        return 0.82 if self.place_anchor in {"hotel_window", "kitchen_corner"} else 0.68

    @property
    def debug_summary(self) -> str:
        object_text = ",".join(self.objects) if self.objects else "none"
        return (
            f"energy={self.energy_level}; social={self.social_mode}; arc={self.emotional_arc}; "
            f"habit={self.habit}; place={self.place_anchor}; objects={object_text}; self={self.self_presentation}"
        )

    @property
    def daily_state(self) -> "BehaviorState":
        return self

    @property
    def anti_repetition_flags(self) -> List[str]:
        return list(getattr(self, "_anti_repetition_flags", []))

    @property
    def source(self) -> str:
        return str(getattr(self, "_source", "new"))


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
    social_presence: str = ""
    style_intensity: float | str | None = None
    outfit_style: str = ""
    enhance_attractiveness: float | str | None = None
    outfit_override: str = ""
    weather_hint: str = ""
    source: str = "library"
    scene_moment: str = ""
    scene_moment_type: str = ""
    scene_source: str = ""
    moment_signature: str = ""
    moment_reason: str = ""
    visual_focus: str = ""
    scene_family: str = ""
    action_family: str = ""
    location_family: str = ""
    publish_score: float | None = None
    publish_decision: str = ""
    decision_reason: str = ""


@dataclass
class OutfitSelection:
    item_ids: List[str]
    summary: str
    top: str = ""
    bottom: str = ""
    outerwear: str = ""
    shoes: str = ""
    accessories: str = ""
    fit: str = ""
    fabric: str = ""
    condition: str = ""
    styling: str = ""
    sentence: str = ""
    place: str = ""
    activity: str = ""
    time_of_day: str = ""
    weather_context: str = ""
    social_presence: str = ""
    energy: str = ""
    habit: str = ""
    style_intensity: float = 0.0
    outfit_style: str = ""
    enhance_attractiveness: float = 0.0
    outfit_override_used: str = ""
    style_profile: List[str] = field(default_factory=list)
    outfit_sentence: str = ""

    def prompt_sentence(self) -> str:
        return self.outfit_sentence or self.sentence or self.summary

    def structured_payload(self) -> dict:
        return {
            "top": self.top,
            "bottom": self.bottom,
            "outerwear": self.outerwear,
            "shoes": self.shoes,
            "accessories": self.accessories,
            "fit": self.fit,
            "fabric": self.fabric,
            "condition": self.condition,
            "styling": self.styling,
            "sentence": self.prompt_sentence(),
            "outfit_sentence": self.prompt_sentence(),
            "outfit_summary": self.summary or self.prompt_sentence(),
            "place": self.place,
            "activity": self.activity,
            "time_of_day": self.time_of_day,
            "weather_context": self.weather_context,
            "social_presence": self.social_presence,
            "energy": self.energy,
            "habit": self.habit,
            "style_intensity": self.style_intensity,
            "outfit_style": self.outfit_style,
            "enhance_attractiveness": self.enhance_attractiveness,
            "outfit_override_used": self.outfit_override_used,
            "style_profile": list(self.style_profile),
        }


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
    outfit_sentence: str = ""
    outfit_struct_json: str = ""
    outfit_summary: str = ""
    negative_prompt: str = ""
    prompt_package_json: str = ""
    shot_archetype: str = ""
    platform_intent: str = ""
    generation_mode: str = ""
    framing_mode: str = ""
    prompt_mode: str = ""
    reference_type: str = ""
    primary_anchors: str = ""
    secondary_anchors: str = ""
    manual_generation_step: str = ""
    caption_text: str = ""
    short_caption: str = ""
    post_timezone: str = ""
    publish_score: float | None = None
    selection_reason: str = ""
    delivery_status: str = "planned"
    notes: str = ""
    behavior_state: str = ""
    habit: str = ""
    place_anchor: str = ""
    objects: str = ""
    self_presentation: str = ""
    emotional_arc: str = ""
    habit_used: str = ""
    habit_family: str = ""
    recurring_habit_summary: str = ""
    familiar_place_anchor: str = ""
    familiar_place_label: str = ""
    familiar_place_family: str = ""
    familiarity_score: float | None = None
    recurring_objects_in_scene: str = ""
    object_presence_mode: str = ""
    self_presentation_mode: str = ""
    social_presence_mode: str = ""
    transition_hint_used: str = ""
    transition_context: str = ""
    caption_voice_mode: str = ""
    action_family: str = ""
    emotional_tone_family: str = ""
    social_context_hint: str = ""
    social_presence_detail: str = ""
    caption_voice_constraints: str = ""
    day_behavior_summary: str = ""
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
    behavioral_context: Optional[BehavioralContext] = None
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
