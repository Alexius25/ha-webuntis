"""Sensor platform for WebUntis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WebUntisCoordinator


@dataclass(frozen=True, kw_only=True)
class WebUntisSensorDescription(SensorEntityDescription):
    """Description for WebUntis sensors."""

    value_key: str
    lesson_key: str | None = None


SENSORS: tuple[WebUntisSensorDescription, ...] = (
    WebUntisSensorDescription(
        key="lessons_today",
        name="Lessons Today",
        icon="mdi:book-open-page-variant",
        value_key="lesson_count_today",
    ),
    WebUntisSensorDescription(
        key="changed_lessons_today",
        name="Changed Lessons Today",
        icon="mdi:update",
        value_key="changed_lessons_today",
    ),
    WebUntisSensorDescription(
        key="next_lesson",
        name="Next Lesson",
        icon="mdi:clock-outline",
        value_key="next_lesson",
        lesson_key="next_lesson",
    ),
    WebUntisSensorDescription(
        key="current_lesson",
        name="Current Lesson",
        icon="mdi:school",
        value_key="current_lesson",
        lesson_key="current_lesson",
    ),
    WebUntisSensorDescription(
        key="changed_lesson",
        name="Changed Lesson",
        icon="mdi:alert-circle-outline",
        value_key="changed_lesson",
        lesson_key="changed_lesson",
    ),
    WebUntisSensorDescription(
        key="next_changed_lesson",
        name="Next Changed Lesson",
        icon="mdi:clock-alert-outline",
        value_key="next_changed_lesson",
        lesson_key="next_changed_lesson",
    ),
    WebUntisSensorDescription(
        key="next_lesson_status",
        name="Next Lesson Status",
        icon="mdi:information-outline",
        value_key="next_lesson_status",
        lesson_key="next_lesson",
    ),
    WebUntisSensorDescription(
        key="current_lesson_status",
        name="Current Lesson Status",
        icon="mdi:information",
        value_key="current_lesson_status",
        lesson_key="current_lesson",
    ),
    WebUntisSensorDescription(
        key="changed_lesson_status",
        name="Changed Lesson Status",
        icon="mdi:alert",
        value_key="changed_lesson_status",
        lesson_key="changed_lesson",
    ),
    WebUntisSensorDescription(
        key="next_lesson_start",
        name="Next Lesson Start",
        icon="mdi:clock-start",
        value_key="next_lesson_start",
        lesson_key="next_lesson",
    ),
    WebUntisSensorDescription(
        key="next_lesson_end",
        name="Next Lesson End",
        icon="mdi:clock-end",
        value_key="next_lesson_end",
        lesson_key="next_lesson",
    ),
    WebUntisSensorDescription(
        key="current_schoolyear",
        name="Current Schoolyear",
        icon="mdi:calendar-range",
        value_key="current_schoolyear",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WebUntis sensor entities."""
    coordinator: WebUntisCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(WebUntisSensor(coordinator, entry, description) for description in SENSORS)


