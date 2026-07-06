"""Navico Advertiser integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .advertiser import AdvertiserConfig, NavicoAdvertiser
from .config_flow import normalize_site, sites_to_json
from .const import (
    CONF_ADVERTISE_IP,
    CONF_INTERFACE,
    CONF_INTERVAL,
    CONF_SITES,
    DOMAIN,
    SERVICE_ADD_SITE,
    SERVICE_EXPORT_STATE,
    SERVICE_RELOAD,
    SERVICE_REMOVE_SITE,
    SERVICE_SEND_NOW,
    SERVICE_UPDATE_SITE,
    SITE_DESCRIPTION,
    SITE_ICON,
    SITE_ID,
    SITE_LANGUAGE,
    SITE_NAME,
    SITE_ONLY_SHOW_ON_CLIENT_IP,
    SITE_PROGRESS_BAR,
    SITE_SOURCE,
    SITE_URL,
)

_LOGGER = logging.getLogger(__name__)

NavicoConfigEntry = ConfigEntry


ADD_SITE_SCHEMA = vol.Schema(
    {
        vol.Optional(SITE_ID): cv.string,
        vol.Required(SITE_NAME): cv.string,
        vol.Required(SITE_URL): cv.url,
        vol.Required(SITE_ICON): cv.url,
        vol.Optional(SITE_DESCRIPTION, default=""): cv.string,
        vol.Optional(SITE_LANGUAGE, default="en"): cv.string,
        vol.Optional(SITE_SOURCE): cv.string,
        vol.Optional(SITE_PROGRESS_BAR, default=True): cv.boolean,
        vol.Optional(SITE_ONLY_SHOW_ON_CLIENT_IP, default=True): cv.boolean,
    }
)

UPDATE_SITE_SCHEMA = vol.Schema(
    {
        vol.Required(SITE_ID): cv.string,
        vol.Required(SITE_NAME): cv.string,
        vol.Required(SITE_URL): cv.url,
        vol.Required(SITE_ICON): cv.url,
        vol.Optional(SITE_DESCRIPTION, default=""): cv.string,
        vol.Optional(SITE_LANGUAGE, default="en"): cv.string,
        vol.Optional(SITE_SOURCE): cv.string,
        vol.Optional(SITE_PROGRESS_BAR, default=True): cv.boolean,
        vol.Optional(SITE_ONLY_SHOW_ON_CLIENT_IP, default=True): cv.boolean,
    }
)

REMOVE_SITE_SCHEMA = vol.Schema({vol.Required(SITE_ID): cv.string})


async def async_setup_entry(hass: HomeAssistant, entry: NavicoConfigEntry) -> bool:
    """Set up Navico Advertiser from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    advertiser = NavicoAdvertiser(hass, _entry_config(entry), _entry_sites(entry))
    hass.data[DOMAIN][entry.entry_id] = {"advertiser": advertiser}
    await advertiser.async_start()

    async def async_stop_advertiser(*_: Any) -> None:
        """Stop the advertiser when Home Assistant is shutting down."""
        await advertiser.async_stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_advertiser)
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
        hass.services.async_remove(DOMAIN, SERVICE_ADD_SITE)
        hass.services.async_remove(DOMAIN, SERVICE_UPDATE_SITE)
        hass.services.async_remove(DOMAIN, SERVICE_REMOVE_SITE)
        hass.services.async_remove(DOMAIN, SERVICE_RELOAD)
        hass.services.async_remove(DOMAIN, SERVICE_SEND_NOW)
        hass.services.async_remove(DOMAIN, SERVICE_EXPORT_STATE)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: NavicoConfigEntry) -> None:
    """Apply updated options without restarting Home Assistant."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    advertiser: NavicoAdvertiser = entry_data["advertiser"]
    advertiser.update(_entry_config(entry), _entry_sites(entry))
    await advertiser.async_send_once()


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_SITE):
        return

    async def async_add_site(call: ServiceCall) -> None:
        entry = _get_single_entry(hass)
        sites = _entry_sites(entry)
        site = normalize_site(dict(call.data))
        sites = [item for item in sites if item[SITE_ID] != site[SITE_ID]] + [site]
        _update_sites(hass, entry, sites)

    async def async_update_site(call: ServiceCall) -> None:
        entry = _get_single_entry(hass)
        sites = _entry_sites(entry)
        site = normalize_site(dict(call.data))
        if not any(item[SITE_ID] == site[SITE_ID] for item in sites):
            raise HomeAssistantError(f"Unknown site id: {site[SITE_ID]}")
        sites = [site if item[SITE_ID] == site[SITE_ID] else item for item in sites]
        _update_sites(hass, entry, sites)

    async def async_remove_site(call: ServiceCall) -> None:
        entry = _get_single_entry(hass)
        site_id = call.data[SITE_ID]
        sites = [site for site in _entry_sites(entry) if site[SITE_ID] != site_id]
        _update_sites(hass, entry, sites)

    async def async_reload(call: ServiceCall) -> None:
        entry = _get_single_entry(hass)
        await _async_update_listener(hass, entry)

    async def async_send_now(call: ServiceCall) -> None:
        entry = _get_single_entry(hass)
        await hass.data[DOMAIN][entry.entry_id]["advertiser"].async_send_once()

    async def async_export_state(call: ServiceCall) -> dict[str, Any]:
        entry = _get_single_entry(hass)
        return {
            "interface": entry.data.get(CONF_INTERFACE, ""),
            "advertise_ip": entry.data[CONF_ADVERTISE_IP],
            "interval": entry.data[CONF_INTERVAL],
            "sites": _entry_sites(entry),
        }

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_SITE, async_add_site, schema=ADD_SITE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_SITE, async_update_site, schema=UPDATE_SITE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_SITE, async_remove_site, schema=REMOVE_SITE_SCHEMA
    )
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
        raise vol.Invalid("Navico Advertiser is not configured")
    return entries[0]


def _entry_config(entry: NavicoConfigEntry) -> AdvertiserConfig:
    """Build runtime advertiser config from entry data."""
    return AdvertiserConfig(
        advertise_ip=entry.data[CONF_ADVERTISE_IP],
        interface=entry.data.get(CONF_INTERFACE, ""),
        interval=int(entry.data.get(CONF_INTERVAL, 10)),
    )


def _entry_sites(entry: NavicoConfigEntry) -> list[dict[str, Any]]:
    """Return configured advertised sites."""
    return list(entry.options.get(CONF_SITES, entry.data.get(CONF_SITES, [])))


def _update_sites(
    hass: HomeAssistant, entry: NavicoConfigEntry, sites: list[dict[str, Any]]
) -> None:
    """Persist updated site list and notify the running advertiser."""
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_SITES: sites}
    )
    _LOGGER.debug("Updated Navico advertised sites: %s", sites_to_json(sites))
