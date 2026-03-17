# Character Identity Pack Mapping

## What the current code expects

The pipeline reads `data/character_identity/character_identity_profile.json`.

Backward-compatible legacy keys still supported:

- `reference_pack.face_reference`
- `reference_pack.half_body_reference`
- `reference_pack.full_body_reference`
- `reference_pack.expressions_pack`
- `reference_pack.angles_pack`
- `reference_pack.lighting_neutral_reference`
- `reference_pack.style_neutral_reference`
- `reference_pack.walking_pose_reference`
- `reference_pack.seated_pose_reference`

Prompt selection now also supports `reference_manifest`, which maps real folders into semantic reference types used by the prompt system.

## Recommended folder layout

Put your existing pack under `data/character_identity/references/`:

- `data/character_identity/references/base`
- `data/character_identity/references/angles`
- `data/character_identity/references/body_consistency`
- `data/character_identity/references/expressions`
- `data/character_identity/references/full_body`
- `data/character_identity/references/identity_lock`
- `data/character_identity/references/selfies`
- `data/character_identity/references/wardrobe/lifestyle`
- `data/character_identity/references/wardrobe/uniform`

No pipeline rewrite is needed if the manifest points to those folders.

## Recommended mapping

- `face`: primary `base`, `identity_lock`; secondary `angles`, `expressions`
- `selfie`: primary `selfies`, `base`; secondary `identity_lock`, `angles`
- `full_body`: primary `full_body`, `body_consistency`; secondary `wardrobe/lifestyle`, `identity_lock`
- `lifestyle`: primary `wardrobe/lifestyle`, `body_consistency`; secondary `full_body`, `selfies`
- `uniform`: primary `wardrobe/uniform`, `full_body`; secondary `body_consistency`, `identity_lock`

Legacy compatibility is auto-derived from this mapping:

- `face_reference` <- face anchors
- `half_body_reference` <- lifestyle anchors
- `full_body_reference` <- full-body anchors
- `expressions_pack` <- expressions
- `angles_pack` <- angles

## Shot/generation selection rules

- `front_selfie`, `mirror_selfie`, `selfie_mode`, `mirror_selfie_mode` -> `selfie`
- `close_portrait`, `portrait_mode` -> `face`
- `seated_table_shot`, `waist_up`, `waist-up_mode`, `seated_lifestyle_mode` -> `lifestyle`
- `full_body`, `friend_shot`, `full-body_mode` -> `full_body`
- `uniform_mode` -> `uniform`

## Manual step that still remains

The project now decides which reference type and anchors are needed, but it still does not upload images to external generators.

Manual user step at generation time:

- open the external generator
- attach the primary anchor folder/files indicated by the prompt package
- optionally attach the secondary anchors for extra lock
- paste the generated prompt
- run generation and manually reject bad outputs/artifacts
