# WebUntis for Home Assistant

[![Open in Home Assistant](https://img.shields.io/badge/Open%20in%20Home%20Assistant-%2300A6FF?style=for-the-badge&logo=homeassistant)](http://homeassistant.local:8123)

A custom Home Assistant integration for WebUntis that exposes timetable data, lesson changes, and useful automation-friendly sensor states directly in your HA dashboard.

> Replace `homeassistant.local` with your actual Home Assistant hostname or IP if needed.

## Features

- UI-based config flow
- WebUntis authentication via session + JWT handling
- Timetable polling with a coordinator
- Calendar entity for upcoming lessons
- Rich sensor data for dashboards and automations
- Binary sensors for school-day context

## Included sensors

### Core timetable sensors

- `sensor.<name>_lessons_today`  
  Returns: integer, for example `6`  
  Meaning: number of lessons scheduled for today.

- `sensor.<name>_changed_lessons_today`  
  Returns: integer, for example `2`  
  Meaning: number of lessons with a non-regular status today.

- `sensor.<name>_next_lesson`  
  Returns: string, for example `Mathe` or `Deutsch`  
  Meaning: title/name of the next upcoming lesson.

- `sensor.<name>_current_lesson`  
  Returns: string, for example `Biologie`  
  Meaning: title/name of the currently active lesson, if one is currently running.

- `sensor.<name>_changed_lesson`  
  Returns: string, for example `Englisch`  
  Meaning: first changed lesson of the current timetable day.

- `sensor.<name>_next_changed_lesson`  
  Returns: string, for example `Physik`  
  Meaning: next upcoming changed lesson, ordered by lesson time.

### Status and time sensors

- `sensor.<name>_next_lesson_status`  
  Returns: string, for example `REGULAR`, `CANCELLED`, `SUBSTITUTION`  
  Meaning: status of the next lesson.

- `sensor.<name>_current_lesson_status`  
  Returns: string, for example `REGULAR` or `CANCELLED`  
  Meaning: status of the currently active lesson.

- `sensor.<name>_changed_lesson_status`  
  Returns: string, for example `CANCELLED`  
  Meaning: status of the next/first changed lesson.

- `sensor.<name>_next_lesson_start`  
  Returns: time string, for example `08:00`  
  Meaning: start time of the next upcoming lesson.

- `sensor.<name>_next_lesson_end`  
  Returns: time string, for example `08:45`  
  Meaning: end time of the next upcoming lesson.

- `sensor.<name>_current_schoolyear`  
  Returns: string, for example `2026/2027`  
  Meaning: current school year label from WebUntis.

### Binary sensors

- `binary_sensor.<name>_is_holiday`  
  Returns: `on` / `off`  
  Meaning: `on` if today is a school holiday.

- `binary_sensor.<name>_is_weekend`  
  Returns: `on` / `off`  
  Meaning: `on` if today is Saturday or Sunday.

### Calendar

- `calendar.<name>_timetable`  
  Returns: calendar events with summary, start, end, and description  
  Meaning: upcoming timetable entries rendered as Home Assistant calendar events.

## Attribute payloads for automation

The lesson-based sensors also expose additional attributes for automations and templates. These are available via the entity state attributes, not as separate sensors.

Examples:

- `status` — lesson status such as `REGULAR`, `CANCELLED`, `SUBSTITUTION`
- `start` — lesson start time such as `08:00`
- `end` — lesson end time such as `08:45`
- `substitution_text` — text from WebUntis in case of substitution
- `lesson_info` — additional lesson information
- `room` — room or rooms assigned to the lesson
- `teacher` — teacher or teachers assigned to the lesson
- `lesson_text` — lesson title/name

Example template:

```yaml
{{ state_attr('sensor.my_webuntis_next_lesson', 'status') }}
{{ state_attr('sensor.my_webuntis_next_lesson', 'substitution_text') }}
```

## Installation

1. Copy the `custom_components/webuntis` folder into your Home Assistant config directory under `custom_components/`.
2. Restart Home Assistant.
3. Open Home Assistant and go to **Settings -> Devices & Services -> Add Integration**.
4. Search for **WebUntis**.
5. Fill in the required values:
   - School
   - Username
   - Password
   - Base URL, for example `example.webuntis.com`
   - Client identity (optional, defaults to `HomeAssistant`)
   - Timetable scope: `own` or `class`
   - Class ID for class-scoped timetables
   - Update interval in minutes

## Multiple entries

You can add multiple WebUntis entries from the UI. This is useful if:

- you have different users or classes
- you want separate profiles for different groups
- you want a dedicated timetable for one student or one class

## Options

Open an integration entry and click **Configure** to update:

- client identity
- timetable scope
- class ID
- update interval

## Useful Home Assistant workflows

Below are ready-to-use patterns for automations built around the added lesson sensors.

### 1) Notify when a changed lesson is coming up

```yaml
alias: WebUntis changed lesson notification
triggers:
  - trigger: state
    entity_id:
      - sensor.my_webuntis_next_changed_lesson
    to: "not_none"
conditions:
  - condition: template
    value_template: "{{ states('sensor.my_webuntis_next_changed_lesson') not in ['unknown', 'none', 'unavailable'] }}"
actions:
  - service: notify.mobile_app_phone
    data:
      message: >-
        Die nächste geänderte Stunde ist {{ states('sensor.my_webuntis_next_changed_lesson') }}.
```

### 2) Notify when the current lesson is changed

```yaml
alias: WebUntis current lesson substitution alert
triggers:
  - trigger: state
    entity_id:
      - sensor.my_webuntis_current_lesson_status
    not_to:
      - "unknown"
      - "REGULAR"
actions:
  - service: notify.mobile_app_phone
    data:
      message: >-
        Achtung: {{ states('sensor.my_webuntis_current_lesson') }} ist geändert.
        Status: {{ states('sensor.my_webuntis_current_lesson_status') }}
```

### 3) Start a routine before the next lesson begins

```yaml
alias: WebUntis prepare for next lesson
triggers:
  - trigger: state
    entity_id:
      - sensor.my_webuntis_next_lesson_start
    to: ~
conditions:
  - condition: template
    value_template: "{{ states('sensor.my_webuntis_next_lesson_start') not in ['unknown', 'none', 'unavailable'] }}"
actions:
  - service: script.turn_on
    target:
      entity_id: script.prepare_school_day
```

### 4) Turn on a "school mode" when class starts

```yaml
alias: WebUntis school mode ON
triggers:
  - trigger: state
    entity_id:
      - sensor.my_webuntis_current_lesson
    from: "unknown"
    to: ~
conditions:
  - condition: template
    value_template: "{{ states('sensor.my_webuntis_current_lesson') not in ['unknown', 'none', 'unavailable'] }}"
actions:
  - service: switch.turn_on
    target:
      entity_id: switch.school_mode
```

### 5) Pause notifications on holidays and weekends

```yaml
alias: Skip school notifications on holiday or weekend
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.my_webuntis_is_holiday
      - binary_sensor.my_webuntis_is_weekend
actions:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ is_state('binary_sensor.my_webuntis_is_holiday', 'on') or is_state('binary_sensor.my_webuntis_is_weekend', 'on') }}"
        sequence:
          - service: input_boolean.turn_off
            target:
              entity_id: input_boolean.school_notifications_enabled
```

## Example dashboard cards

A compact dashboard setup could look like this:

- Entities card for:
  - next lesson
  - current lesson
  - current lesson status
  - next changed lesson
  - lessons today
- Markdown card with a note like:
  - "Heute: 6 Stunden | 2 Änderungen"
- Calendar card for the WebUntis timetable

## Notes

- This integration reads timetable data and calendar metadata from WebUntis.
- It expects a valid student or class timetable view from your WebUntis instance.
- If your WebUntis host is not reachable from Home Assistant, check network access, proxy settings, and certificates.

## Development notes

- The integration uses a coordinator for periodic updates.
- The `sensor.py` platform exposes automation-friendly derived values in addition to the raw timetable data.
- The calendar entity reads the current timetable and maps lesson entries to Home Assistant calendar events.
