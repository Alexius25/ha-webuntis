"""Coordinator for WebUntis integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WebUntisApiClient, WebUntisApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class WebUntisCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage WebUntis data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: WebUntisApiClient,
        interval_minutes: int,
        timetable_scope: str,
        class_id: int | None,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval_minutes),
        )
        self.api = api
        self.timetable_scope = timetable_scope
        self.class_id = class_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from WebUntis."""
        try:
            today = date.today()
            timetable = await self.api.async_get_timetable(
                today,
                today,
                self.timetable_scope,
                self.class_id,
            )
            holidays = await self.api.async_get_holidays()
            schoolyears = await self.api.async_get_schoolyears()
        except WebUntisApiError as err:
            raise UpdateFailed(str(err)) from err

        today_is_holiday = self._is_holiday(today, holidays)
        next_lesson = self._extract_next_lesson(timetable)
        lesson_count_today = self._lesson_count(timetable)
        changed_lessons_today = self._changed_lesson_count(timetable)
        current_schoolyear = self._current_schoolyear(today, schoolyears)

        return {
            "timetable_today": timetable,
            "holidays": holidays,
            "schoolyears": schoolyears,
            "is_holiday": today_is_holiday,
            "is_weekend": datetime.now().weekday() >= 5,
            "next_lesson": next_lesson,
            "lesson_count_today": lesson_count_today,
            "changed_lessons_today": changed_lessons_today,
            "current_schoolyear": current_schoolyear,
            "timetable_scope": self.timetable_scope,
            "class_id": self.class_id,
        }

    async def async_fetch_timetable_range(
        self,
        start_day: date,
        end_day: date,
    ) -> dict[str, Any]:
        """Fetch timetable for any date range using current coordinator profile."""
        return await self.api.async_get_timetable(
            start_day,
            end_day,
            self.timetable_scope,
            self.class_id,
        )

    def _extract_grid_entries(self, timetable: dict[str, Any]) -> list[dict[str, Any]]:
        days = timetable.get("days", [])
        entries: list[dict[str, Any]] = []

        for day in days:
            if not isinstance(day, dict):
                continue
            grid_entries = day.get("gridEntries")
            if isinstance(grid_entries, list):
                for entry in grid_entries:
                    if isinstance(entry, dict):
                        enriched_entry = dict(entry)
                        enriched_entry["__day_date"] = day.get("date")
                        entries.append(enriched_entry)

        return entries

    def extract_grid_entries(self, timetable: dict[str, Any]) -> list[dict[str, Any]]:
        """Public wrapper for timetable entry extraction."""
        return self._extract_grid_entries(timetable)

    def _extract_next_lesson(self, timetable: dict[str, Any]) -> dict[str, Any] | None:
        now_hhmm = datetime.now().strftime("%H:%M")
        entries = self._extract_grid_entries(timetable)

        entries.sort(
            key=lambda item: (
                (item.get("duration") or {}).get("start") or "23:59",
                (item.get("duration") or {}).get("end") or "23:59",
            )
        )

        for entry in entries:
            duration = entry.get("duration") or {}
            start = duration.get("start")
            if isinstance(start, str) and start >= now_hhmm:
                return entry

        return entries[0] if entries else None

    def _lesson_count(self, timetable: dict[str, Any]) -> int:
        return len(self._extract_grid_entries(timetable))

    def _changed_lesson_count(self, timetable: dict[str, Any]) -> int:
        count = 0
        for entry in self._extract_grid_entries(timetable):
            status = entry.get("status")
            if isinstance(status, str) and status != "REGULAR":
                count += 1
        return count

    def _is_holiday(self, current_day: date, holidays: list[dict[str, Any]]) -> bool:
        for holiday in holidays:
            start = self.api.parse_untis_date(holiday.get("startDate"))
            end = self.api.parse_untis_date(holiday.get("endDate"))
            if start and end and start <= current_day <= end:
                return True
        return False

    def _current_schoolyear(
        self, current_day: date, schoolyears: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        for schoolyear in sorted(
            schoolyears,
            key=lambda value: str(value.get("startDate") or ""),
            reverse=True,
        ):
            start = self.api.parse_untis_date(schoolyear.get("startDate"))
            end = self.api.parse_untis_date(schoolyear.get("endDate"))
            if start and end and start <= current_day <= end:
                return schoolyear

        return schoolyears[0] if schoolyears else None
