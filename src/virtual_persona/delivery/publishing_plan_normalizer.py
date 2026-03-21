from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, is_dataclass
from datetime import date
from typing import Any, Mapping

from virtual_persona.models.domain import PublishingPlanItem


logger = logging.getLogger(__name__)

PUBLISHING_PLAN_HEADERS = [
    "publication_id",
    "date",
    "platform",
    "post_time",
    "content_type",
    "city",
    "day_type",
    "narrative_phase",
    "scene_moment",
    "scene_source",
    "scene_moment_type",
    "moment_signature",
    "visual_focus",
    "activity_type",
    "outfit_ids",
    "prompt_type",
    "prompt_text",
    "negative_prompt",
    "prompt_package_json",
    "shot_archetype",
    "platform_intent",
    "generation_mode",
    "framing_mode",
    "prompt_mode",
    "reference_type",
    "primary_anchors",
    "secondary_anchors",
    "manual_generation_step",
    "caption_text",
    "short_caption",
    "post_timezone",
    "publish_score",
    "selection_reason",
    "delivery_status",
    "notes",
    "emotional_arc",
    "habit_used",
    "habit_family",
    "familiar_place_anchor",
    "familiar_place_label",
    "recurring_objects_in_scene",
    "self_presentation_mode",
    "social_presence_mode",
    "transition_hint_used",
    "caption_voice_mode",
    "action_family",
    "social_context_hint",
    "day_behavior_summary",
    "selected_image_path",
    "clean_image_export_path",
    "generation_diagnostics",
    "identity_mode",
    "reference_pack_type",
    "face_similarity_score",
]

REQUIRED_PUBLISHING_PLAN_HEADERS = [
    "caption_text",
    "caption",
    "short_caption",
    "shot_archetype",
    "framing_mode",
    "generation_mode",
    "reference_type",
    "identity_mode",
    "primary_anchors",
    "secondary_anchors",
    "manual_generation_step",
    "prompt_mode",
    "platform",
    "moment",
    "prompt",
    "negative_prompt",
]

DEBUG_PATTERNS = (
    "score=",
    "selected_by_",
    "decision_explanation",
    "selection_reason",
    "generation_diagnostics",
    "reason=",
    "reasons=",
    "explanation",
    "debug",
)
FRAMING_PATTERNS = (
    "friend-shot",
    "friend shot",
    "3/4 body",
    "waist-up",
    "waist up",
    "head-and-shoulders",
    "head to mid-calf",
    "head-to-mid-calf",
    "full body",
    "head-to-toe",
    "mirror selfie",
    "front selfie",
)
MODE_TOKEN_RE = re.compile(r"(?:^|[\s,;/])[\w-]+_mode(?:$|[\s,;/])", re.IGNORECASE)
NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")
LEGACY_PROMPT_PATTERNS = (
    "half-body and 3/4 body framing from waist-up",
    "half-body",
    "from waist-up",
    "no plastic skin",
    "no identity drift",
    "no duplicate people",
    "no distorted limbs",
    "no fashion catalog symmetry",
    "no symmetry",
    "no overproduced lighting",
    "no overproduced campaign lighting",
)
TRAVEL_TOKENS = ("airport", "terminal", "travel", "flight", "layover", "boarding")
TRAVEL_WALK_TOKENS = ("walk", "walking", "stroll", "moving through")
SMARTPHONE_TOKENS = ("rounded personal smartphone", "personal smartphone", "smartphone in hand", "phone in hand")


def _to_mapping(source: Mapping[str, Any] | PublishingPlanItem | Any) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    if is_dataclass(source):
        return asdict(source)
    if hasattr(source, "__dict__"):
        return dict(vars(source))
    return {}


def _normalize_header(value: str) -> str:
    return str(value or "").strip().lower()


def _extract_value(container: Mapping[str, Any], *keys: str) -> str:
    normalized = {_normalize_header(key): value for key, value in container.items()}
    for key in keys:
        value = normalized.get(_normalize_header(key))
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _looks_like_debug(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in DEBUG_PATTERNS)


def _looks_like_mode_token(value: str) -> bool:
    return bool(MODE_TOKEN_RE.search(value))


