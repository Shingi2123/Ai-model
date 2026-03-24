from datetime import date, datetime
import json

from virtual_persona.models.domain import (
    BehavioralContext,
    CharacterBehaviorProfile,
    DailyPackage,
    DailyBehaviorState,
    DayScene,
    GeneratedContent,
    LifeState,
    OutfitSelection,
    SlowBehaviorState,
    SunSnapshot,
    WeatherSnapshot,
)
from virtual_persona.pipeline.publishing_plan_engine import PublishingPlanEngine


class DummyState:
    def __init__(self, rules=None, history=None, existing_posts=None):
        self.rules = rules or []
        self.rows = []
        self.history = history or []
        self.logs = []
        self.existing_posts = existing_posts or []

    def load_posting_rules(self):
        return self.rules

    def append_publishing_plan(self, row):
        self.rows.append(row)

    def load_content_moment_memory(self):
        return self.history

    def load_publishing_plan(self, target_date=None):
        return self.existing_posts

    def save_run_log(self, status, message):
        self.logs.append((status, message))


def _build_package(day_type: str = "work_day", phase: str = "growth", scenes=None) -> DailyPackage:
    scenes = scenes or [
        DayScene(
            block="morning",
            location="cafe",
            description="coffee before work",
            mood="focused",
            time_of_day="morning",
            activity="coffee",
            scene_moment="hotel coffee by window",
            scene_moment_type="detail",
            scene_source="scene_moment_engine",
            moment_signature="coffee-window",
            visual_focus="espresso cup",
        ),
        DayScene(
            block="day",
            location="street",
            description="city transfer",
            mood="active",
            time_of_day="day",
            activity="commute",
            scene_moment="arriving at terminal",
            scene_moment_type="transition",
            scene_source="scene_moment_engine",
            moment_signature="terminal-transfer",
            visual_focus="departure board",
        ),
        DayScene(
            block="evening",
            location="river",
            description="golden hour",
            mood="calm",
            time_of_day="evening",
            activity="walk",
            scene_moment="golden hour river walk",
            scene_moment_type="cinematic",
            scene_source="scene_moment_engine",
            moment_signature="river-golden-hour",
            visual_focus="city lights",
        ),
    ]
    return DailyPackage(
        generated_at=datetime.utcnow(),
        date=date(2026, 1, 10),
        city="Prague",
        day_type=day_type,
        summary="day",
        weather=WeatherSnapshot(city="Prague", temp_c=20, condition="clear", humidity=10, wind_speed=1, cloudiness=0),
        sun=SunSnapshot(sunrise_local=datetime.utcnow(), sunset_local=datetime.utcnow()),
        outfit=OutfitSelection(
            item_ids=["look_1", "jeans"],
            summary="soft knit top, straight jeans, white sneakers, small shoulder bag and compact carry on",
            outfit_sentence="soft knit top, straight jeans, white sneakers, small shoulder bag and compact carry on; slightly relaxed fit with natural drape",
            top="soft knit top",
            bottom="straight jeans",
            shoes="white sneakers",
            accessories="small shoulder bag and compact carry on",
            fit="slightly relaxed fit with natural drape",
        ),
        scenes=scenes,
        content=GeneratedContent(
            post_caption="caption text",
            story_lines=["story-1", "story-2"],
            photo_prompts=["photo-1", "photo-2", "photo-3"],
            video_prompts=["video-1", "video-2", "video-3"],
            publish_windows=["09:00", "09:00", "09:00"],
            creative_notes=[],
            prompt_packages=[
                {"photo": {"final_prompt": "Identity: stable.\n\ncandid 3/4 body shot\n\nScene: coffee before work with a carry on, shoulder bag, and phone kept close.\n\nOutfit: soft knit top, straight jeans, white sneakers, small shoulder bag and compact carry on; slightly relaxed fit with natural drape.\n\nEnvironment: photorealistic cafe; lived-in environmental detail; accurate perspective and scale.\n\nMood: quiet confidence.", "negative_prompt": "bad anatomy", "shot_archetype": "friend_shot", "platform_intent": "instagram_feed", "generation_mode": "full-body_mode", "framing_mode": "friend-shot, 3/4 body", "prompt_mode": "dense", "identity_mode": "reference_manifest", "reference_pack_type": "full_body", "reference_type": "full_body", "primary_anchors": "ref/a.png, ref/b.png", "secondary_anchors": "ref/c.png", "manual_generation_step": "Attach 2-3 primary anchors, add 1 secondary anchor only if needed.", "outfit_sentence": "soft knit top, straight jeans, white sneakers, small shoulder bag and compact carry on; slightly relaxed fit with natural drape", "outfit_summary": "soft knit top, straight jeans, white sneakers, small shoulder bag and compact carry on; slightly relaxed fit with natural drape", "outfit_struct_json": "{\"top\": \"soft knit top\", \"bottom\": \"straight jeans\", \"shoes\": \"white sneakers\", \"accessories\": \"small shoulder bag and compact carry on\", \"fit\": \"slightly relaxed fit with natural drape\"}"}},
                {"photo": {"final_prompt": "Identity: stable.\n\nmirror selfie head-and-shoulders shot\n\nScene: arriving at terminal with a carry on, shoulder bag, and phone ready beside her.\n\nOutfit: soft knit top, straight jeans, white sneakers, small shoulder bag and compact carry on; slightly relaxed fit with natural drape.\n\nEnvironment: photorealistic terminal; accurate perspective and scale.\n\nMood: quiet confidence.", "negative_prompt": "bad anatomy", "shot_archetype": "mirror_selfie", "platform_intent": "instagram_feed", "generation_mode": "mirror_selfie_mode", "framing_mode": "mirror selfie, head-and-shoulders", "prompt_mode": "compact", "identity_mode": "reference_manifest", "reference_pack_type": "selfie", "reference_type": "selfie", "primary_anchors": "ref/selfie.png", "secondary_anchors": "ref/lock.png", "manual_generation_step": "Attach the main primary anchor, then add 1-2 supporting anchors if needed.", "outfit_sentence": "soft knit top, straight jeans, white sneakers, small shoulder bag and compact carry on; slightly relaxed fit with natural drape", "outfit_summary": "soft knit top, straight jeans, white sneakers, small shoulder bag and compact carry on; slightly relaxed fit with natural drape", "outfit_struct_json": "{\"top\": \"soft knit top\", \"bottom\": \"straight jeans\", \"shoes\": \"white sneakers\", \"accessories\": \"small shoulder bag and compact carry on\", \"fit\": \"slightly relaxed fit with natural drape\"}"}},
                {"photo": {"final_prompt": "Identity: stable.\n\ncandid 3/4 body shot\n\nScene: golden hour river walk with a carry on, shoulder bag, and phone kept nearby.\n\nOutfit: soft knit top, straight jeans, white sneakers, small shoulder bag and compact carry on; slightly relaxed fit with natural drape.\n\nEnvironment: photorealistic river walk; accurate perspective and scale.\n\nMood: quiet confidence.", "negative_prompt": "bad anatomy", "shot_archetype": "candid_handheld", "platform_intent": "instagram_feed", "generation_mode": "lifestyle_mode", "framing_mode": "candid handheld, 3/4 body", "prompt_mode": "dense", "identity_mode": "reference_manifest", "reference_pack_type": "lifestyle", "reference_type": "lifestyle", "primary_anchors": "ref/life.png", "secondary_anchors": "", "manual_generation_step": "Attach the main primary anchor, then add 1-2 supporting anchors if needed.", "outfit_sentence": "soft knit top, straight jeans, white sneakers, small shoulder bag and compact carry on; slightly relaxed fit with natural drape", "outfit_summary": "soft knit top, straight jeans, white sneakers, small shoulder bag and compact carry on; slightly relaxed fit with natural drape", "outfit_struct_json": "{\"top\": \"soft knit top\", \"bottom\": \"straight jeans\", \"shoes\": \"white sneakers\", \"accessories\": \"small shoulder bag and compact carry on\", \"fit\": \"slightly relaxed fit with natural drape\"}"}},
            ],
        ),
        life_state=LifeState(
            date=date(2026, 1, 10),
            weekday="saturday",
            month=1,
            season="winter",
            is_holiday=False,
            holiday_name="",
            home_city="Prague",
            current_city="Prague",
            day_type=day_type,
            day_type_reason="",
            fatigue_level=2,
            mood_base="good",
            narrative_phase=phase,
        ),
        behavioral_context=BehavioralContext(
            profile=CharacterBehaviorProfile(),
            slow_state=SlowBehaviorState(),
            daily_state=DailyBehaviorState(
                self_presentation_mode="travel_neat",
                social_presence_mode="alone_but_in_public",
                caption_voice_mode="quiet_observational",
            ),
            emotional_arc="between_flights_introspection",
            selected_habit="terminal_pause",
            habit_family="transit_ritual",
            habit_context="recurring_behavior",
            recurring_habit_summary="transit_ritual: last used 1d ago",
            familiar_place_anchor="airport side corridor",
            familiar_place_label="side corridor she tends to choose",
            familiar_place_family="transit_edge",
            familiarity_score=0.66,
            recurring_objects=["carry_on", "shoulder_bag", "phone"],
            object_presence_mode="transit_objects_visible",
            outfit_behavior_mode="travel_casual_mode",
            transition_hint="same_carry_on_carried_forward",
            transition_context="object_continuity",
            allowed_scene_families=["transit", "preparation"],
            likely_actions=["terminal_pause", "touch_bag_strap"],
            action_family="transit_ritual",
            gesture_bias=["touch_bag_strap"],
            social_context_hint="quiet_people_exist_around_her_but_not_center_frame",
            social_presence_detail="alone in frame, public life nearby",
            caption_voice_constraints=["keep it concise", "avoid melodrama"],
            debug_summary="energy=0.48; quiet=0.62; arc=between_flights_introspection",
        ),
    )


