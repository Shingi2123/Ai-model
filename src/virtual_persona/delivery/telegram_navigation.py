from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from virtual_persona.delivery.publishing_formatter import _convert_time_for_user, _post_header_emoji
from virtual_persona.delivery.publishing_plan_normalizer import (
    format_reference_aliases,
    item_from_payload,
    load_prompt_meta,
    resolve_canonical_prompt,
)
from virtual_persona.models.domain import PublishingPlanItem


logger = logging.getLogger(__name__)
SUMMARY_DIVIDER = "----------------"


@dataclass
class PlanScreenContext:
    target_date: date
    city: str
    day_type: str
    narrative_phase: str
    persona_timezone: str
    user_timezone: str


@dataclass
class ParsedCallback:
    view: str
    target_date: str | None = None
    publication_id: str | None = None
    post_index: int | None = None


def short_text(text: str, limit: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def _is_missing_value(value: str | None) -> bool:
    normalized = (value or "").strip()
    return not normalized or normalized.lower() == "unknown"


def _format_compact_meta(context: PlanScreenContext) -> list[str]:
    lines: list[str] = []
    if not _is_missing_value(context.city):
        lines.append(f"City: {context.city}")
    lines.append(f"Persona TZ: {context.persona_timezone}")
    lines.append(f"User TZ: {context.user_timezone}")
    lines.append("")
    lines.append(f"Day type: {context.day_type}")
    lines.append(f"Phase: {context.narrative_phase}")
    return lines


def format_plan_screen(context: PlanScreenContext, items: list[PublishingPlanItem]) -> str:
    header_lines = [f"Plan for {context.target_date.strftime('%d %B')}"]
    header_lines.extend(_format_compact_meta(context))
    header = "\n".join(header_lines)
    if not items:
        return f"{header}\n\nNo planned posts for this day yet."
    rows = []
    for idx, item in enumerate(items, start=1):
        source_tz = item.post_timezone or context.persona_timezone
        user_time = _convert_time_for_user(context.target_date, item.post_time, source_tz, context.user_timezone)
        rows.append(
            "\n".join(
                [
                    SUMMARY_DIVIDER,
                    "",
                    f"{_post_header_emoji(item.content_type)} POST #{idx}",
                    f"Persona: {item.post_time} ({source_tz})",
                    f"You: {user_time} ({context.user_timezone})",
                    f"Platform: {item.platform} • {item.content_type.title()}",
                    f"Moment: {short_text(item.scene_moment, 110)}",
                    f"Caption: {short_text(item.short_caption or item.caption_text, 140)}",
                ]
            )
        )
    return f"{header}\n\n" + "\n\n".join(rows)


def format_post_screen(context: PlanScreenContext, item: PublishingPlanItem, post_index: int) -> str:
    source_tz = item.post_timezone or context.persona_timezone
    user_time = _convert_time_for_user(context.target_date, item.post_time, source_tz, context.user_timezone)
    emoji = _post_header_emoji(item.content_type)
    behavior_line = (
        "\n\n🧠 Behavior:"
        f"\nEnergy: {item.behavior_state.split(';')[0].replace('energy=', '').strip() if item.behavior_state else 'medium'}"
        f"\nSocial: {item.social_presence_mode or 'alone'}"
        "\n\n🎭 Emotional arc:"
        f"\n{item.emotional_arc or 'routine'}"
        "\n\n🔁 Habit:"
        f"\n{item.habit or item.habit_used or 'none'}"
        "\n\n📍 Place:"
        f"\n{item.place_anchor or item.familiar_place_anchor or 'kitchen_corner'}"
        "\n\n🎒 Objects:"
        f"\n{short_text(item.objects or item.recurring_objects_in_scene or 'none', 80)}"
        "\n\n👤 Self:"
        f"\n{item.self_presentation or item.self_presentation_mode or 'relaxed'}"
    )
    return (
        f"{emoji} POST #{post_index + 1}\n\n"
        f"Platform: {item.platform}\n"
        f"Format: {item.content_type.title()}\n"
        f"Persona: {item.post_time} ({source_tz})\n"
        f"You: {user_time} ({context.user_timezone})\n\n"
        f"Moment: {short_text(item.scene_moment, 220)}\n"
        f"Caption: {short_text(item.short_caption or item.caption_text, 220)}"
        f"{behavior_line}"
    )


def _format_detail_header(item: PublishingPlanItem, post_index: int) -> str:
    return f"POST #{post_index + 1} - {item.platform} / {item.content_type.title()}"


def _display_value(value: str | None, fallback: str) -> str:
    return (value or "").strip() or fallback


def _format_field(label: str, value: str) -> str:
    return f"- {label}: {value}"


def _format_manual_generation_step(step: str | None) -> str:
    text = (step or "").strip()
    if not text:
        return "Attach 2-3 primary anchors. Add 1 extra only if generation starts drifting."
    lowered = " ".join(text.lower().split())
    known_translations = {
        "attach 2-3 primary anchors, add 1 secondary anchor if the generator starts drifting.": "Attach 2-3 primary anchors. Add 1 extra only if generation starts drifting.",
        "use the primary anchors first. add secondary anchors only if you need to reinforce angle, emotion, or body consistency.": "Use primary anchors first. Add secondary anchors only to reinforce angle, emotion, or body consistency.",
        "attach the primary anchors listed below for generation.": "Attach the primary anchors listed below.",
        "attach 2-3 primary anchors, add 1 secondary anchor only if needed.": "Attach 2-3 primary anchors. Add 1 secondary only if needed.",
    }
    return known_translations.get(lowered, text)


def format_prompt_screen(item: PublishingPlanItem, post_index: int) -> str:
    prompt_value, prompt_source, legacy_detected, prompt_format_version = resolve_canonical_prompt(item)
    prompt = (prompt_value or "").strip()
    if not prompt:
        prompt_meta = load_prompt_meta(item)
        prompt = str(prompt_meta.get("final_prompt") or "").strip()
        if prompt:
            prompt_source = "prompt_package_json.final_prompt_fallback"
    prompt = _display_value(prompt, "No saved prompt for this post.")
    caption = _display_value(item.caption_text, "No saved caption.")
    short_caption = _display_value(item.short_caption or item.caption_text, "No short caption.")
    negative = _display_value(item.negative_prompt, "No negative prompt.")
    shot_archetype = _display_value(item.shot_archetype, "Not set")
    generation_mode = _display_value(item.generation_mode, "Not set")
    framing_mode = _display_value(item.framing_mode, "Not set")
    prompt_mode = _display_value(item.prompt_mode, "Not set")
    identity_mode = _display_value(item.identity_mode, "Not set")
    reference_type = _display_value(item.reference_type or item.reference_pack_type, "Not set")
    primary_anchors = _display_value(format_reference_aliases(item.primary_anchors), "No primary anchors")
    secondary_anchors = _display_value(format_reference_aliases(item.secondary_anchors), "No secondary anchors")
    manual_generation_step = _format_manual_generation_step(item.manual_generation_step)
    logger.info(
        "telegram_detail_render publication_id=%s prompt_source=%s prompt_format_version=%s legacy_prompt_detected=%s",
        item.publication_id,
        prompt_source,
        prompt_format_version or "unknown",
        "yes" if legacy_detected else "no",
    )
    generation_block = "\n".join(
        [
            _format_field("Shot type", shot_archetype),
            _format_field("Framing", framing_mode),
            _format_field("Reference type", reference_type),
            _format_field("Generation mode", generation_mode),
        ]
    )
    references_block = "\n".join(
        [
            _format_field("Primary", primary_anchors),
            _format_field("Secondary", secondary_anchors),
            _format_field("How to use", manual_generation_step),
        ]
    )
    extra_block = "\n".join(
        [
            _format_field("Platform", item.platform),
            _format_field("Prompt mode", prompt_mode),
            _format_field("Identity mode", identity_mode),
            _format_field("Behavior", _display_value(item.behavior_state or item.day_behavior_summary, "energy=medium; social=alone")),
            _format_field("Emotional arc", _display_value(item.emotional_arc, "routine")),
            _format_field("Habit", _display_value(item.habit or item.habit_used, "none")),
            _format_field("Habit family", _display_value(item.habit_family, "neutral")),
            _format_field("Habit memory", _display_value(item.recurring_habit_summary, "same behavior thread")),
            _format_field("Place anchor", _display_value(item.place_anchor or item.familiar_place_anchor, "kitchen_corner")),
            _format_field("Place label", _display_value(item.familiar_place_label, item.place_anchor or "kitchen corner")),
            _format_field("Place family", _display_value(item.familiar_place_family, "daily_anchor")),
            _format_field("Familiarity", _display_value(str(item.familiarity_score) if item.familiarity_score is not None else "", "0.0")),
            _format_field("Objects", _display_value(item.objects or item.recurring_objects_in_scene, "none")),
            _format_field("Object mode", _display_value(item.object_presence_mode, "anchored_objects")),
            _format_field("Self-presentation", _display_value(item.self_presentation or item.self_presentation_mode, "relaxed")),
            _format_field("Social presence", _display_value(item.social_presence_mode, "alone")),
            _format_field("Social detail", _display_value(item.social_presence_detail, "alone in frame")),
            _format_field("Transition", _display_value(item.transition_context or item.transition_hint_used, "routine")),
            _format_field("Action family", _display_value(item.action_family, "stillness")),
            _format_field("Tone family", _display_value(item.emotional_tone_family, "grounded_daily")),
            _format_field("Voice constraints", _display_value(item.caption_voice_constraints, "keep it natural")),
            _format_field("Social context", _display_value(item.social_context_hint, "no people in frame")),
        ]
    )
    return (
        f"Prompt for {_format_detail_header(item, post_index)}\n\n"
        f"Generation\n{generation_block}\n\n"
        f"References\n{references_block}\n\n"
        "Prompt\n```\n"
        f"{prompt}\n"
        "```\n\n"
        "Negative prompt\n```\n"
        f"{negative}\n"
        "```\n\n"
        "Caption\n```\n"
        f"{caption}\n"
        "```\n\n"
        "Short caption\n```\n"
        f"{short_caption}\n"
        "```\n\n"
        f"Extra\n{extra_block}"
    )


def format_caption_screen(item: PublishingPlanItem, post_index: int) -> str:
    caption = (item.caption_text or item.short_caption or "").strip()
    body = caption if caption else "No saved caption for this post yet."
    return f"{_format_detail_header(item, post_index)}\n\nCaption:\n{body}"


def format_moment_screen(item: PublishingPlanItem, post_index: int) -> str:
    moment = (item.scene_moment or "").strip()
    body = moment if moment else "No saved moment for this post yet."
    return f"{_format_detail_header(item, post_index)}\n\nMoment:\n{body}"


def plan_item_key(item: PublishingPlanItem) -> str:
    if item.publication_id:
        return f"publication_id:{item.publication_id}"
    return "|".join([item.date.isoformat(), item.platform, item.content_type, item.scene_moment, item.post_time])


def normalize_plan_items(items: list[PublishingPlanItem]) -> list[PublishingPlanItem]:
    ordered = sorted(items, key=lambda item: (item.post_time, item.platform, item.content_type, item.publication_id or "", item.scene_moment))
    unique: list[PublishingPlanItem] = []
    seen: set[str] = set()
    for item in ordered:
        key = plan_item_key(item)
        if key in seen:
            continue
        seen.add(key)
        if not item.publication_id:
            item.publication_id = key
        unique.append(item)
    return unique


def build_plan_keyboard(items: list[PublishingPlanItem], target_date: date) -> list[list[tuple[str, str]]]:
    rows = []
    day = target_date.isoformat()
    for idx, item in enumerate(items):
        rows.append([(f"Post {idx + 1}", f"p:{day}:{item.publication_id}")])
    rows.append([("Refresh", f"plan:{day}")])
    return rows


def build_post_keyboard(target_date: date, publication_id: str) -> list[list[tuple[str, str]]]:
    day = target_date.isoformat()
    return [
        [("Prompt", f"pv:{day}:{publication_id}:prompt"), ("Caption", f"pv:{day}:{publication_id}:caption")],
        [("Moment", f"pv:{day}:{publication_id}:moment")],
        [("Back to plan", f"back:plan:{day}")],
    ]


def build_detail_keyboard(target_date: date, publication_id: str) -> list[list[tuple[str, str]]]:
    day = target_date.isoformat()
    return [[("Back to post", f"back:post:{day}:{publication_id}"), ("Back to plan", f"back:plan:{day}")]]


def parse_callback(data: str) -> ParsedCallback:
    if data == "plan:today" or data == "back:plan":
        return ParsedCallback(view="plan")
    if data.startswith("plan:"):
        return ParsedCallback(view="plan", target_date=data.split(":", 1)[1])
    if data.startswith("p:"):
        _, raw = data.split(":", 1)
        parts = raw.split(":")
        if len(parts) == 1:
            return ParsedCallback(view="post", post_index=int(parts[0]))
        return ParsedCallback(view="post", target_date=parts[0], publication_id=parts[1])
    if data.startswith("back:post:"):
        parts = data.split(":")
        if len(parts) == 3:
            return ParsedCallback(view="post", post_index=int(parts[-1]))
        return ParsedCallback(view="post", target_date=parts[2], publication_id=parts[3])
    if data.startswith("back:plan:"):
        return ParsedCallback(view="plan", target_date=data.split(":", 2)[2])
    if data.startswith("pv:"):
        parts = data.split(":")
        if len(parts) == 3:
            _, post_index, view_name = parts
            return ParsedCallback(view=view_name, post_index=int(post_index))
        _, target_date, publication_id, view_name = parts
        return ParsedCallback(view=view_name, target_date=target_date, publication_id=publication_id)
    raise ValueError(f"Unknown callback data: {data}")


def serialize_context(context: PlanScreenContext, items: list[PublishingPlanItem]) -> dict:
    return {
        "target_date": context.target_date.isoformat(),
        "city": context.city,
        "day_type": context.day_type,
        "narrative_phase": context.narrative_phase,
        "persona_timezone": context.persona_timezone,
        "user_timezone": context.user_timezone,
        "items": [
            {
                "publication_id": item.publication_id,
                "date": item.date.isoformat(),
                "platform": item.platform,
                "post_time": item.post_time,
                "content_type": item.content_type,
                "city": item.city,
                "day_type": item.day_type,
                "narrative_phase": item.narrative_phase,
                "scene_moment": item.scene_moment,
                "scene_source": item.scene_source,
                "scene_moment_type": item.scene_moment_type,
                "moment_signature": item.moment_signature,
                "visual_focus": item.visual_focus,
                "activity_type": item.activity_type,
                "outfit_ids": item.outfit_ids,
                "prompt_type": item.prompt_type,
                "prompt_text": item.prompt_text,
                "negative_prompt": item.negative_prompt,
                "prompt_package_json": item.prompt_package_json,
                "shot_archetype": item.shot_archetype,
                "platform_intent": item.platform_intent,
                "generation_mode": item.generation_mode,
                "framing_mode": item.framing_mode,
                "prompt_mode": item.prompt_mode,
                "identity_mode": item.identity_mode,
                "reference_type": item.reference_type,
                "reference_pack_type": item.reference_pack_type,
                "primary_anchors": item.primary_anchors,
                "secondary_anchors": item.secondary_anchors,
                "manual_generation_step": item.manual_generation_step,
                "caption": item.caption_text,
                "caption_text": item.caption_text,
                "short_caption": item.short_caption,
                "post_timezone": item.post_timezone,
                "delivery_status": item.delivery_status,
                "emotional_arc": item.emotional_arc,
                "habit_used": item.habit_used,
                "habit_family": item.habit_family,
                "recurring_habit_summary": item.recurring_habit_summary,
                "familiar_place_anchor": item.familiar_place_anchor,
                "familiar_place_label": item.familiar_place_label,
                "familiar_place_family": item.familiar_place_family,
                "familiarity_score": item.familiarity_score,
                "recurring_objects_in_scene": item.recurring_objects_in_scene,
                "object_presence_mode": item.object_presence_mode,
                "self_presentation_mode": item.self_presentation_mode,
                "social_presence_mode": item.social_presence_mode,
                "transition_hint_used": item.transition_hint_used,
                "transition_context": item.transition_context,
                "caption_voice_mode": item.caption_voice_mode,
                "action_family": item.action_family,
                "emotional_tone_family": item.emotional_tone_family,
                "social_context_hint": item.social_context_hint,
                "social_presence_detail": item.social_presence_detail,
                "caption_voice_constraints": item.caption_voice_constraints,
                "day_behavior_summary": item.day_behavior_summary,
            }
            for item in items
        ],
    }


def deserialize_context(raw: dict) -> tuple[PlanScreenContext, list[PublishingPlanItem]]:
    context = PlanScreenContext(
        target_date=date.fromisoformat(raw["target_date"]),
        city=raw["city"],
        day_type=raw["day_type"],
        narrative_phase=raw["narrative_phase"],
        persona_timezone=raw["persona_timezone"],
        user_timezone=raw["user_timezone"],
    )
    items = [
        item_from_payload(
            row,
            context.target_date,
            default_city=context.city,
            default_day_type=context.day_type,
            default_narrative_phase=context.narrative_phase,
        )
        for row in raw.get("items", [])
    ]
    return context, items


def item_from_row(row: dict, fallback_date: date) -> PublishingPlanItem:
    return item_from_payload(row, fallback_date)
