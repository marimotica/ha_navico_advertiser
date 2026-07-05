"""UDP multicast advertiser for Navico MFD browser tiles."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import socket
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant, callback

from .const import (
    DEFAULT_ADVERTISE_INTERVAL,
    DEFAULT_MULTICAST_GROUP,
    DEFAULT_MULTICAST_PORT,
    DEFAULT_SOURCE,
    DEFAULT_TTL,
    SITE_DESCRIPTION,
    SITE_ICON,
    SITE_LANGUAGE,
    SITE_NAME,
    SITE_ONLY_SHOW_ON_CLIENT_IP,
    SITE_PROGRESS_BAR,
    SITE_SOURCE,
    SITE_URL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AdvertiserConfig:
    """Runtime advertiser configuration."""

    advertise_ip: str
    interface: str = ""
    interval: int = DEFAULT_ADVERTISE_INTERVAL
    multicast_group: str = DEFAULT_MULTICAST_GROUP
    multicast_port: int = DEFAULT_MULTICAST_PORT
    ttl: int = DEFAULT_TTL


def build_announcement(advertise_ip: str, site: dict[str, Any]) -> str:
    """Build one Navico MFD advertisement JSON payload."""
    name = str(site[SITE_NAME])
    language = str(site.get(SITE_LANGUAGE) or "en")
    source = str(site.get(SITE_SOURCE) or DEFAULT_SOURCE)
    description = str(site.get(SITE_DESCRIPTION) or "")
    progress_bar = bool(site.get(SITE_PROGRESS_BAR, True))
    only_show = site.get(SITE_ONLY_SHOW_ON_CLIENT_IP, True)

    payload = {
        "Version": "1",
        "Source": source,
        "IP": advertise_ip,
        "FeatureName": name,
        "Text": [
            {
                "Language": language,
                "Name": name,
                "Description": description,
            }
        ],
        "Icon": str(site[SITE_ICON]),
        "URL": str(site[SITE_URL]),
        "OnlyShowOnClientIP": "true" if only_show else "false",
        "BrowserPanel": {
            "Enable": True,
            "ProgressBarEnable": progress_bar,
            "MenuText": [{"Language": language, "Name": name}],
        },
    }
    return json.dumps(payload, separators=(",", ":"))


class NavicoAdvertiser:
    """Send Navico MFD UDP multicast advertisements in the background."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: AdvertiserConfig,
        sites: list[dict[str, Any]],
    ) -> None:
        """Initialize advertiser."""
        self.hass = hass
        self.config = config
        self.sites = sites
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()

    @property
    def running(self) -> bool:
        """Return whether the background task is running."""
        return self._task is not None and not self._task.done()

    @callback
    def update(self, config: AdvertiserConfig, sites: list[dict[str, Any]]) -> None:
        """Update runtime configuration used by the next send cycle."""
        self.config = config
        self.sites = sites

    async def async_start(self) -> None:
        """Start background advertisement task."""
        if self.running:
            return
        self._stopped.clear()
        self._task = self.hass.async_create_task(self._async_run())

    async def async_stop(self) -> None:
        """Stop background advertisement task."""
        self._stopped.set()
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def async_send_once(self) -> None:
        """Send all currently configured site advertisements once."""
        await self.hass.async_add_executor_job(self._send_once)

    async def _async_run(self) -> None:
        """Run advertisement loop."""
        while not self._stopped.is_set():
            await self.async_send_once()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    self._stopped.wait(), timeout=max(1, self.config.interval)
                )

    def _send_once(self) -> None:
        """Send all advertisements synchronously from an executor."""
        if not self.sites:
            return

        config = self.config
        try:
            with socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
            ) as sock:
                if config.interface:
                    try:
                        sock.setsockopt(
                            socket.SOL_SOCKET,
                            getattr(socket, "SO_BINDTODEVICE", 25),
                            config.interface.encode() + b"\0",
                        )
                    except OSError as err:
                        _LOGGER.warning(
                            "Failed to bind Navico advertiser to interface %s: %s",
                            config.interface,
                            err,
                        )
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, config.ttl)
                sock.setsockopt(
                    socket.IPPROTO_IP,
                    socket.IP_MULTICAST_IF,
                    socket.inet_aton(config.advertise_ip),
                )
                sock.bind((config.advertise_ip, 0))
                for site in self.sites:
                    data = build_announcement(config.advertise_ip, site).encode()
                    sock.sendto(data, (config.multicast_group, config.multicast_port))
        except OSError as err:
            _LOGGER.warning("Failed to send Navico advertisements: %s", err)
