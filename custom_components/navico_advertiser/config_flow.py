"""Config flow for Navico Advertiser."""

from __future__ import annotations

import ipaddress
import json
import socket
import struct
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_ADVERTISE_IP,
    CONF_INTERFACE,
    CONF_INTERVAL,
    CONF_SITES,
    DEFAULT_ADVERTISE_INTERVAL,
    DOMAIN,
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


def default_site(advertise_ip: str) -> dict[str, Any]:
    """Return the default Home Assistant advertisement site."""
    base_url = f"http://{advertise_ip}:8123/"
    return normalize_site(
        {
            SITE_ID: "home_assistant",
            SITE_NAME: "Home Assistant",
            SITE_DESCRIPTION: "Home Assistant on HAOS",
            SITE_URL: base_url,
            SITE_ICON: f"{base_url}favicon.ico",
            SITE_LANGUAGE: "en",
            SITE_SOURCE: "Home Assistant",
            SITE_PROGRESS_BAR: True,
            SITE_ONLY_SHOW_ON_CLIENT_IP: True,
        }
    )


def normalize_site(site: dict[str, Any]) -> dict[str, Any]:
    """Normalize one advertised site definition."""
    name = str(site.get(SITE_NAME, "")).strip()
    url = str(site.get(SITE_URL, site.get(CONF_URL, ""))).strip()
    icon = str(site.get(SITE_ICON, "")).strip()
    site_id = str(site.get(SITE_ID) or _slugify(name)).strip()
    return {
        SITE_ID: site_id,
        SITE_NAME: name,
        SITE_DESCRIPTION: str(site.get(SITE_DESCRIPTION, "")).strip(),
        SITE_URL: url,
        SITE_ICON: icon,
        SITE_LANGUAGE: str(site.get(SITE_LANGUAGE) or "en").strip() or "en",
        SITE_SOURCE: str(site.get(SITE_SOURCE) or "Home Assistant").strip(),
        SITE_PROGRESS_BAR: bool(site.get(SITE_PROGRESS_BAR, True)),
        SITE_ONLY_SHOW_ON_CLIENT_IP: bool(site.get(SITE_ONLY_SHOW_ON_CLIENT_IP, True)),
    }


def validate_sites_json(value: str) -> list[dict[str, Any]]:
    """Parse and validate advertised sites JSON."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as err:
        raise vol.Invalid("invalid_json") from err
    if not isinstance(parsed, list):
        raise vol.Invalid("sites_must_be_list")
    sites = [normalize_site(item) for item in parsed]
    seen: set[str] = set()
    for site in sites:
        if not site[SITE_ID]:
            raise vol.Invalid("site_id_required")
        if not site[SITE_NAME] or not site[SITE_URL] or not site[SITE_ICON]:
            raise vol.Invalid("site_required_fields")
        if site[SITE_ID] in seen:
            raise vol.Invalid("duplicate_site_id")
        seen.add(site[SITE_ID])
    return sites


def sites_to_json(sites: list[dict[str, Any]]) -> str:
    """Serialize sites for the options flow text editor."""
    return json.dumps(sites, indent=2, sort_keys=True)


def validate_ip(value: str) -> str:
    """Validate an IPv4 address string."""
    try:
        ip = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as err:
        raise vol.Invalid("invalid_ip") from err
    return str(ip)


def get_default_ip() -> str:
    """Best-effort default outbound IPv4 address detection."""
    for interface in ("end0", "eth0"):
        if interface_ip := get_interface_ip(interface):
            return interface_ip
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
        except OSError:
            return "127.0.0.1"


def get_interface_ip(interface: str) -> str | None:
    """Return the IPv4 address assigned to a Linux network interface."""
    try:
        import fcntl
    except ImportError:
        return None

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            data = struct.pack("256s", interface[:15].encode())
            result = fcntl.ioctl(sock.fileno(), 0x8915, data)
            return socket.inet_ntoa(result[20:24])
    except OSError:
        return None


class NavicoAdvertiserConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Navico Advertiser."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        default_ip = get_default_ip()

        if user_input is not None:
            try:
                advertise_ip = validate_ip(user_input[CONF_ADVERTISE_IP])
            except vol.Invalid:
                errors[CONF_ADVERTISE_IP] = "invalid_ip"
            else:
                interval = max(1, int(user_input[CONF_INTERVAL]))
                return self.async_create_entry(
                    title="Navico Advertiser",
                    data={
                        CONF_INTERFACE: str(user_input.get(CONF_INTERFACE, "")).strip(),
                        CONF_ADVERTISE_IP: advertise_ip,
                        CONF_INTERVAL: interval,
                    },
                    options={CONF_SITES: [default_site(advertise_ip)]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_INTERFACE, default="end0"): str,
                    vol.Required(CONF_ADVERTISE_IP, default=default_ip): str,
                    vol.Required(
                        CONF_INTERVAL, default=DEFAULT_ADVERTISE_INTERVAL
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=3600)),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NavicoAdvertiserOptionsFlow:
        """Get the options flow for this handler."""
        return NavicoAdvertiserOptionsFlow(config_entry)


class NavicoAdvertiserOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Navico Advertiser."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options and advertised sites."""
        errors: dict[str, str] = {}
        current_sites = self.config_entry.options.get(
            CONF_SITES, self.config_entry.data.get(CONF_SITES, [])
        )

        if user_input is not None:
            try:
                advertise_ip = validate_ip(user_input[CONF_ADVERTISE_IP])
                sites = validate_sites_json(user_input[CONF_SITES])
            except vol.Invalid as err:
                reason = str(err) or "invalid_options"
                if reason == "invalid_ip":
                    errors[CONF_ADVERTISE_IP] = reason
                else:
                    errors[CONF_SITES] = reason
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_INTERFACE: str(user_input.get(CONF_INTERFACE, "")).strip(),
                        CONF_ADVERTISE_IP: advertise_ip,
                        CONF_INTERVAL: max(1, int(user_input[CONF_INTERVAL])),
                    },
                    options={CONF_SITES: sites},
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INTERFACE,
                        default=self.config_entry.data.get(CONF_INTERFACE, ""),
                    ): str,
                    vol.Required(
                        CONF_ADVERTISE_IP,
                        default=self.config_entry.data[CONF_ADVERTISE_IP],
                    ): str,
                    vol.Required(
                        CONF_INTERVAL,
                        default=self.config_entry.data.get(
                            CONF_INTERVAL, DEFAULT_ADVERTISE_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=3600)),
                    vol.Required(
                        CONF_SITES, default=sites_to_json(current_sites)
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                }
            ),
            errors=errors,
        )


def _slugify(value: str) -> str:
    """Create a stable ASCII slug from a label."""
    slug = "".join(char.lower() if char.isalnum() else "_" for char in value)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")
