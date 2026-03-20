from __future__ import annotations

from virtual_persona.models.domain import DailyPackage


def package_to_markdown(package: DailyPackage) -> str:
    issues = "\n".join(f"- [{i.level}] {i.code}: {i.message}" for i in package.continuity_issues) or "- none"
    scenes = "\n".join(f"- {s.time_of_day.title()} • {s.location}: {s.description}" for s in package.scenes)
    photo_prompts = "\n".join(f"- {p}" for p in package.content.photo_prompts)
    video_prompts = "\n".join(f"- {p}" for p in package.content.video_prompts)
    behavior = package.behavioral_context
    behavior_block = ""
    if behavior is not None:
        behavior_block = (
            f"**Behavior:** {behavior.debug_summary}\n"
            f"**Emotional arc:** {behavior.emotional_arc}\n"
            f"**Habit:** {behavior.selected_habit}\n"
            f"**Place anchor:** {behavior.familiar_place_anchor}\n"
            f"**Objects:** {', '.join(behavior.recurring_objects)}\n"
            f"**Self-presentation:** {behavior.daily_state.self_presentation_mode}\n\n"
        )

    return (
        f"# Daily Content Package — {package.date}\n\n"
        f"**City:** {package.city}\n"
        f"**Day type:** {package.day_type}\n"
        f"**Summary:** {package.summary}\n"
        f"**Weather:** {package.weather.condition}, {package.weather.temp_c}°C\n"
        f"**Sun:** {package.sun.sunrise_local.time()} / {package.sun.sunset_local.time()}\n"
        f"**Outfit:** {package.outfit.summary}\n\n"
        f"{behavior_block}"
        f"## Scenes\n{scenes}\n\n"
        f"## Post Caption\n{package.content.post_caption}\n\n"
        f"## Story Lines\n" + "\n".join(f"- {s}" for s in package.content.story_lines) + "\n\n"
        f"## Photo Prompts\n{photo_prompts}\n\n"
        f"## Video Prompts\n{video_prompts}\n\n"
        f"## Publish Windows\n" + "\n".join(f"- {w}" for w in package.content.publish_windows) + "\n\n"
        f"## Continuity Flags\n{issues}\n"
    )
