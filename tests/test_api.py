"""Unit tests for WebUntis API client."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import patch


if "aiohttp" not in sys.modules:
    aiohttp_stub = types.ModuleType("aiohttp")
    aiohttp_stub.ClientError = Exception
    aiohttp_stub.ClientSession = object
    sys.modules["aiohttp"] = aiohttp_stub


API_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "custom_components" / "webuntis" / "api.py"
)
API_SPEC = importlib.util.spec_from_file_location("webuntis_api_module", API_MODULE_PATH)
if API_SPEC is None or API_SPEC.loader is None:
    raise RuntimeError("Unable to load WebUntis API module for tests")

API_MODULE = importlib.util.module_from_spec(API_SPEC)
sys.modules[API_SPEC.name] = API_MODULE
API_SPEC.loader.exec_module(API_MODULE)
WebUntisApiClient = API_MODULE.WebUntisApiClient


class MockResponse:
    """Simple async-like response mock."""

    def __init__(self, json_data=None, text_data: str = "", status: int = 200):
        self._json_data = json_data
        self._text_data = text_data
        self.status = status

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


class MockSession:
    """Minimal aiohttp ClientSession mock."""

    def __init__(self, *, post_responses=None, get_responses=None):
        self.post_responses = list(post_responses or [])
        self.get_responses = list(get_responses or [])
        self.last_get = None
        self.last_post = None

    async def post(self, url, **kwargs):
        self.last_post = {"url": url, **kwargs}
        return self.post_responses.pop(0)

    async def get(self, url, **kwargs):
        self.last_get = {"url": url, **kwargs}
        return self.get_responses.pop(0)


def test_async_login_fetches_session_and_jwt():
    session = MockSession(
        post_responses=[
            MockResponse(
                json_data={
                    "result": {
                        "sessionId": "session-123",
                        "personId": 12,
                        "klasseId": 34,
                    }
                }
            )
        ],
        get_responses=[MockResponse(text_data="jwt-token-xyz")],
    )

    client = WebUntisApiClient(
        session=session,
        school="myschool",
        username="user",
        password="pass",
        base_url="example.webuntis.com",
        client_identity="HomeAssistant",
    )

    asyncio.run(client.async_login())

    assert client._session_info is not None
    assert client._session_info.session_id == "session-123"
    assert client._session_info.jwt_token == "jwt-token-xyz"


def test_async_get_timetable_uses_own_scope():
    session = MockSession(
        get_responses=[
            MockResponse(
                json_data={
                    "days": [
                        {
                            "date": "2026-11-13",
                            "gridEntries": [],
                        }
                    ]
                }
            )
        ]
    )

    client = WebUntisApiClient(
        session=session,
        school="myschool",
        username="user",
        password="pass",
        base_url="example.webuntis.com",
        client_identity="HomeAssistant",
    )
    client._session_info = type("Session", (), {
        "session_id": "session-1",
        "person_id": 777,
        "class_id": 123,
        "jwt_token": "jwt-1",
    })()

    async def _always_valid():
        return True

    client.async_validate_session = _always_valid  # type: ignore[method-assign]

    data = asyncio.run(
        client.async_get_timetable(date(2026, 11, 13), date(2026, 11, 13), "own")
    )

    assert isinstance(data, dict)
    assert session.last_get is not None
    assert session.last_get["params"]["resourceType"] == "STUDENT"
    assert session.last_get["params"]["resources"] == "777"


def test_async_get_timetable_uses_class_scope_with_explicit_class_id():
    session = MockSession(
        get_responses=[
            MockResponse(
                json_data={
                    "days": [
                        {
                            "date": "2026-11-13",
                            "gridEntries": [],
                        }
                    ]
                }
            )
        ]
    )

    client = WebUntisApiClient(
        session=session,
        school="myschool",
        username="user",
        password="pass",
        base_url="example.webuntis.com",
        client_identity="HomeAssistant",
    )
    client._session_info = type("Session", (), {
        "session_id": "session-1",
        "person_id": 777,
        "class_id": 123,
        "jwt_token": "jwt-1",
    })()

    async def _always_valid():
        return True

    client.async_validate_session = _always_valid  # type: ignore[method-assign]

    data = asyncio.run(
        client.async_get_timetable(
            date(2026, 11, 13),
            date(2026, 11, 13),
            "class",
            class_id=999,
        )
    )

    assert isinstance(data, dict)
    assert session.last_get is not None
    assert session.last_get["params"]["resourceType"] == "CLASS"
    assert session.last_get["params"]["resources"] == "999"


def test_sensor_exposes_changed_lesson_and_automation_fields():
    package_root = types.ModuleType("custom_components")
    package_root.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components")]
    sys.modules.setdefault("custom_components", package_root)

    webuntis_package = types.ModuleType("custom_components.webuntis")
    webuntis_package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components" / "webuntis")]
    sys.modules["custom_components.webuntis"] = webuntis_package

    homeassistant_module = types.ModuleType("homeassistant")
    homeassistant_module.__path__ = []
    sys.modules.setdefault("homeassistant", homeassistant_module)

    sensor_module = types.ModuleType("homeassistant.components.sensor")

    class SensorEntity:
        pass

    @dataclass(frozen=True, kw_only=True)
    class SensorEntityDescription:
        key: str | None = None
        name: str | None = None
        icon: str | None = None

    sensor_module.SensorEntity = SensorEntity
    sensor_module.SensorEntityDescription = SensorEntityDescription
    sys.modules["homeassistant.components.sensor"] = sensor_module

    config_entries_module = types.ModuleType("homeassistant.config_entries")
    config_entries_module.ConfigEntry = type("ConfigEntry", (), {})
    sys.modules["homeassistant.config_entries"] = config_entries_module

    core_module = types.ModuleType("homeassistant.core")
    core_module.HomeAssistant = type("HomeAssistant", (), {})
    sys.modules["homeassistant.core"] = core_module

    helpers_module = types.ModuleType("homeassistant.helpers")
    helpers_module.__path__ = []
    sys.modules["homeassistant.helpers"] = helpers_module

    entity_platform_module = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform_module.AddEntitiesCallback = object
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform_module

    coordinator_module = types.ModuleType("homeassistant.helpers.update_coordinator")

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

        def __class_getitem__(cls, item):
            return cls

    coordinator_module.CoordinatorEntity = CoordinatorEntity
    sys.modules["homeassistant.helpers.update_coordinator"] = coordinator_module

    const_module = types.ModuleType("custom_components.webuntis.const")
    const_module.DOMAIN = "webuntis"
    sys.modules["custom_components.webuntis.const"] = const_module

    coordinator_file_module = types.ModuleType("custom_components.webuntis.coordinator")

    class DummyCoordinator:
        pass

    coordinator_file_module.WebUntisCoordinator = DummyCoordinator
    sys.modules["custom_components.webuntis.coordinator"] = coordinator_file_module

    sensor_path = Path(__file__).resolve().parents[1] / "custom_components" / "webuntis" / "sensor.py"
    sensor_spec = importlib.util.spec_from_file_location("custom_components.webuntis.sensor", sensor_path)
    if sensor_spec is None or sensor_spec.loader is None:
        raise RuntimeError("Unable to load sensor module for tests")

    sensor_file = importlib.util.module_from_spec(sensor_spec)
    sys.modules["custom_components.webuntis.sensor"] = sensor_file
    sensor_spec.loader.exec_module(sensor_file)

    sensor_keys = {description.key for description in sensor_file.SENSORS}
    assert {"changed_lesson", "next_changed_lesson", "current_lesson", "next_lesson_status"}.issubset(sensor_keys)

    timetable = {
        "days": [
            {
                "date": "2026-11-13",
                "gridEntries": [
                    {
                        "duration": {"start": "08:00", "end": "08:45"},
                        "lessonText": "Deutsch",
                        "status": "REGULAR",
                    },
                    {
                        "duration": {"start": "09:00", "end": "09:45"},
                        "lessonText": "Mathe",
                        "status": "CANCELLED",
                        "substitutionText": "Vertretung",
                    },
                ],
            }
        ]
    }
    coordinator = types.SimpleNamespace(
        data={"timetable_today": timetable},
        extract_grid_entries=lambda timetable_data: [
            {
                "duration": {"start": "08:00", "end": "08:45"},
                "lessonText": "Deutsch",
                "status": "REGULAR",
            },
            {
                "duration": {"start": "09:00", "end": "09:45"},
                "lessonText": "Mathe",
                "status": "CANCELLED",
                "substitutionText": "Vertretung",
            },
        ],
    )
    entry = types.SimpleNamespace(entry_id="entry-1")

    changed_description = next(
        description for description in sensor_file.SENSORS if description.key == "changed_lesson"
    )
    changed_sensor = sensor_file.WebUntisSensor(coordinator, entry, changed_description)
    assert changed_sensor.native_value == "Mathe"
    assert changed_sensor.extra_state_attributes["status"] == "CANCELLED"
    assert changed_sensor.extra_state_attributes["lesson"]["lessonText"] == "Mathe"

    class MockDateTime(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 11, 13, 8, 30)

    current_description = next(
        description for description in sensor_file.SENSORS if description.key == "current_lesson"
    )
    current_sensor = sensor_file.WebUntisSensor(coordinator, entry, current_description)
    with patch.object(sensor_file, "datetime", MockDateTime):
        assert current_sensor.native_value == "Deutsch"
        assert current_sensor.extra_state_attributes["lesson"]["lessonText"] == "Deutsch"
