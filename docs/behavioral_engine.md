# Behavioral Logic Engine

## Goal

`BehavioralLogicEngine` makes daily generation feel like one continuous life instead of isolated good-looking posts. It sits between global life state and scene/content generation and becomes an upstream driver for the day.

## Inputs

- Current date, city, weather, and `day_type`
- `narrative_context` with `narrative_phase` and energy
- Recent history, recent moment memory, and continuity hints
- Character profile, including stable behavior traits
- Stored `behavior_memory`

## Behavior Layers

### Stable traits

- `CharacterBehaviorProfile` stores long-lived tendencies: quiet mornings, ritual need, social openness, repeat-place affinity, hurry tolerance, familiar-space bias, caption restraint, recurring objects, and favorite habit/place archetypes.
- It also carries caption openness, preferred caption length, reflective bias, work/uniform alignment, travel lightness, and repeat-route preference so voice and scene logic are driven by the same persona profile.

### Slow state

- `SlowBehaviorState` tracks adaptation over time: city adaptation, route familiarity, sense of home, accumulated fatigue, emotional comfort, social reserve, city confidence, and settledness.
- It now also tracks `location_comfort`, `familiarity_weight`, and `recent_transition_load`, which makes new cities feel slightly less certain at first and prevents hard jumps after travel-heavy days.
- These values are smoothed with recent behavior memory, so adaptation does not reset every day.

### Daily state

- `DailyBehaviorState` tracks the short-lived mode of the day: energy, social openness, routine stability, transit fatigue, comfort in city, desire for quiet, desire for movement, emotional tone, mental load, hurry level, internal coherence, softness, self-presentation mode, social presence mode, and caption voice mode.
- It also assigns an `emotional_tone_family`, which is used by anti-repetition checks and caption shaping.
- Daily state depends on the slow state, `day_type`, `narrative_phase`, and previous daily behavior.

## Engine Output

`BehavioralContext` now includes:

- Stable profile, slow state, and daily state
- Emotional arc
- Selected habit and `habit_family`
- Familiar place anchor and human-readable place label
- Familiar place family and familiarity score
- Recurring object set for the day
- Object presence mode
- Outfit behavior mode
- Transition hint from previous day
- Transition context
- Allowed scene families
- Likely actions and `action_family`
- Gesture bias
- Social context hint
- Social presence detail
- Caption voice constraints
- Caption opening guard
- Anti-repetition flags

## Habit System

- Habits are not random one-off actions. Each habit has:
  - valid `day_type` contexts
  - a habit family
  - minimum repeat gap
  - preferred place anchor
  - object bias
  - action bias
- `behavior_memory` is used as recurring habit memory. The engine checks recent usage, family streaks, and repeat gaps before selecting a habit.

## Favorite Places and Familiar Spaces

- The engine stores place archetypes such as `quiet hotel window`, `airport side corridor`, `cafe corner near glass`, and `soft morning desk`.
- Selection favors places that fit the day and emotional state, but rotates them when repetition pressure is high.
- `city_adaptation`, `route_familiarity`, and `settledness` make new cities feel less familiar at first, then more stable over time.
- Each anchor also carries a place family plus a familiarity score, so the engine can return to the same kind of space without hard-copying the exact same scene too often.

## Recurring Objects

- Objects are selected from day-type defaults, habit-specific objects, and profile-level recurring items.
- Object continuity is soft, not literal inventory bookkeeping: travel days keep luggage and bags in play, quiet days can drop the phone, and repeated object bundles are rotated when overused.
- `object_presence_mode` tells downstream systems whether objects should be visibly functional, minimally present, or clearly travel-related in frame.

## Emotional Arc

- Emotional arc comes from narrative phase plus the computed day state.
- Supported arcs now include:
  - `between_flights_introspection`
  - `curious_city_openness`
  - `low_energy_recovery`
  - `quiet_settling`
  - `adaptation_in_new_city`
  - `subtle_pre_departure_melancholy`
  - `routine_stability`

## Anti-Repetition Guard

- The engine checks the last few behavior rows for:
  - same habit
  - same habit family
  - same familiar place
  - same familiar place family
  - same emotional arc
  - same emotional tone family
  - same caption voice mode
  - repeated object bundle pressure
  - repeated day-type streaks
- These are soft constraints. They steer the system toward another plausible branch without breaking continuity.

## Pipeline Order

The intended order is now:

1. Build base context.
2. Build `narrative_context`.
3. Recompute `behavioral_context` with narrative inputs available.
4. Use behavior to bias planner scene families.
5. Use behavior inside scene moment selection.
6. Use behavior in caption generation, prompt construction, and publishing metadata.
7. Persist one row into `behavior_memory`.

In practice this means behavior is upstream of scene family selection, action/object bias, outfit behavior mode, caption voice constraints, and transition hints.

## Persistence

`behavior_memory` stores one row per day with:

- emotional arc
- selected habit
- habit family
- familiar place anchor and label
- familiar place family and familiarity score
- recurring objects
- object presence mode
- self-presentation mode
- social presence mode
- transition hint
- transition context
- caption voice mode
- action family
- emotional tone family
- social context hint
- social presence detail
- caption voice constraints
- caption opening guard
- daily and slow behavior state payloads

## Telegram / Debugging

- Telegram detail view now exposes compact behavior fields: arc, habit, habit family, place anchor, place label, objects, self-presentation, social presence, action family, and social context.
- It now also shows habit memory, place family, familiarity score, object mode, transition context, tone family, social detail, and caption voice constraints.
- `day_behavior_summary` remains the compact high-level trace for quick inspection.

## Fallback Rules

- If behavior memory is missing, defaults from `CharacterBehaviorProfile` are used.
- If `narrative_context` is unavailable, the engine still returns a valid fallback behavior context.
- Missing persistence data should reduce richness, not break generation.
