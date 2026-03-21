# Virtual AI Character Engine (MVP+)

Production-minded Python repository for managing a **transparent virtual AI character / digital persona** with strict continuity controls.

> Ethical positioning: this system is designed for disclosed virtual characters only. It should not be used to impersonate real humans or mislead audiences.

## What this project does

The engine generates a daily content package for a virtual influencer while preserving continuity:
- Character identity consistency (appearance, age, style boundaries)
- City/time/weather realism
- Outfit and wardrobe logic with cooldowns
- Day dramaturgy (morning/afternoon/evening)
- Prompt generation for photo/video
- Captions and story lines
- Continuity checks and conflict flags
- Telegram delivery with resilient fallback

Current evolution path is toward a **life simulation engine** where life-state (city, duty/rest logic, fatigue, mood, continuity memory) is computed first and content is derived from it.

## Architecture

`main.py` + modular package `src/virtual_persona`:

- `config` — runtime/env settings loader
- `models` — Pydantic domain models
- `storage` — local state backend + Google Sheets placeholder
- `services`
  - weather (`OpenWeather` + fallback)
  - sun (`Sunrise-Sunset` + fallback)
  - wardrobe selection and persistence
- `pipeline`
  - life engine (date/season/fatigue/mood baseline)
  - route engine (home-base + route-pool decisions)
  - context builder
  - daily planner
  - prompt composer (block-based prompt assembly)
  - content generator
  - continuity checker
  - orchestrator
- `delivery`
  - markdown package formatter
  - Telegram sender
- `llm`
  - provider interface
  - fallback/template provider
  - optional OpenAI provider

## Repository structure

- `config/`
  - `settings.example.yaml`
  - `character_bible.example.json`
  - `wardrobe.example.json`
  - `prompt_templates.example.json`
- `data/`
  - `samples/` (calendar/history demo data)
  - `state/` (runtime state)
  - `outputs/` (daily package json/md)
  - `logs/`
- `scripts/`
  - `bootstrap_google_sheet.py`
  - `telegram_polling.py`
