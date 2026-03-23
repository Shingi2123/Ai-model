from __future__ import annotations

from virtual_persona.models.domain import DailyPackage


def package_to_markdown(package: DailyPackage) -> str:
    issues = "\n".join(f"- [{i.level}] {i.code}: {i.message}" for i in package.continuity_issues) or "- нет"
    scenes = "\n".join(f"- {s.time_of_day.title()} • {s.location}: {s.description}" for s in package.scenes)
    photo_prompts = "\n".join(f"- {p}" for p in package.content.photo_prompts)
    video_prompts = "\n".join(f"- {p}" for p in package.content.video_prompts)
    behavior = package.behavioral_context
    behavior_block = ""
    if behavior is not None:
        behavior_block = (
            f"**Поведение:** {behavior.debug_summary}\n"
            f"**Эмоциональная фаза:** {behavior.emotional_arc}\n"
            f"**Привычка:** {behavior.selected_habit} ({behavior.habit_family})\n"
            f"**Память привычки:** {behavior.recurring_habit_summary}\n"
            f"**Якорь места:** {behavior.familiar_place_anchor} ({behavior.familiar_place_label})\n"
            f"**Семья места / знакомость:** {behavior.familiar_place_family} / {behavior.familiarity_score:.2f}\n"
            f"**Объекты:** {', '.join(behavior.recurring_objects)} ({behavior.object_presence_mode})\n"
            f"**Подача:** {behavior.daily_state.self_presentation_mode}\n\n"
        )

    return (
        f"# Дневной пакет контента — {package.date}\n\n"
        f"**Город:** {package.city}\n"
        f"**Тип дня:** {package.day_type}\n"
        f"**Сводка:** {package.summary}\n"
        f"**Погода:** {package.weather.condition}, {package.weather.temp_c}°C\n"
        f"**Солнце:** {package.sun.sunrise_local.time()} / {package.sun.sunset_local.time()}\n"
        f"**Образ:** {package.outfit.summary}\n\n"
        f"{behavior_block}"
        f"## Сцены\n{scenes}\n\n"
        f"## Подпись к посту\n{package.content.post_caption}\n\n"
        f"## Сторис\n" + "\n".join(f"- {s}" for s in package.content.story_lines) + "\n\n"
        f"## Фотопромпты\n{photo_prompts}\n\n"
        f"## Видеопромпты\n{video_prompts}\n\n"
        f"## Окна публикации\n" + "\n".join(f"- {w}" for w in package.content.publish_windows) + "\n\n"
        f"## Флаги консистентности\n{issues}\n"
    )
