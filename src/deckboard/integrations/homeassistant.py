"""Home Assistant capability mapping helpers for optional deckboard integrations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntityProfile:
    """Capability-first view of a Home Assistant entity domain."""

    domain: str
    supports_toggle: bool = False
    supports_range: bool = False
    supports_mode: bool = False
    supports_sensor_value: bool = False
    supports_transport: bool = False


_DOMAIN_PROFILES = {
    "automation": EntityProfile("automation", supports_toggle=True),
    "button": EntityProfile("button"),
    "climate": EntityProfile(
        "climate",
        supports_toggle=True,
        supports_range=True,
        supports_mode=True,
        supports_sensor_value=True,
    ),
    "cover": EntityProfile("cover", supports_toggle=True, supports_range=True),
    "fan": EntityProfile(
        "fan",
        supports_toggle=True,
        supports_range=True,
        supports_mode=True,
    ),
    "input_boolean": EntityProfile("input_boolean", supports_toggle=True),
    "input_number": EntityProfile("input_number", supports_range=True),
    "light": EntityProfile(
        "light",
        supports_toggle=True,
        supports_range=True,
        supports_mode=True,
    ),
    "media_player": EntityProfile(
        "media_player",
        supports_toggle=True,
        supports_range=True,
        supports_mode=True,
        supports_transport=True,
    ),
    "number": EntityProfile("number", supports_range=True),
    "scene": EntityProfile("scene"),
    "select": EntityProfile("select", supports_mode=True),
    "sensor": EntityProfile("sensor", supports_sensor_value=True),
    "switch": EntityProfile("switch", supports_toggle=True),
}


def capability_profile(domain: str) -> EntityProfile:
    """Return a capability-first profile for a Home Assistant entity domain."""
    return _DOMAIN_PROFILES.get(domain, EntityProfile(domain))


__all__ = ["EntityProfile", "capability_profile"]