- `cron/daily_pipeline.cron`
- `docs/vps_deploy.md`
- `tests/`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# optional extras:
pip install '.[telegram,google,llm]'
```

Copy and configure environment:

```bash
cp .env.example .env
```

Fill at minimum:
- `TIMEZONE`
- `DEFAULT_CITY`
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (for delivery)
- `OPENWEATHER_API_KEY` (optional but recommended)

## CLI commands

```bash
python main.py bootstrap
python main.py generate-day
python main.py generate-day --date 2026-01-12 --city Rome
python main.py check-continuity
python main.py send-telegram
python main.py test-run
```

### Command behavior
- `bootstrap` initializes local runtime folders
- `generate-day` runs full pipeline and saves output json
- `check-continuity` runs generation + prints continuity flags
- `send-telegram` sends short summary from today's package
- `test-run` generates and writes markdown package

## Telegram bot commands (polling script)

If you install telegram dependency:

```bash
python scripts/telegram_polling.py
```

Supported bot commands:
- `/generate_day`
- `/show_today`
- `/show_history`
- `/regenerate`
- `/set_city <City>`
- `/help`

## Google Sheets schema

Use `scripts/bootstrap_google_sheet.py` to initialize sheet tabs:

- `character_profile`
- `wardrobe`
- `cities`
- `scene_library`
- `daily_calendar`
- `content_history`
- `continuity_flags`
- `prompt_templates`
- `prompt_blocks`
- `route_pool`
- `life_state`
- `run_log`

New life-memory sheets (self-management layer):
- `wardrobe_items` (canonical item catalog with lifecycle fields)
- `outfit_memory` (history of assembled outfits)
- `wardrobe_actions` (AI decisions over wardrobe lifecycle)
- `shopping_candidates` (future additions suggested by AI)
- `scene_memory` (scene usage/repeat control)
- `activity_memory` (activity distribution memory)
- `location_memory` (location usage memory)
- `scene_candidates` (AI-generated scene proposals with continuity filters)
- `activity_candidates` (AI-generated activity proposals tied to day_type/mood/fatigue)
- `style_rules` (optional style brain rules for capsule strategy)

`prompt_templates` is still supported for backward compatibility, while `prompt_blocks` is used by `PromptComposer` to inject persistent identity/realism/continuity rules.

Prompt System v3 recommended `character_profile` fields for realism continuity:
- `device_profile`, `recurring_phone_device`
- `face_signature`, `face_shape`, `nose_bridge`, `cheekbone_softness`, `lip_fullness`, `brow_style`
- `favorite_locations`, `recurring_spaces`


Compatibility mode:
- Legacy `wardrobe` remains supported as fallback catalog source.
- If new memory sheets are absent/empty, pipeline still works with old behavior.

## Migration (Google Sheets) for life-memory stage

1. Run `python scripts/bootstrap_google_sheet.py` to create missing tabs.
2. Keep existing sheets unchanged: `character_profile`, `wardrobe`, `cities`, `scene_library`, `daily_calendar`, `content_history`, `continuity_flags`, `prompt_templates`, `prompt_blocks`, `route_pool`, `life_state`, `run_log`.
3. Create/populate new sheets with these headers:
   - `wardrobe_items`: `item_id,name,category,subcategory,color,style_tags,season_tags,weather_tags,occasion_tags,work_allowed,layer_role,warmth,status,owned_since,last_used,wear_count,times_in_content,capsule_role,style_vector,priority_score,notes`
   - `outfit_memory`: `date,outfit_id,item_ids,city,day_type,weather,occasion,used_in_content,repeat_score,notes`
   - `wardrobe_actions`: `date,action_type,target_item_id,reason,status,context_day_type,context_season,context_city,notes`
   - `shopping_candidates`: `candidate_id,category,subcategory,suggested_name,reason,priority,season,style_match,gap_score,status,notes`
   - `scene_memory`: `scene_id,last_used,usage_count,last_city,last_day_type,repeat_cooldown,status,notes`
   - `activity_memory`: `activity_id,activity_type,last_used,usage_count,context_tags,status,notes`
   - `location_memory`: `location_id,city,location_type,name,usage_count,last_used,season_tags,status,notes`
   - `scene_candidates`: `candidate_id,day_type,time_block,location,description,mood,activity_hint,city,season,source_context,generated_by_ai,status,score,notes`
   - `activity_candidates`: `candidate_id,activity_code,activity_label,day_type,time_block,city,season,mood_fit,fatigue_min,fatigue_max,weather_fit,source_context,generated_by_ai,status,score,notes`
   - `style_rules` (optional): `rule_id,rule_type,target,rule_value,priority,status,notes`
4. Optional gradual migration: copy relevant `wardrobe` rows into `wardrobe_items` and set `status=active`.
5. Run `python main.py test-run` and verify writes now include memory sheets in addition to existing outputs.

Required env for bootstrap:
- `GOOGLE_SERVICE_ACCOUNT_JSON_PATH`
- `GOOGLE_SHEET_ID`

## Continuity guarantees in MVP

Checks currently implemented:
- city jump detection without transfer day type
- outfit repeat warning in recent history
- weather vs scene clash (e.g. rain + bright sun)

Fallbacks:
- if weather API fails: safe configured weather fallback
- if sun API fails: default local sunrise/sunset fallback
- if Telegram fails: write markdown fallback in outputs
- if Google Sheets unavailable: local state mode continues

## OpenClaw integration

OpenClaw is optional and treated as an orchestration/trigger bridge only.
Core continuity logic and memory stay in Python modules and state files.

## VPS deploy

See `docs/vps_deploy.md` and `cron/daily_pipeline.cron`.

## Testing

```bash
pytest
```

## Production notes

Before production usage:
- Replace all example config/data with your character canon
- Add richer continuity rule set and scene library
- Add stronger transport constraints between cities
- Add content moderation and governance policy checks
- Add structured monitoring/alerts around failed runs

## Identity Pipeline (production upgrade)

### 1) Character Identity Pack

New storage root: `data/character_identity/`.

Contains:
- `character_identity_profile.json` (Character DNA / Identity Manifest)
- `references/face_reference.*`
- `references/half_body_reference.*`
- `references/full_body_reference.*`
- optional `expressions_pack`, `angles_pack`, lighting/style-neutral refs, walking/seated refs

Fallback behavior:
- If identity pack is incomplete, prompt system falls back to Character DNA + existing `character_profile` fields.
- Daily pipeline, publishing plan, Telegram output and day-freeze remain compatible.

### 2) Bootstrap workflow for new character (semi-automatic)

```bash
python scripts/bootstrap_identity_pack.py --input-dir data/identity_sources
```

Input: 3–8 user-selected source photos.
Output: initialized manifest and checklist.

Manual step required:
- Generate/select best synthetic base face candidate and set `reference_pack.face_reference`.

### 3) Identity pack expansion workflow (semi-automatic)

```bash
python scripts/expand_identity_pack.py --identity-root data/character_identity
```

Creates/updates expansion checklist for:
- half-body
- full-body
- expression and angle packs
- walking/seated references

Manual step required:
- User validates generated refs and rejects artifacts before marking references as ready.

### 4) Prompt System v4

Prompt blocks now follow strict structure:
1. identity anchor
2. body anchor
3. scene action
4. wardrobe block
5. camera block
6. realism block
7. continuity block
8. platform intent
9. negative prompt

Includes:
- adaptive `prompt_mode` (`compact` / `dense`)
- generation mode registry (`portrait`, `waist-up`, `seated`, `full-body`, `selfie`, `mirror-selfie`)
- layered negative prompts (universal + shot/location/mode)
- reference-aware bundle selection per shot archetype

### 5) Quality review and scoring

`run_log` now supports quality trace fields:
- `face_similarity`
- `scene_logic_score`
- `hand_integrity_flag`
- `body_consistency_flag`
- `artifact_flags`
- `prompt_mode`
- `reference_pack_used`

Scene sanity checker provides rule-based flags and allows manual rejection reason flow via metadata.

### 6) Clean image export

Utility: `virtual_persona.utils.export_utils.clean_image_export(source_path, target_path)`
- Removes metadata via Pillow re-save when available
- Falls back to safe byte-copy if Pillow unavailable

### 7) Publishing package output

Publishing plan rows now include additional package fields:
- `selected_image_path`
- `clean_image_export_path`
- `generation_diagnostics`
- `identity_mode`
- `reference_pack_type`
- `face_similarity_score`

### 8) Google Sheets update

`python scripts/bootstrap_google_sheet.py` now updates/creates headers for identity and quality analytics, including:
- `character_identity`
- `identity_references`
- `asset_quality`
- expanded `publishing_plan`, `content_history`, `run_log`

All writes use header names (not fixed column indexes), including reordered sheet headers.

### 9) Behavioral logic engine

The pipeline now has a dedicated behavioral layer between life state and daily content generation.

- Stable behavior traits live in the character profile as machine-readable tendencies such as quiet-morning preference, ritual need, repeat-place affinity, social openness, and stable caption voice.
- Slow behavior state tracks adaptation to city, accumulated fatigue, route familiarity, sense of home, emotional comfort, social reserve, location comfort, familiarity weight, and transition load.
- Daily behavior state computes energy, social openness, routine stability, transit fatigue, desire for quiet, desire for movement, emotional tone, emotional tone family, self-presentation mode, social presence mode, and caption voice mode.
- Recurring habits, familiar place anchors and families, familiarity score, recurring objects, object presence mode, emotional arc, transition hints, transition context, and caption voice constraints are generated and persisted into `behavior_memory`.
- Scene planning, scene moments, captions, prompt composition, and publishing metadata all consume the same `BehavioralContext` upstream.
- Telegram detail views now expose compact behavior diagnostics for each post.

See [docs/behavioral_engine.md](docs/behavioral_engine.md) for the full model and pipeline order.
