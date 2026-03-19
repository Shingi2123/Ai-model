from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List

from virtual_persona.models.domain import DailyPackage, DayScene, PublishingPlanItem


DEFAULT_POSTING_RULES = [
    {"rule_id": "default-work-photo", "platform": "Instagram", "content_type": "photo", "preferred_time": "09:30", "enabled": "true", "priority": "10", "min_per_day": "1", "max_per_day": "2", "day_type_filter": "work_day", "narrative_phase_filter": "", "city_filter": "", "weekday_filter": "", "notes": "Work day cadence 1-2"},
    {"rule_id": "default-travel-photo", "platform": "Instagram", "content_type": "photo", "preferred_time": "10:00", "enabled": "true", "priority": "9", "min_per_day": "1", "max_per_day": "3", "day_type_filter": "travel_day", "narrative_phase_filter": "", "city_filter": "", "weekday_filter": "", "notes": "Travel day cadence 1-3"},
    {"rule_id": "default-weekend-photo", "platform": "Instagram", "content_type": "photo", "preferred_time": "11:00", "enabled": "true", "priority": "8", "min_per_day": "1", "max_per_day": "2", "day_type_filter": "weekend_day,day_off", "narrative_phase_filter": "", "city_filter": "", "weekday_filter": "", "notes": "Weekend cadence 1-2"},
    {"rule_id": "default-special-video", "platform": "Instagram", "content_type": "video", "preferred_time": "19:30", "enabled": "true", "priority": "11", "min_per_day": "2", "max_per_day": "3", "day_type_filter": "special_day,event_day", "narrative_phase_filter": "", "city_filter": "", "weekday_filter": "", "notes": "Special day cadence 2-3"},
    {"rule_id": "default-recovery-photo", "platform": "Instagram", "content_type": "photo", "preferred_time": "12:00", "enabled": "true", "priority": "12", "min_per_day": "1", "max_per_day": "1", "day_type_filter": "", "narrative_phase_filter": "recovery_phase", "city_filter": "", "weekday_filter": "", "notes": "Recovery phase keeps gentle rhythm"},
]


@dataclass
class RankedMoment:
    scene: DayScene
    score: float
    reasons: List[str]


logger = logging.getLogger(__name__)


