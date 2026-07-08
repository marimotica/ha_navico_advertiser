"""Config flow for Navico Advertiser."""

from __future__ import annotations

import ipaddress
import socket
import struct
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

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
)


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
        if user_input is not None:
            try:
                data = _validated_config(user_input)
            except vol.Invalid:
                errors[CONF_ADVERTISE_IP] = "invalid_ip"
            else:
                return self.async_create_entry(title="Navico Advertiser", data=data)

        default_ip = (
            str(user_input.get(CONF_ADVERTISE_IP, ""))
            if user_input is not None
            else get_default_ip()
        )
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(default_ip),
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
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = _validated_config(user_input)
            except vol.Invalid:
                errors[CONF_ADVERTISE_IP] = "invalid_ip"
            else:
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=data
                )
                return self.async_create_entry(title="", data={})

        data = self._config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(data.get(CONF_ADVERTISE_IP, get_default_ip()), data),
            errors=errors,
        )


def _validated_config(user_input: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize config entry data."""
    return {
        CONF_INTERFACE: str(user_input.get(CONF_INTERFACE, "")).strip(),
        CONF_ADVERTISE_IP: validate_ip(user_input[CONF_ADVERTISE_IP]),
        CONF_INTERVAL: int(user_input.get(CONF_INTERVAL, DEFAULT_ADVERTISE_INTERVAL)),
        CONF_LISTEN_IP: validate_ip(user_input.get(CONF_LISTEN_IP, DEFAULT_LISTEN_IP)),
        CONF_LISTEN_PORT: int(user_input.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT)),
        CONF_PROXY_PORT: int(user_input.get(CONF_PROXY_PORT, DEFAULT_PROXY_PORT)),
    }


def _schema(default_ip: str, data: dict[str, Any] | None = None) -> vol.Schema:
    """Return config/options schema."""
    data = data or {}
    return vol.Schema(
        {
            vol.Optional(CONF_INTERFACE, default=data.get(CONF_INTERFACE, "end0")): str,
            vol.Required(
                CONF_ADVERTISE_IP, default=data.get(CONF_ADVERTISE_IP, default_ip)
            ): str,
            vol.Required(
                CONF_PROXY_PORT, default=data.get(CONF_PROXY_PORT, DEFAULT_PROXY_PORT)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required(
                CONF_INTERVAL,
                default=data.get(CONF_INTERVAL, DEFAULT_ADVERTISE_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=3600)),
            vol.Required(
                CONF_LISTEN_IP, default=data.get(CONF_LISTEN_IP, DEFAULT_LISTEN_IP)
            ): str,
            vol.Required(
                CONF_LISTEN_PORT,
                default=data.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        }
    )