def test_publishing_plan_generates_reasonable_count_and_logs():
    state = DummyState()
    engine = PublishingPlanEngine(state)

    rows = engine.generate(_build_package(day_type="travel_day", phase="transition_phase"))

    assert 1 <= len(rows) <= 3
    assert state.rows
    assert any(status == "debug" and "publishing_decision" in msg for status, msg in state.logs)


def test_publishing_plan_avoids_duplicate_times_even_if_windows_repeat():
    state = DummyState()
    engine = PublishingPlanEngine(state)

    rows = engine.generate(_build_package(day_type="travel_day", phase="transition_phase"))

    times = [row.post_time for row in rows]
    assert len(times) == len(set(times))


def test_publishing_plan_can_return_zero_for_low_quality_recovery_day():
    state = DummyState()
    engine = PublishingPlanEngine(state)
    weak_scenes = [
        DayScene(
            block="day",
            location="home",
            description="rest",
            mood="calm",
            time_of_day="day",
            activity="rest",
            scene_moment="quiet room",
            scene_moment_type="transition",
            scene_source="scene_moment_engine",
            moment_signature="quiet-room",
            visual_focus="",
        )
    ]

    rows = engine.generate(_build_package(day_type="day_off", phase="recovery_phase", scenes=weak_scenes))

    assert len(rows) == 0


