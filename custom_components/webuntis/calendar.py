"""Calendar platform for WebUntis."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import WebUntisCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WebUntis calendar entities."""
    coordinator: WebUntisCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WebUntisCalendarEntity(coordinator, entry)])


class WebUntisCalendarEntity(CoordinatorEntity[WebUntisCoordinator], CalendarEntity):
    """Calendar entity for timetable entries."""

    _attr_has_entity_name = True
    _attr_name = "Timetable"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: WebUntisCoordinator, entry: ConfigEntry) -> None:
        """Initialize WebUntis calendar entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming calendar event."""
        next_lesson = self.coordinator.data.get("next_lesson")
        if not isinstance(next_lesson, dict):
            return None
        return self._entry_to_calendar_event(next_lesson)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events in a datetime range."""
        timetable = await self.coordinator.async_fetch_timetable_range(
            start_date.date(),
            end_date.date(),
        )

        entries = self.coordinator.extract_grid_entries(timetable)
        events: list[CalendarEvent] = []

        for entry in entries:
            event = self._entry_to_calendar_event(entry)
            if event is None:
                continue

            if isinstance(event.start, datetime):
                if start_date <= event.start <= end_date:
                    events.append(event)

        return events

    def _entry_to_calendar_event(self, entry: dict[str, Any]) -> CalendarEvent | None:
        """Convert WebUntis grid entry to HA calendar event."""
        lesson_day = self._parse_lesson_day(entry.get("__day_date")) or date.today()

        duration = entry.get("duration") or {}
        start_time = self._parse_hhmm(duration.get("start"))
        end_time = self._parse_hhmm(duration.get("end"))
        if start_time is None or end_time is None:
            return None

        start = dt_util.as_local(datetime.combine(lesson_day, start_time))
        end = dt_util.as_local(datetime.combine(lesson_day, end_time))

        if end <= start:
            return None

        summary = str(entry.get("lessonText") or entry.get("name") or "Untis lesson")

        return CalendarEvent(
            summary=summary,
            start=start,
            end=end,
            description=str(entry.get("lessonInfo") or entry.get("substitutionText") or ""),
            location=None,
        )

    def _parse_hhmm(self, value: Any) -> time | None:
        """Parse HH:MM values returned by WebUntis."""
        if not isinstance(value, str) or ":" not in value:
            return None

        try:
            hour_str, minute_str = value.split(":", maxsplit=1)
            return time(hour=int(hour_str), minute=int(minute_str))
        except (TypeError, ValueError):
            return None

    def _parse_lesson_day(self, value: Any) -> date | None:
        """Parse lesson day from API payload."""
        if not isinstance(value, str):
            return None

        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            parsed = self.coordinator.api.parse_untis_date(value)
            return parsed