def _looks_like_framing(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in FRAMING_PATTERNS)


def _is_invalid_caption(value: str) -> bool:
    return _looks_like_mode_token(value) or _looks_like_framing(value) or _looks_like_debug(value)


def _is_invalid_short_caption(value: str) -> bool:
    return _is_invalid_caption(value)


def _is_invalid_generation_mode(value: str) -> bool:
    lowered = value.lower()
    return "score=" in lowered or "reason=" in lowered or "selected_by_" in lowered


def _is_invalid_reference_type(value: str) -> bool:
    lowered = value.lower()
    return "selected_by_" in lowered or "decision" in lowered or "explanation" in lowered or "score=" in lowered


def _is_invalid_identity_mode(value: str) -> bool:
    return bool(NUMBER_RE.match(value.strip()))


def _warn_invalid_field(row: Mapping[str, Any], field_name: str, bad_value: str, fallback_value: str) -> None:
    logger.warning(
        "publishing_plan_normalizer invalid_field publication_id=%s field=%s bad_value=%r fallback=%r",
        _extract_value(row, "publication_id") or "<missing>",
        field_name,
        bad_value,
        fallback_value,
    )


def load_prompt_meta(source: Mapping[str, Any] | PublishingPlanItem | Any) -> dict[str, Any]:
    row = _to_mapping(source)
    raw = row.get("prompt_package_json")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def is_legacy_prompt(text: str, *, row: Mapping[str, Any] | None = None, prompt_meta: Mapping[str, Any] | None = None) -> bool:
    lowered = " ".join(str(text or "").lower().split())
    if not lowered:
        return False
    if any(token in lowered for token in LEGACY_PROMPT_PATTERNS):
        return True

    scene_text = " ".join(
        [
            _extract_value(row or {}, "scene_moment", "moment"),
            _extract_value(row or {}, "scene_source"),
            _extract_value(prompt_meta or {}, "scene_context"),
        ]
    ).lower()
    is_travel_walk = any(token in scene_text for token in TRAVEL_TOKENS) and any(token in scene_text for token in TRAVEL_WALK_TOKENS)
    if is_travel_walk and any(token in lowered for token in SMARTPHONE_TOKENS):
        return True
    return False


def resolve_canonical_prompt(
    source: Mapping[str, Any] | PublishingPlanItem | Any,
    *,
    default: str = "",
) -> tuple[str, str, bool, str]:
    row = _to_mapping(source)
    prompt_meta = load_prompt_meta(row)
    meta_prompt = _extract_value(prompt_meta, "final_prompt")
    meta_version = _extract_value(prompt_meta, "prompt_format_version") or ("v6" if meta_prompt else "")
    meta_legacy = is_legacy_prompt(meta_prompt, row=row, prompt_meta=prompt_meta)
    if meta_prompt and meta_legacy:
        logger.warning(
            "publishing_plan_normalizer legacy_prompt_detected publication_id=%s source=prompt_package_json.final_prompt",
            _extract_value(row, "publication_id") or "<missing>",
        )

    resolved_prompt = ""
    prompt_source = "missing"
    if meta_prompt and not meta_legacy:
        resolved_prompt = meta_prompt
        prompt_source = "prompt_package_json.final_prompt"
    else:
        row_prompt = _extract_value(row, "prompt_text", "prompt")
        if row_prompt and not is_legacy_prompt(row_prompt, row=row, prompt_meta=prompt_meta):
            resolved_prompt = row_prompt
            prompt_source = "row.prompt_text"
        else:
            resolved_prompt = default

    return resolved_prompt, prompt_source, meta_legacy, meta_version or ("v6" if resolved_prompt == meta_prompt and resolved_prompt else "")