def test_publishing_plan_selects_subset_and_drops_duplicates():
    state = DummyState()
    engine = PublishingPlanEngine(state)
    scenes = [
        DayScene("morning", "cafe", "a", "focused", "morning", scene_moment="moment a", scene_moment_type="detail", moment_signature="same", visual_focus="cup"),
        DayScene("day", "cafe", "b", "focused", "day", scene_moment="moment b", scene_moment_type="detail", moment_signature="same", visual_focus="cup"),
        DayScene("evening", "street", "c", "active", "evening", scene_moment="moment c", scene_moment_type="cinematic", moment_signature="unique", visual_focus="lights"),
    ]

    rows = engine.generate(_build_package(day_type="travel_day", phase="transition_phase", scenes=scenes))

    signatures = [row.moment_signature for row in rows]
    assert len(signatures) == len(set(signatures))


def test_fallback_selects_one_when_primary_decision_returns_zero():
    state = DummyState(existing_posts=[{"date": "2026-01-10"}] * 8)
    engine = PublishingPlanEngine(state)

    rows = engine.generate(_build_package(day_type="work_day", phase="recovery_phase"))

    assert len(rows) == 1
    assert any("fallback_selected=1" in msg for status, msg in state.logs if status == "debug")


def test_fallback_does_not_select_when_best_score_below_soft_threshold():
    state = DummyState(existing_posts=[{"date": "2026-01-10"}] * 8)
    engine = PublishingPlanEngine(state)
    very_weak = [
        DayScene(
            block="night",
            location="home",
            description="late technical transfer",
            mood="tired",
            time_of_day="night",
            activity="sync",
            scene_moment="late router reset",
            scene_moment_type="technical",
            scene_source="scene_moment_engine",
            moment_signature="router-reset",
            visual_focus="",
        )
    ]

    rows = engine.generate(_build_package(day_type="work_day", phase="recovery_phase", scenes=very_weak))

    assert rows == []
    assert any("fallback_reason=best_ranked_below_soft_threshold" in msg for status, msg in state.logs if status == "debug")