class PublishingPlanEngine:
    MIN_GAP_MINUTES = 90
    SOFT_FALLBACK_SCORE_THRESHOLD = 1.6
    DAY_THEME_HINTS = {
        "travel_day": {"transit", "city_observation", "ambient_street"},
        "work_day": {"preparation", "work_setup", "transit"},
        "day_off": {"recovery", "meal", "hotel_private"},
        "layover_day": {"hotel_private", "city_observation", "recovery"},
    }


    def __init__(self, state_store) -> None:
        self.state = state_store

    def generate(self, package: DailyPackage) -> List[PublishingPlanItem]:
        rules = self._resolve_rules(package)
        persona_timezone = self._resolve_city_timezone(package.city)

        ranked = self._rank_moments(package)
        target_posts = self._decide_post_count(package, ranked)
        selected = self._select_diverse_moments(ranked, target_posts)
        initial_selected_count = len(selected)

        fallback_meta = {
            "applied": False,
            "reason": "not_needed",
            "chosen_signature": "",
            "chosen_score": None,
        }
        if not selected and ranked:
            selected, fallback_meta = self._apply_fallback_selection(ranked, selected)

        assigned_times = self._assign_times(package, selected, rules)
        content_types = self._assign_content_types(selected, rules)
        self._annotate_moment_decisions(package, ranked, selected, initial_selected_count, fallback_meta)

        items: List[PublishingPlanItem] = []
        for idx, ranked_moment in enumerate(selected):
            scene = ranked_moment.scene
            content_type = content_types[idx]
            prompt_meta = self._pick_prompt_package(package, scene, content_type)
            final_prompt = str(prompt_meta.get("final_prompt") or "").strip()
            caption = package.content.post_caption
            selection_reason = self._selection_reason(scene)
            item = PublishingPlanItem(
                publication_id=f"{package.date.isoformat()}-{idx+1:02d}",
                date=package.date,
                platform=self._rule_platform(rules),
                post_time=assigned_times[idx],
                content_type=content_type,
                city=package.city,
                day_type=package.day_type,
                narrative_phase=self._phase(package),
                scene_moment=scene.scene_moment or scene.description or "unspecified_scene",
                scene_source=scene.scene_source or scene.source or "scene_library",
                scene_moment_type=scene.scene_moment_type or "lifestyle",
                moment_signature=scene.moment_signature or f"{package.date.isoformat()}-{idx+1:02d}",
                visual_focus=scene.visual_focus or "natural daily detail",
                activity_type=scene.activity or "daily_life",
                outfit_ids=list(package.outfit.item_ids),
                prompt_type=content_type,
                prompt_text="",
                negative_prompt=str(prompt_meta.get("negative_prompt", "")),
                prompt_package_json=json.dumps(prompt_meta, ensure_ascii=False),
                shot_archetype=str(prompt_meta.get("shot_archetype", "")),
                platform_intent=str(prompt_meta.get("platform_intent", "")),
                generation_mode=str(prompt_meta.get("generation_mode", "")),
                framing_mode=str(prompt_meta.get("framing_mode", "")),
                prompt_mode=str(prompt_meta.get("prompt_mode", "")),
                reference_type=str(prompt_meta.get("reference_type", prompt_meta.get("reference_pack_type", ""))),
                primary_anchors=str(prompt_meta.get("primary_anchors", "")),
                secondary_anchors=str(prompt_meta.get("secondary_anchors", "")),
                manual_generation_step=str(prompt_meta.get("manual_generation_step", "")),
                caption_text=self._required_text(caption, scene.scene_moment or scene.description or "A quiet daily moment."),
                short_caption=self._short_caption(self._required_text(caption, scene.scene_moment or scene.description or "Daily moment"), limit=72),
                post_timezone=persona_timezone or "UTC",
                publish_score=ranked_moment.score if ranked_moment.score is not None else 0.0,
                selection_reason=selection_reason or "selected_for_publication",
                delivery_status="planned",
                notes=f"score={ranked_moment.score:.2f}; reasons={', '.join(ranked_moment.reasons[:3])}",
                identity_mode=str(prompt_meta.get("identity_mode", "")),
                reference_pack_type=str(prompt_meta.get("reference_pack_type", "")),
            )
            item.prompt_text = self._required_text(
                final_prompt,
                scene.scene_moment or scene.description or "daily lifestyle scene",
            )
            logger.info(f"[PROMPT_SAVE] {item.publication_id} prompt saved: {bool(item.prompt_text)}")
            items.append(item)

        package.publishing_plan = items

        if hasattr(self.state, "append_publishing_plan"):
            for item in items:
                self.state.append_publishing_plan(self._item_to_row(item))

        self._log_decision(package, ranked, selected, assigned_times, target_posts, initial_selected_count, fallback_meta)
        return items

    def _resolve_rules(self, package: DailyPackage) -> List[Dict[str, Any]]:
        rules = self._load_rules()
        matched = [r for r in rules if self._rule_matches_package(r, package)]
        if not matched:
            matched = [r for r in DEFAULT_POSTING_RULES if self._rule_matches_package(r, package)]
        return sorted(matched, key=lambda row: int(self._as_int(row.get("priority"), 0)), reverse=True)

    def _rank_moments(self, package: DailyPackage) -> List[RankedMoment]:
        rows = []
        history = self._load_recent_moment_signatures(lookback_days=7)

        for scene in package.scenes:
            score = 1.0
            reasons: List[str] = []
            moment = (scene.scene_moment or scene.description or "").lower()

            if scene.visual_focus:
                score += 0.8
                reasons.append("visual_focus")
            if scene.scene_moment_type and scene.scene_moment_type not in {"transition", "routine"}:
                score += 0.6
                reasons.append(f"moment_type:{scene.scene_moment_type}")
            if scene.time_of_day in {"morning", "day", "evening"}:
                score += 0.4
                reasons.append("clear_time_anchor")
            if package.day_type == "travel_day" and any(k in moment for k in ["station", "airport", "terminal", "street", "flight"]):
                score += 0.7
                reasons.append("travel_context")
            if self._phase(package) in {"transition_phase", "exploration_phase"} and scene.activity:
                score += 0.4
                reasons.append("phase_activity")
            if self._phase(package) == "recovery_phase" and "calm" in (scene.mood or ""):
                score += 0.3
                reasons.append("recovery_mood")
            if self._is_representative(scene, package.day_type):
                score += 0.8
                reasons.append("day_theme_representative")

            signature = scene.moment_signature or scene.scene_moment or scene.description
            if signature and signature in history:
                score -= 0.8
                reasons.append("recent_repeat_penalty")
            if scene.scene_moment_type in {"technical", "transition"}:
                score -= 0.4
                reasons.append("low_publish_type_penalty")

            rows.append(RankedMoment(scene=scene, score=round(score, 3), reasons=reasons))

        rows.sort(key=lambda r: r.score, reverse=True)
        return rows

    def _is_representative(self, scene: DayScene, day_type: str) -> bool:
        archetype = str(scene.scene_moment_type or "").strip().lower()
        moment = str(scene.scene_moment or scene.description or "").lower()
        hints = self.DAY_THEME_HINTS.get(day_type, set())
        if archetype in hints:
            return True
        if day_type == "travel_day" and any(token in moment for token in ["terminal", "airport", "flight", "station", "arrival"]):
            return True
        if day_type == "work_day" and any(token in moment for token in ["setup", "meeting", "desk", "preparation"]):
            return True
        return False

    def _decide_post_count(self, package: DailyPackage, ranked: List[RankedMoment]) -> int:
        if not ranked:
            return 0

        quality = sum(1 for r in ranked if r.score >= 1.9)
        very_strong = sum(1 for r in ranked if r.score >= 2.5)

        bounds = self._policy_bounds(package)
        min_policy = bounds["min"]
        max_policy = bounds["max"]

        base = 1 if quality > 0 else 0
        if package.day_type in {"travel_day", "event_day"} and very_strong >= 2:
            base += 1
        if self._phase(package) in {"exploration_phase", "transition_phase"} and quality >= 3:
            base += 1
        if self._phase(package) == "recovery_phase" and package.day_type != "travel_day":
            base = max(0, base - 1)

        fatigue = getattr(package.life_state, "fatigue_level", 3) if package.life_state else 3
        if fatigue >= 7:
            base = max(0, base - 1)

        recent = self._recent_post_volume(lookback_days=3)
        if recent >= 7:
            base = max(0, base - 1)

        raw = max(0, min(base, 3, quality if quality > 0 else base))
        if raw <= 0:
            return 0
        return min(max_policy, max(min_policy, raw))


    def _policy_bounds(self, package: DailyPackage) -> Dict[str, int]:
        matched = [r for r in self._load_rules() if self._rule_matches_package(r, package)]
        if not matched:
            return {"min": 0, "max": 3}
        mins = [self._as_int(r.get("min_per_day"), 0) for r in matched]
        maxs = [self._as_int(r.get("max_per_day"), 3) for r in matched]
        min_bound = max(0, max(mins) if mins else 0)
        max_bound = min(3, max(maxs) if maxs else 3)
        if max_bound < min_bound:
            max_bound = min_bound
        return {"min": min_bound, "max": max_bound}

    def _select_diverse_moments(self, ranked: List[RankedMoment], target_posts: int) -> List[RankedMoment]:
        selected: List[RankedMoment] = []
        for row in ranked:
            if len(selected) >= target_posts:
                break
            if self._is_duplicate_against_selected(row.scene, [x.scene for x in selected]):
                continue
            selected.append(row)
        return selected

    def _apply_fallback_selection(self, ranked: List[RankedMoment], selected: List[RankedMoment]) -> tuple[List[RankedMoment], Dict[str, Any]]:
        fallback_meta = {
            "applied": False,
            "reason": "no_ranked_candidates",
            "chosen_signature": "",
            "chosen_score": None,
        }
        if selected:
            fallback_meta["reason"] = "not_needed"
            return selected, fallback_meta
        if not ranked:
            return selected, fallback_meta

        best = ranked[0]
        fallback_meta["chosen_signature"] = best.scene.moment_signature or best.scene.scene_moment or best.scene.description
        fallback_meta["chosen_score"] = best.score

        if best.score >= self.SOFT_FALLBACK_SCORE_THRESHOLD:
            fallback_meta["applied"] = True
            fallback_meta["reason"] = "best_ranked_above_soft_threshold"
            return [best], fallback_meta

        fallback_meta["reason"] = "best_ranked_below_soft_threshold"
        return selected, fallback_meta

    def _annotate_moment_decisions(
        self,
        package: DailyPackage,
        ranked: List[RankedMoment],
        selected: List[RankedMoment],
        initial_selected_count: int,
        fallback_meta: Dict[str, Any],
    ) -> None:
        selected_keys = {
            (s.scene.moment_signature or s.scene.scene_moment or s.scene.description).strip().lower(): s
            for s in selected
        }
        fallback_key = (str(fallback_meta.get("chosen_signature") or "")).strip().lower() if fallback_meta.get("applied") else ""

        for row in ranked:
            scene = row.scene
            key = (scene.moment_signature or scene.scene_moment or scene.description).strip().lower()
            scene.publish_score = row.score
            if key in selected_keys:
                if fallback_key and key == fallback_key and initial_selected_count == 0:
                    scene.publish_decision = "fallback_selected"
                    scene.decision_reason = "selected_as_best_ranked_above_soft_threshold"
                else:
                    scene.publish_decision = "selected"
                    scene.decision_reason = "selected_by_primary_decision_and_diversity"
            else:
                if row.score < self.SOFT_FALLBACK_SCORE_THRESHOLD:
                    scene.publish_decision = "below_fallback_threshold"
                    scene.decision_reason = "score_below_soft_fallback_threshold"
                else:
                    scene.publish_decision = "not_in_top_subset"
                    scene.decision_reason = "not_selected_after_primary_decision_and_diversity"

    def _assign_times(self, package: DailyPackage, selected: List[RankedMoment], rules: List[Dict[str, Any]]) -> List[str]:
        if not selected:
            return []

        used: List[int] = []
        assigned: List[str] = []
        publish_windows = list(package.content.publish_windows or [])
        preferred_by_type = {str(rule.get("content_type") or "photo").lower(): str(rule.get("preferred_time") or "").strip() for rule in rules}

        for idx, ranked_moment in enumerate(selected):
            scene = ranked_moment.scene
            target_bucket = self._bucket_for_scene(scene)
            bucket_center = {"morning": 9 * 60 + 30, "day": 13 * 60 + 0, "evening": 19 * 60 + 0, "night": 21 * 60}[target_bucket]

            candidates = []
            if idx < len(publish_windows):
                t = self._parse_time_to_minutes(publish_windows[idx])
                if t is not None:
                    candidates.append(t)

            candidate_rule_time = preferred_by_type.get("photo" if idx == 0 else "video")
            if candidate_rule_time:
                t = self._parse_time_to_minutes(candidate_rule_time)
                if t is not None:
                    candidates.append(t)

            candidates.extend([bucket_center - 45, bucket_center, bucket_center + 40, bucket_center + 90])
            valid = [c for c in candidates if 6 * 60 <= c <= 23 * 60]
            picked = self._pick_non_colliding_time(valid, used)
            if picked is None:
                picked = self._fallback_time(used, bucket_center)
            used.append(picked)
            assigned.append(self._minutes_to_hhmm(picked))

        return assigned

    def _assign_content_types(self, selected: List[RankedMoment], rules: List[Dict[str, Any]]) -> List[str]:
        if not selected:
            return []
        sequence: List[str] = []
        for idx in range(len(selected)):
            if idx < len(rules):
                sequence.append(str(rules[idx].get("content_type") or "photo").strip().lower())
            else:
                sequence.append("photo")
        return sequence

    def _pick_non_colliding_time(self, candidates: List[int], used: List[int]) -> int | None:
        unique = sorted(set(candidates), key=lambda x: x)
        for candidate in unique:
            if all(abs(candidate - u) >= self.MIN_GAP_MINUTES for u in used):
                return candidate
        return None

    def _fallback_time(self, used: List[int], preferred: int) -> int:
        cursor = preferred
        while any(abs(cursor - u) < self.MIN_GAP_MINUTES for u in used):
            cursor += self.MIN_GAP_MINUTES
            if cursor > 22 * 60:
                cursor = max(7 * 60, preferred - self.MIN_GAP_MINUTES)
        return cursor

    @staticmethod
    def _bucket_for_scene(scene: DayScene) -> str:
        raw = (scene.time_of_day or scene.block or "day").lower()
        if "morn" in raw:
            return "morning"
        if raw in {"noon", "afternoon", "day"}:
            return "day"
        if "night" in raw:
            return "night"
        if "even" in raw:
            return "evening"
        return "day"

    @staticmethod
    def _parse_time_to_minutes(value: str) -> int | None:
        try:
            hours, minutes = value.strip().split(":", 1)
            h, m = int(hours), int(minutes)
            if 0 <= h < 24 and 0 <= m < 60:
                return h * 60 + m
            return None
        except Exception:
            return None

    @staticmethod
    def _minutes_to_hhmm(total: int) -> str:
        h = max(0, min(23, total // 60))
        m = max(0, min(59, total % 60))
        return f"{h:02d}:{m:02d}"

    @staticmethod
    def _is_duplicate_against_selected(scene: DayScene, selected: List[DayScene]) -> bool:
        sig = (scene.moment_signature or scene.scene_moment or scene.description).strip().lower()
        for existing in selected:
            ex_sig = (existing.moment_signature or existing.scene_moment or existing.description).strip().lower()
            if sig and sig == ex_sig:
                return True
            same_location = (scene.location or "").strip().lower() == (existing.location or "").strip().lower()
            same_type = (scene.scene_moment_type or "").strip().lower() == (existing.scene_moment_type or "").strip().lower()
            if same_location and same_type and same_type:
                return True
        return False

    def _recent_post_volume(self, lookback_days: int) -> int:
        if not hasattr(self.state, "load_publishing_plan"):
            return 0
        rows = self.state.load_publishing_plan() or []
        if not rows:
            return 0
        today = datetime.utcnow().date()
        count = 0
        for row in rows:
            try:
                row_date = date.fromisoformat(str(row.get("date")))
            except Exception:
                continue
            if 0 <= (today - row_date).days <= lookback_days:
                count += 1
        return count

    def _load_recent_moment_signatures(self, lookback_days: int) -> set[str]:
        signatures: set[str] = set()
        if not hasattr(self.state, "load_content_moment_memory"):
            return signatures

        rows = self.state.load_content_moment_memory() or []
        today = datetime.utcnow().date()
        for row in rows:
            raw_sig = str(row.get("moment_signature") or "").strip()
            if not raw_sig:
                continue
            raw_date = str(row.get("date") or "")
            try:
                dt = date.fromisoformat(raw_date)
            except Exception:
                continue
            if 0 <= (today - dt).days <= lookback_days:
                signatures.add(raw_sig)
        return signatures

    def _log_decision(
        self,
        package: DailyPackage,
        ranked: List[RankedMoment],
        selected: List[RankedMoment],
        assigned_times: List[str],
        target_posts: int,
        initial_selected_count: int,
        fallback_meta: Dict[str, Any],
    ) -> None:
        selected_signatures = [s.scene.moment_signature or s.scene.scene_moment or s.scene.description for s in selected]
        reasons = "; ".join(f"{(r.scene.moment_signature or r.scene.description)[:24]}={r.score:.2f}" for r in ranked[:5])
        fallback_part = (
            f" fallback_selected={1 if fallback_meta.get('applied') else 0}"
            f" fallback_reason={fallback_meta.get('reason')}"
            f" chosen_signature={fallback_meta.get('chosen_signature') or '-'}"
            f" chosen_score={fallback_meta.get('chosen_score') if fallback_meta.get('chosen_score') is not None else '-'}"
        )
        bounds = self._policy_bounds(package)
        message = (
            f"publishing_decision date={package.date.isoformat()} generated={len(package.scenes)} "
            f"ranked={len(ranked)} target={target_posts} policy_min={bounds['min']} policy_max={bounds['max']} selected_initial={initial_selected_count} selected={len(selected)} "
            f"times={','.join(assigned_times) or '-'} selected_signatures={selected_signatures} "
            f"top_scores={reasons}{fallback_part}"
        )
        if hasattr(self.state, "save_run_log"):
            self.state.save_run_log("debug", message)

    def _resolve_city_timezone(self, city: str) -> str:
        if hasattr(self.state, "load_cities"):
            for row in self.state.load_cities() or []:
                if str(row.get("city", "")).strip().lower() == city.strip().lower() and row.get("timezone"):
                    return str(row.get("timezone")).strip()
        return "UTC"

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
        return (
            self._match_filter(rule.get("day_type_filter"), package.day_type)
            and self._match_filter(rule.get("narrative_phase_filter"), self._phase(package))
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
    def _required_text(value: str, fallback: str) -> str:
        text = str(value or "").strip()
        return text or fallback

    @staticmethod
    def _pick_prompt_text(scene: DayScene, prompt_meta: Dict[str, Any]) -> str:
        final_prompt = str(prompt_meta.get("final_prompt") or "").strip()
        if final_prompt:
            return final_prompt
        return scene.scene_moment or scene.description


    @staticmethod
    def _pick_prompt_package(package: DailyPackage, scene: DayScene, content_type: str) -> Dict[str, Any]:
        packages = getattr(package.content, "prompt_packages", []) or []
        index = next((i for i, s in enumerate(package.scenes) if s == scene), 0)
        if not packages:
            return {}
        payload = packages[min(index, len(packages) - 1)]
        if not isinstance(payload, dict):
            return {}
        candidate = payload.get(content_type) or payload.get("photo") or {}
        if isinstance(candidate, dict):
            candidate.setdefault("platform_intent", "instagram_feed" if content_type in {"photo", "carousel"} else ("reel_cover" if content_type in {"video", "reel"} else "story_lifestyle"))
            return candidate
        return {}

    @staticmethod
    def _selection_reason(scene: DayScene) -> str:
        reason = str(getattr(scene, "decision_reason", "") or "").strip()
        if reason:
            return reason
        decision = str(getattr(scene, "publish_decision", "") or "").strip()
        if decision:
            return decision
        return "selected_for_publication"

    @staticmethod
    def _item_to_row(item: PublishingPlanItem) -> Dict[str, Any]:
        row = asdict(item)
        row["date"] = item.date.isoformat()
        row["outfit_ids"] = ", ".join(item.outfit_ids)
        return row

    @staticmethod
    def _phase(package: DailyPackage) -> str:
        return getattr(package.life_state, "narrative_phase", "routine_stability") if package.life_state else "routine_stability"

    @staticmethod
    def _rule_platform(rules: List[Dict[str, Any]]) -> str:
        if not rules:
            return "Instagram"
        return str(rules[0].get("platform") or "Instagram")
