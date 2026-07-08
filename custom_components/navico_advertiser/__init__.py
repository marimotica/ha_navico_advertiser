"""Navico Advertiser integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse

from .advertiser import AdvertiserConfig, NavicoAdvertiser
from .const import (
    CONF_ADVERTISE_IP,
    CONF_INTERFACE,
    CONF_INTERVAL,
    CONF_LISTEN_IP,
    CONF_LISTEN_PORT,
    CONF_PROXY_PORT,
    DEFAULT_ADVERTISE_INTERVAL,
    DEFAULT_LISTEN_IP,
    DEFAULT_LISTEN_PORT,
    DEFAULT_PROXY_PORT,
    DOMAIN,
    SERVICE_EXPORT_STATE,
    SERVICE_RELOAD,
    SERVICE_SEND_NOW,
)

NavicoConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: NavicoConfigEntry) -> bool:
    """Set up Navico Advertiser from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    advertiser = NavicoAdvertiser(hass, _entry_config(entry))
    hass.data[DOMAIN][entry.entry_id] = {"advertiser": advertiser}
    await advertiser.async_start()

    async def async_stop_runtime(*_: Any) -> None:
        """Stop runtime tasks when Home Assistant is shutting down."""
        await advertiser.async_stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_runtime)
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NavicoConfigEntry) -> bool:
    """Unload Navico Advertiser config entry."""
    entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if entry_data is not None:
        await entry_data["advertiser"].async_stop()
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_RELOAD)
        hass.services.async_remove(DOMAIN, SERVICE_SEND_NOW)
        hass.services.async_remove(DOMAIN, SERVICE_EXPORT_STATE)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: NavicoConfigEntry) -> None:
    """Apply updated options without restarting Home Assistant."""
    advertiser: NavicoAdvertiser = hass.data[DOMAIN][entry.entry_id]["advertiser"]
    if advertiser.update(_entry_config(entry)):
        await advertiser.async_restart()
    await advertiser.async_send_once()


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_RELOAD):
        return

    async def async_reload(call: ServiceCall) -> None:
        entry = _get_single_entry(hass)
        await _async_update_listener(hass, entry)

    async def async_send_now(call: ServiceCall) -> None:
        entry = _get_single_entry(hass)
        await hass.data[DOMAIN][entry.entry_id]["advertiser"].async_send_once()

    async def async_export_state(call: ServiceCall) -> dict[str, Any]:
        entry = _get_single_entry(hass)
        advertiser: NavicoAdvertiser = hass.data[DOMAIN][entry.entry_id]["advertiser"]
        return {
            "config": _entry_config(entry).__dict__,
            "cached_announcements": len(advertiser._announcements),
        }

    hass.services.async_register(DOMAIN, SERVICE_RELOAD, async_reload)
    hass.services.async_register(DOMAIN, SERVICE_SEND_NOW, async_send_now)
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_STATE,
        async_export_state,
        supports_response=SupportsResponse.ONLY,
    )


def _get_single_entry(hass: HomeAssistant) -> NavicoConfigEntry:
    """Return the single configured Navico Advertiser entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise RuntimeError("Navico Advertiser is not configured")
    return entries[0]


def _entry_config(entry: NavicoConfigEntry) -> AdvertiserConfig:
    """Build runtime relay config from entry data."""
    data = entry.data
    return AdvertiserConfig(
        advertise_ip=data[CONF_ADVERTISE_IP],
        interface=data.get(CONF_INTERFACE, ""),
        interval=int(data.get(CONF_INTERVAL, DEFAULT_ADVERTISE_INTERVAL)),
        listen_ip=data.get(CONF_LISTEN_IP, DEFAULT_LISTEN_IP),
        listen_port=int(data.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT)),
        proxy_port=int(data.get(CONF_PROXY_PORT, DEFAULT_PROXY_PORT)),
    )