def _resolve_field(
    row: Mapping[str, Any],
    prompt_meta: Mapping[str, Any],
    *,
    field_name: str,
    row_keys: tuple[str, ...],
    meta_keys: tuple[str, ...] = (),
    invalid_predicate=None,
    default: str = "",
) -> str:
    raw_value = _extract_value(row, *row_keys)
    if raw_value and not (invalid_predicate and invalid_predicate(raw_value)):
        return raw_value
    meta_value = _extract_value(prompt_meta, *(meta_keys or row_keys))
    if meta_value and not (invalid_predicate and invalid_predicate(meta_value)):
        if raw_value:
            _warn_invalid_field(row, field_name, raw_value, meta_value)
        return meta_value
    if raw_value and invalid_predicate and invalid_predicate(raw_value):
        _warn_invalid_field(row, field_name, raw_value, default)
        return default
    return raw_value or meta_value or default


def normalize_reference_aliases(value: str | None) -> list[str]:
    raw = (value or "").strip()
    if not raw:
        return []

    aliases: list[str] = []
    seen: set[str] = set()
    for chunk in raw.replace(";", ",").split(","):
        token = chunk.strip().replace("\\", "/")
        if not token:
            continue
        token = token.rstrip("/")
        parts = [part for part in token.split("/") if part and part != "."]
        alias = parts[-1] if parts else token
        if alias == "lifestyle" and len(parts) > 1 and parts[-2] == "wardrobe":
            alias = "wardrobe_lifestyle"
        if alias == "uniform" and len(parts) > 1 and parts[-2] == "wardrobe":
            alias = "wardrobe_uniform"
        if alias.lower() == "refs" and len(parts) > 1:
            alias = parts[-2]
        if alias not in seen:
            seen.add(alias)
            aliases.append(alias)
    return aliases


def format_reference_aliases(value: str | None) -> str:
    return ", ".join(normalize_reference_aliases(value))


