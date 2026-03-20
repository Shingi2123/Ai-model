# Behavioral Logic Engine

## Purpose

`BehavioralLogicEngine` turns the project from isolated daily scenes into a continuous persona life stream. It sits between global life state and daily content generation, producing a reusable behavior context for the whole day.

## Inputs

- Current date, city, and `day_type`
- `narrative_phase` and energy from narrative context
- Recent history, recent moments, and continuity hints
- Character profile fields, including long-lived behavior traits
- Stored behavior memory from previous generated days

## Layers

- Stable traits: long-lived preferences such as quiet mornings, ritual affinity, social openness, repeat-place affinity, and caption voice.
- Slow state: city adaptation, accumulated fatigue, route familiarity, sense of home, emotional comfort, and social reserve.
- Daily state: energy level, social openness, routine stability, transit fatigue, comfort in city, desire for quiet, desire for movement, emotional tone, mental load, self-presentation mode, social presence mode, and caption voice mode.

## Output

The engine returns `BehavioralContext` with:

- `profile`
- `slow_state`
- `daily_state`
- `emotional_arc`
- `selected_habit`
- `familiar_place_anchor`
- `recurring_objects`
- `outfit_behavior_mode`
- `transition_hint`
- `allowed_scene_families`
- `likely_actions`
- `gesture_bias`
- `anti_repetition_flags`

## Pipeline Order

The generation flow now works like this:

1. `ContextBuilder` loads life state, continuity, history, and behavior profile fields.
2. `BehavioralLogicEngine` computes stable, slow, and daily behavior.
3. `DailyPlanner` uses behavior to bias scene families and pacing.
4. `SceneMomentGenerator` uses habits, familiar places, recurring objects, social presence, and anti-repetition pressure.
5. Wardrobe and captions inherit self-presentation mode, emotional arc, and recurring behavior tone.
6. `PublishingPlanEngine` persists behavior metadata into each publication item.

## Memory Sheets

`behavior_memory` stores one row per day with:

- `daily_behavior_state`
- `slow_behavior_state`
- `emotional_arc`
- `selected_habit`
- `familiar_place_anchor`
- `recurring_objects_in_scene`
- `self_presentation_mode`
- `social_presence_mode`
- `transition_hint_used`
- `caption_voice_mode`
- `day_behavior_summary`

## Anti-Repetition Guard

The engine checks recent behavior memory and applies soft pressure against repeating:

- the same habit
- the same familiar place anchor
- the same emotional arc
- identical day-type streaks without variation

This does not block realistic continuity. It nudges the next day toward another plausible branch.

## Fallback Behavior

If behavior-specific data is missing, the engine falls back to:

- default behavior profile values
- current life state
- recent history if available

The pipeline stays functional even without stored behavior memory.