def test_scene_decisions_are_written_with_fallback_metadata():
    state = DummyState(existing_posts=[{"date": "2026-01-10"}] * 8)
    engine = PublishingPlanEngine(state)
    package = _build_package(day_type="work_day", phase="recovery_phase")

    rows = engine.generate(package)

    assert len(rows) == 1
    decisions = {scene.moment_signature: scene.publish_decision for scene in package.scenes}
    assert "fallback_selected" in decisions.values()
    assert all(scene.publish_score is not None for scene in package.scenes)
    assert all(scene.decision_reason for scene in package.scenes)


def test_publishing_plan_row_contains_timezone_and_decision_metadata():
    state = DummyState()
    engine = PublishingPlanEngine(state)

    rows = engine.generate(_build_package(day_type="travel_day", phase="transition_phase"))

    assert rows
    first = rows[0]
    assert first.post_timezone
    assert first.publish_score is not None
    assert first.selection_reason

    persisted = state.rows[0]
    assert persisted["post_timezone"]
    assert persisted["publish_score"] is not None
    assert persisted["selection_reason"]
    assert "negative_prompt" in persisted
    assert first.emotional_arc == "between_flights_introspection"
    assert first.habit_used == "terminal_pause"
    assert first.habit_family == "transit_ritual"
    assert first.familiar_place_anchor == "airport side corridor"
    assert first.familiar_place_label
    assert first.day_behavior_summary
    assert first.action_family == "transit_ritual"
    assert first.social_context_hint
    assert first.identity_mode == "reference_manifest"
    assert first.reference_pack_type
    assert first.generation_mode
    assert first.framing_mode
    assert first.prompt_mode
    assert first.reference_type
    assert first.primary_anchors
    assert first.outfit_sentence
    assert first.outfit_struct_json
    assert first.outfit_summary
    assert json.loads(first.prompt_package_json)["outfit_sentence"] == first.outfit_sentence


def test_publishing_plan_keeps_required_text_fields_non_empty_even_with_empty_caption():
    state = DummyState()
    engine = PublishingPlanEngine(state)
    package = _build_package(day_type="travel_day", phase="transition_phase")
    package.content.post_caption = ""
    package.content.photo_prompts = ["legacy-photo-prompt"] * len(package.scenes)

    rows = engine.generate(package)

    assert rows
    assert all(row.prompt_text.strip() for row in rows)
    assert all(row.caption_text.strip() for row in rows)
    assert all(row.short_caption.strip() for row in rows)
    assert all(row.prompt_text == json.loads(row.prompt_package_json)["final_prompt"] for row in rows)


def test_publishing_plan_uses_prompt_package_final_prompt_as_canonical_source():
    state = DummyState()
    engine = PublishingPlanEngine(state)
    package = _build_package(day_type="travel_day", phase="transition_phase")
    package.content.photo_prompts = [
        "legacy formatted prompt with half-body and 3/4 body framing from waist-up",
        "legacy second prompt",
        "legacy third prompt",
    ]

    rows = engine.generate(package)

    assert all(row.prompt_text == json.loads(row.prompt_package_json)["final_prompt"] for row in rows)
    assert all("half-body and 3/4 body framing from waist-up" not in row.prompt_text.lower() for row in rows)


def test_publishing_plan_normalizer_prefers_only_prompt_package_final_prompt():
    from virtual_persona.delivery.publishing_plan_normalizer import resolve_canonical_prompt, resolve_outfit_sentence

    item = engine_item = _build_package(day_type="travel_day", phase="transition_phase").content.prompt_packages[0]["photo"]
    resolved, source, legacy, version = resolve_canonical_prompt(
        {
            "publication_id": "pub-1",
            "prompt_text": "legacy row prompt",
            "prompt_package_json": json.dumps(engine_item, ensure_ascii=False),
        }
    )
    outfit_sentence, outfit_source = resolve_outfit_sentence({"prompt_package_json": json.dumps(engine_item, ensure_ascii=False)})

    assert resolved == engine_item["final_prompt"]
    assert source == "prompt_package_json.final_prompt"
    assert legacy is False
    assert version
    assert outfit_sentence == engine_item["outfit_sentence"]
    assert outfit_source == "prompt_package_json.outfit_sentence"


def test_publishing_plan_uses_default_rules_when_store_has_none():
    state = DummyState(rules=[])
    engine = PublishingPlanEngine(state)

    rows = engine.generate(_build_package(day_type="work_day", phase="growth"))

    assert rows
    assert all(row.platform == "Instagram" for row in rows)