def normalize_publishing_plan_payload(
    source: Mapping[str, Any] | PublishingPlanItem | Any,
    fallback_date: date,
    *,
    default_city: str = "",
    default_day_type: str = "work_day",
    default_narrative_phase: str = "routine_stability",
) -> dict[str, Any]:
    row = _to_mapping(source)
    prompt_meta = load_prompt_meta(row)
    row_date = _extract_value(row, "date") or fallback_date.isoformat()
    try:
        target_date = date.fromisoformat(row_date)
    except ValueError:
        target_date = fallback_date

    outfit_ids_raw = row.get("outfit_ids") or []
    if isinstance(outfit_ids_raw, str):
        outfit_ids = [x.strip() for x in outfit_ids_raw.split(",") if x.strip()]
    else:
        outfit_ids = list(outfit_ids_raw)

    caption_text = _resolve_field(
        row,
        prompt_meta,
        field_name="caption_text",
        row_keys=("caption_text", "caption"),
        meta_keys=("caption_text", "caption"),
        invalid_predicate=_is_invalid_caption,
    )
    short_caption = _resolve_field(
        row,
        prompt_meta,
        field_name="short_caption",
        row_keys=("short_caption",),
        meta_keys=("short_caption",),
        invalid_predicate=_is_invalid_short_caption,
        default=caption_text,
    )

    resolved_prompt, _, _, _ = resolve_canonical_prompt(row)

    return {
        "publication_id": _extract_value(row, "publication_id"),
        "date": target_date,
        "platform": _extract_value(row, "platform") or "Instagram",
        "post_time": _extract_value(row, "post_time") or "09:30",
        "content_type": _extract_value(row, "content_type") or "photo",
        "city": _extract_value(row, "city") or default_city,
        "day_type": _extract_value(row, "day_type") or default_day_type,
        "narrative_phase": _extract_value(row, "narrative_phase") or default_narrative_phase,
        "scene_moment": _extract_value(row, "scene_moment", "moment"),
        "scene_source": _extract_value(row, "scene_source"),
        "scene_moment_type": _extract_value(row, "scene_moment_type"),
        "moment_signature": _extract_value(row, "moment_signature"),
        "visual_focus": _extract_value(row, "visual_focus"),
        "activity_type": _extract_value(row, "activity_type"),
        "outfit_ids": outfit_ids,
        "prompt_type": _extract_value(row, "prompt_type"),
        "prompt_text": resolved_prompt,
        "negative_prompt": _resolve_field(
            row,
            prompt_meta,
            field_name="negative_prompt",
            row_keys=("negative_prompt",),
            meta_keys=("negative_prompt",),
        ),
        "prompt_package_json": str(row.get("prompt_package_json") or ""),
        "shot_archetype": _resolve_field(row, prompt_meta, field_name="shot_archetype", row_keys=("shot_archetype",)),
        "platform_intent": _resolve_field(row, prompt_meta, field_name="platform_intent", row_keys=("platform_intent",)),
        "generation_mode": _resolve_field(
            row,
            prompt_meta,
            field_name="generation_mode",
            row_keys=("generation_mode",),
            invalid_predicate=_is_invalid_generation_mode,
        ),
        "framing_mode": _resolve_field(row, prompt_meta, field_name="framing_mode", row_keys=("framing_mode",)),
        "prompt_mode": _resolve_field(row, prompt_meta, field_name="prompt_mode", row_keys=("prompt_mode",)),
        "reference_type": _resolve_field(
            row,
            prompt_meta,
            field_name="reference_type",
            row_keys=("reference_type", "reference_pack_type"),
            meta_keys=("reference_type", "reference_pack_type"),
            invalid_predicate=_is_invalid_reference_type,
        ),
        "primary_anchors": _resolve_field(row, prompt_meta, field_name="primary_anchors", row_keys=("primary_anchors",)),
        "secondary_anchors": _resolve_field(row, prompt_meta, field_name="secondary_anchors", row_keys=("secondary_anchors",)),
        "manual_generation_step": _resolve_field(
            row,
            prompt_meta,
            field_name="manual_generation_step",
            row_keys=("manual_generation_step",),
            meta_keys=("manual_generation_step", "manual_user_step"),
        ),
        "caption_text": caption_text,
        "short_caption": short_caption,
        "post_timezone": _extract_value(row, "post_timezone"),
        "publish_score": row.get("publish_score"),
        "selection_reason": _extract_value(row, "selection_reason"),
        "delivery_status": _extract_value(row, "delivery_status") or "planned",
        "notes": _extract_value(row, "notes"),
        "emotional_arc": _extract_value(row, "emotional_arc"),
        "habit_used": _extract_value(row, "habit_used"),
        "habit_family": _extract_value(row, "habit_family"),
        "familiar_place_anchor": _extract_value(row, "familiar_place_anchor"),
        "familiar_place_label": _extract_value(row, "familiar_place_label"),
        "recurring_objects_in_scene": _extract_value(row, "recurring_objects_in_scene"),
        "self_presentation_mode": _extract_value(row, "self_presentation_mode"),
        "social_presence_mode": _extract_value(row, "social_presence_mode"),
        "transition_hint_used": _extract_value(row, "transition_hint_used"),
        "caption_voice_mode": _extract_value(row, "caption_voice_mode"),
        "action_family": _extract_value(row, "action_family"),
        "social_context_hint": _extract_value(row, "social_context_hint"),
        "day_behavior_summary": _extract_value(row, "day_behavior_summary"),
        "selected_image_path": _extract_value(row, "selected_image_path"),
        "clean_image_export_path": _extract_value(row, "clean_image_export_path"),
        "generation_diagnostics": _extract_value(row, "generation_diagnostics"),
        "identity_mode": _resolve_field(
            row,
            prompt_meta,
            field_name="identity_mode",
            row_keys=("identity_mode",),
            invalid_predicate=_is_invalid_identity_mode,
        ),
        "reference_pack_type": _resolve_field(
            row,
            prompt_meta,
            field_name="reference_pack_type",
            row_keys=("reference_pack_type", "reference_type"),
            meta_keys=("reference_pack_type", "reference_type"),
            invalid_predicate=_is_invalid_reference_type,
        ),
        "face_similarity_score": row.get("face_similarity_score"),
    }


def item_from_payload(
    source: Mapping[str, Any] | PublishingPlanItem | Any,
    fallback_date: date,
    *,
    default_city: str = "",
    default_day_type: str = "work_day",
    default_narrative_phase: str = "routine_stability",
) -> PublishingPlanItem:
    return PublishingPlanItem(
        **normalize_publishing_plan_payload(
            source,
            fallback_date,
            default_city=default_city,
            default_day_type=default_day_type,
            default_narrative_phase=default_narrative_phase,
        )
    )