class WebUntisSensor(CoordinatorEntity[WebUntisCoordinator], SensorEntity):
    """Representation of a WebUntis sensor."""

    entity_description: WebUntisSensorDescription

    def __init__(
        self,
        coordinator: WebUntisCoordinator,
        entry: ConfigEntry,
        description: WebUntisSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True

    def _lesson_entries(self) -> list[dict[str, Any]]:
        """Return all timetable entries for the current day."""
        timetable = self.coordinator.data.get("timetable_today")
        if not isinstance(timetable, dict):
            return []
        if hasattr(self.coordinator, "extract_grid_entries"):
            return self.coordinator.extract_grid_entries(timetable)
        return []

    def _lesson_title(self, lesson: Any) -> str:
        """Return a readable title for a lesson."""
        if not isinstance(lesson, dict):
            return "none"
        return str(lesson.get("lessonText") or lesson.get("name") or "unknown")

    def _lesson_attributes(self, lesson: dict[str, Any]) -> dict[str, Any]:
        """Return the common lesson metadata used by HA automation."""
        duration = lesson.get("duration") or {}
        return {
            "lesson": lesson,
            "start": duration.get("start"),
            "end": duration.get("end"),
            "status": lesson.get("status"),
            "substitution_text": lesson.get("substitutionText"),
            "lesson_info": lesson.get("lessonInfo"),
            "room": lesson.get("room") or lesson.get("rooms"),
            "teacher": lesson.get("teacher") or lesson.get("teachers"),
            "lesson_text": lesson.get("lessonText") or lesson.get("name"),
        }

    def _current_lesson(self) -> dict[str, Any] | None:
        """Return the currently active lesson if any."""
        now_hhmm = datetime.now().strftime("%H:%M")
        for lesson in self._lesson_entries():
            duration = lesson.get("duration") or {}
            start = duration.get("start")
            end = duration.get("end")
            if isinstance(start, str) and isinstance(end, str):
                if start <= now_hhmm < end:
                    return lesson
        return None

    def _changed_lessons(self) -> list[dict[str, Any]]:
        """Return all changed lessons in the current timetable."""
        return [
            entry
            for entry in self._lesson_entries()
            if isinstance(entry.get("status"), str) and entry.get("status") != "REGULAR"
        ]

    def _next_changed_lesson(self) -> dict[str, Any] | None:
        """Return the next changed lesson after now."""
        now_hhmm = datetime.now().strftime("%H:%M")
        changed_lessons = self._changed_lessons()
        for lesson in changed_lessons:
            start = (lesson.get("duration") or {}).get("start")
            if isinstance(start, str) and start >= now_hhmm:
                return lesson
        return changed_lessons[0] if changed_lessons else None

    def _lookup_lesson(self, key: str | None) -> dict[str, Any] | None:
        """Return a lesson dict for a given entity lookup key."""
        if key == "next_lesson":
            return self.coordinator.data.get("next_lesson")
        if key == "current_lesson":
            return self._current_lesson()
        if key == "changed_lesson":
            changed_lessons = self._changed_lessons()
            return changed_lessons[0] if changed_lessons else None
        if key == "next_changed_lesson":
            return self._next_changed_lesson()
        return None

    @property
    def native_value(self) -> Any:
        """Return the sensor state."""
        key = self.entity_description.key
        lesson = self._lookup_lesson(self.entity_description.lesson_key)

        if key == "next_lesson":
            return self._lesson_title(lesson)
        if key == "current_lesson":
            return self._lesson_title(lesson)
        if key == "changed_lesson":
            return self._lesson_title(lesson)
        if key == "next_changed_lesson":
            return self._lesson_title(lesson)
        if key == "next_lesson_status":
            return (lesson or {}).get("status") or "unknown"
        if key == "current_lesson_status":
            return (lesson or {}).get("status") or "unknown"
        if key == "changed_lesson_status":
            return (lesson or {}).get("status") or "unknown"
        if key == "next_lesson_start":
            return ((lesson or {}).get("duration") or {}).get("start") or "unknown"
        if key == "next_lesson_end":
            return ((lesson or {}).get("duration") or {}).get("end") or "unknown"

        value = self.coordinator.data.get(self.entity_description.value_key)
        if key == "current_schoolyear":
            if not isinstance(value, dict):
                return "unknown"
            return value.get("name") or "unknown"
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes for richer context."""
        lesson = self._lookup_lesson(self.entity_description.lesson_key)
        if isinstance(lesson, dict):
            return self._lesson_attributes(lesson)

        if self.entity_description.key == "current_schoolyear":
            schoolyear = self.coordinator.data.get("current_schoolyear")
            if not isinstance(schoolyear, dict):
                return None

            return {
                "id": schoolyear.get("id"),
                "start_date": schoolyear.get("startDate"),
                "end_date": schoolyear.get("endDate"),
            }

        return None
