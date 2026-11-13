"""Async WebUntis API client for Home Assistant."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date, datetime
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

_LOGGER = logging.getLogger(__name__)


class WebUntisApiError(Exception):
    """Base exception for WebUntis API errors."""


class WebUntisApiAuthError(WebUntisApiError):
    """Exception for authentication failures."""


@dataclass(slots=True)
class WebUntisSession:
    """Session information returned by WebUntis."""

    session_id: str
    person_id: int | None
    class_id: int | None
    jwt_token: str | None = None


class WebUntisApiClient:
    """Minimal async API client based on the TS webuntisrest implementation."""

    def __init__(
        self,
        session: ClientSession,
        school: str,
        username: str,
        password: str,
        base_url: str,
        client_identity: str,
    ) -> None:
        self._session = session
        self._school = school
        self._username = username
        self._password = password
        self._base_url = self._normalize_base_url(base_url)
        self._client_identity = client_identity
        self._session_info: WebUntisSession | None = None

    @property
    def school(self) -> str:
        """Return configured school identifier."""
        return self._school

    def _normalize_base_url(self, base_url: str) -> str:
        cleaned = base_url.strip()
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned.rstrip("/")
        return f"https://{cleaned.rstrip('/')}"

    def _cookie_header(self) -> str:
        if self._session_info is None:
            return ""

        school_base64 = base64.b64encode(self._school.encode("utf-8")).decode("ascii")
        return f"JSESSIONID={self._session_info.session_id}; schoolname={school_base64}"

    async def _request_jsonrpc(self, method: str, params: dict[str, Any]) -> Any:
        if self._session_info is None:
            raise WebUntisApiAuthError("No active session")

        payload = {
            "id": self._client_identity,
            "method": method,
            "params": params,
            "jsonrpc": "2.0",
        }

        url = f"{self._base_url}/WebUntis/jsonrpc.do"

        try:
            response = await self._session.post(
                url,
                params={"school": self._school},
                headers={
                    "Cookie": self._cookie_header(),
                    "X-Requested-With": "XMLHttpRequest",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
                json=payload,
                allow_redirects=False,
            )
            response.raise_for_status()
            data = await response.json()
        except ClientError as err:
            raise WebUntisApiError(f"JSON-RPC request failed: {err}") from err

        if "result" not in data:
            raise WebUntisApiError("JSON-RPC response did not include result")

        result = data["result"]
        if isinstance(result, dict) and result.get("code"):
            raise WebUntisApiError(f"WebUntis returned error code: {result['code']}")
        return result

    async def _ensure_jwt(self) -> None:
        if self._session_info is None:
            raise WebUntisApiAuthError("No active session")

        if self._session_info.jwt_token:
            return

        url = f"{self._base_url}/WebUntis/api/token/new"
        try:
            response = await self._session.get(
                url,
                headers={"Cookie": self._cookie_header()},
                allow_redirects=False,
            )
            response.raise_for_status()
            token = await response.text()
        except ClientError as err:
            raise WebUntisApiError(f"Failed to fetch JWT token: {err}") from err

        if not token:
            raise WebUntisApiError("JWT token response was empty")

        self._session_info.jwt_token = token

    async def async_login(self) -> None:
        """Authenticate against WebUntis and initialize the session."""
        payload = {
            "id": self._client_identity,
            "method": "authenticate",
            "params": {
                "user": self._username,
                "password": self._password,
                "client": self._client_identity,
            },
            "jsonrpc": "2.0",
        }
        url = f"{self._base_url}/WebUntis/jsonrpc.do"

        try:
            response = await self._session.post(
                url,
                params={"school": self._school},
                json=payload,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
                allow_redirects=False,
            )
            response.raise_for_status()
            data = await response.json()
        except ClientError as err:
            raise WebUntisApiError(f"Login request failed: {err}") from err

        result = data.get("result")
        if not isinstance(result, dict):
            raise WebUntisApiAuthError("Invalid login response from WebUntis")

        if result.get("code"):
            raise WebUntisApiAuthError(f"Login rejected with code: {result['code']}")

        session_id = result.get("sessionId")
        if not session_id:
            raise WebUntisApiAuthError("No sessionId received from WebUntis")

        self._session_info = WebUntisSession(
            session_id=session_id,
            person_id=result.get("personId"),
            class_id=result.get("klasseId"),
            jwt_token=None,
        )

        await self._ensure_jwt()

    async def async_validate_session(self) -> bool:
        """Validate current session with getLatestImportTime."""
        if self._session_info is None:
            return False

        try:
            result = await self._request_jsonrpc("getLatestImportTime", {})
        except WebUntisApiError:
            return False

        return isinstance(result, int)

    async def async_ensure_session(self) -> None:
        """Ensure the current session is valid, re-login when needed."""
        if self._session_info is None:
            await self.async_login()
            return

        is_valid = await self.async_validate_session()
        if not is_valid:
            _LOGGER.debug("WebUntis session is invalid, logging in again")
            await self.async_login()
            return

        if not self._session_info.jwt_token:
            await self._ensure_jwt()

    async def async_get_own_timetable(self, start_day: date, end_day: date) -> dict[str, Any]:
        """Fetch own timetable entries for the given date range."""
        await self.async_ensure_session()

        if self._session_info is None or self._session_info.person_id is None:
            raise WebUntisApiError("Current account does not expose a student personId")

        url = f"{self._base_url}/WebUntis/api/rest/view/v1/timetable/entries"
        params = {
            "start": start_day.isoformat(),
            "end": end_day.isoformat(),
            "format": "2",
            "resourceType": "STUDENT",
            "resources": str(self._session_info.person_id),
            "periodTypes": "",
            "timetableType": "MY_TIMETABLE",
            "layout": "START_TIME",
        }

        try:
            response = await self._session.get(
                url,
                params=params,
                headers={
                    "Cookie": self._cookie_header(),
                    "Authorization": f"Bearer {self._session_info.jwt_token}",
                },
                allow_redirects=False,
            )
            response.raise_for_status()
            data = await response.json()
        except ClientError as err:
            raise WebUntisApiError(f"Failed to fetch timetable: {err}") from err

        if not isinstance(data, dict):
            raise WebUntisApiError("Timetable response is not a JSON object")

        return data

    async def async_get_class_timetable(
        self,
        start_day: date,
        end_day: date,
        class_id: int | None = None,
    ) -> dict[str, Any]:
        """Fetch class timetable entries for the given date range."""
        await self.async_ensure_session()

        if self._session_info is None:
            raise WebUntisApiError("Missing session for class timetable request")

        resolved_class_id = class_id or self._session_info.class_id
        if resolved_class_id is None:
            raise WebUntisApiError("No class id is available for class timetable")

        url = f"{self._base_url}/WebUntis/api/rest/view/v1/timetable/entries"
        params = {
            "start": start_day.isoformat(),
            "end": end_day.isoformat(),
            "format": "1",
            "resourceType": "CLASS",
            "resources": str(resolved_class_id),
            "periodTypes": "",
            "timetableType": "STANDARD",
            "layout": "START_TIME",
        }

        try:
            response = await self._session.get(
                url,
                params=params,
                headers={
                    "Cookie": self._cookie_header(),
                    "Authorization": f"Bearer {self._session_info.jwt_token}",
                },
                allow_redirects=False,
            )
            response.raise_for_status()
            data = await response.json()
        except ClientError as err:
            raise WebUntisApiError(f"Failed to fetch class timetable: {err}") from err

        if not isinstance(data, dict):
            raise WebUntisApiError("Class timetable response is not a JSON object")

        return data

    async def async_get_timetable(
        self,
        start_day: date,
        end_day: date,
        scope: str,
        class_id: int | None = None,
    ) -> dict[str, Any]:
        """Fetch timetable entries based on configured scope."""
        if scope == "class":
            return await self.async_get_class_timetable(start_day, end_day, class_id)

        return await self.async_get_own_timetable(start_day, end_day)

    async def async_get_holidays(self) -> list[dict[str, Any]]:
        """Fetch all holidays from WebUntis."""
        await self.async_ensure_session()
        result = await self._request_jsonrpc("getHolidays", {})
        if not isinstance(result, list):
            raise WebUntisApiError("Holidays response is not a list")
        return [entry for entry in result if isinstance(entry, dict)]

    async def async_get_schoolyears(self) -> list[dict[str, Any]]:
        """Fetch school year metadata from WebUntis."""
        await self.async_ensure_session()
        result = await self._request_jsonrpc("getSchoolyears", {})
        if not isinstance(result, list):
            raise WebUntisApiError("Schoolyears response is not a list")
        return [entry for entry in result if isinstance(entry, dict)]

    @staticmethod
    def parse_untis_date(value: str | int | None) -> date | None:
        """Parse Untis date values in YYYYMMDD format."""
        if value is None:
            return None

        text = str(value)
        if len(text) != 8 or not text.isdigit():
            return None

        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None
