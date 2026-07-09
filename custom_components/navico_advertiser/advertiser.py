"""UDP multicast relay for Navico MFD browser tile announcements."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from homeassistant.core import HomeAssistant, callback

from .const import (
    DEFAULT_ADVERTISE_INTERVAL,
    DEFAULT_LISTEN_IP,
    DEFAULT_LISTEN_PORT,
    DEFAULT_MULTICAST_GROUP,
    DEFAULT_MULTICAST_PORT,
    DEFAULT_PROXY_PORT,
    DEFAULT_TTL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AdvertiserConfig:
    """Runtime UDP relay configuration."""

    advertise_ip: str
    interface: str = ""
    interval: int = DEFAULT_ADVERTISE_INTERVAL
    listen_ip: str = DEFAULT_LISTEN_IP
    listen_port: int = DEFAULT_LISTEN_PORT
    multicast_group: str = DEFAULT_MULTICAST_GROUP
    multicast_port: int = DEFAULT_MULTICAST_PORT
    proxy_port: int = DEFAULT_PROXY_PORT
    ttl: int = DEFAULT_TTL


def rewrite_announcement(
    payload: dict[str, Any], config: AdvertiserConfig
) -> dict[str, Any]:
    """Rewrite a SignalK Navico announcement for the boat LAN."""
    rewritten = json.loads(json.dumps(payload))
    source_ip = str(rewritten.get("IP") or "")
    rewritten["IP"] = config.advertise_ip
    for key in ("URL", "Icon"):
        if isinstance(rewritten.get(key), str):
            rewritten[key] = rewrite_url(rewritten[key], source_ip, config)
    return rewritten


def rewrite_url(url: str, source_ip: str, config: AdvertiserConfig) -> str:
    """Rewrite one URL from the SignalK container to the advertised host."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return url
    if source_ip and parts.hostname != source_ip:
        return url
    netloc = config.advertise_ip
    if config.proxy_port:
        netloc = f"{netloc}:{config.proxy_port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


class NavicoAdvertiser:
    """Relay SignalK Navico UDP advertisements onto the boat LAN."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: AdvertiserConfig,
    ) -> None:
        """Initialize relay."""
        self.hass = hass
        self.config = config
        self._transport: asyncio.DatagramTransport | None = None
        self._rebroadcast_task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()
        self._announcements: dict[str, bytes] = {}

    @property
    def running(self) -> bool:
        """Return whether the UDP listener is running."""
        return self._transport is not None

    @callback
    def update(self, config: AdvertiserConfig) -> bool:
        """Update runtime configuration. Return true when listener must restart."""
        restart = (
            config.listen_ip != self.config.listen_ip
            or config.listen_port != self.config.listen_port
        )
        self.config = config
        return restart

    async def async_start(self) -> None:
        """Start UDP listener and rebroadcast task."""
        if self.running:
            return
        self._stopped.clear()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.config.listen_ip, self.config.listen_port))
        sock.setblocking(False)
        interface_ips = await self.hass.async_add_executor_job(multicast_interface_ips)
        for interface_ip in interface_ips:
            membership = socket.inet_aton(self.config.multicast_group) + socket.inet_aton(
                interface_ip
            )
            with contextlib.suppress(OSError):
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _NavicoRelayProtocol(self), sock=sock
        )
        self._rebroadcast_task = self.hass.async_create_task(self._async_rebroadcast())
        _LOGGER.info(
            "Listening for Navico announcements on %s:%s",
            self.config.listen_ip,
            self.config.listen_port,
        )

    async def async_stop(self) -> None:
        """Stop UDP listener and rebroadcast task."""
        self._stopped.set()
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        if self._rebroadcast_task is not None:
            self._rebroadcast_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._rebroadcast_task
            self._rebroadcast_task = None

    async def async_restart(self) -> None:
        """Restart UDP listener."""
        await self.async_stop()
        await self.async_start()

    async def async_send_once(self) -> None:
        """Send all cached rewritten advertisements once."""
        for data in list(self._announcements.values()):
            await self.hass.async_add_executor_job(self._send_payload, data)

    async def _async_rebroadcast(self) -> None:
        """Periodically rebroadcast cached rewritten announcements."""
        while not self._stopped.is_set():
            await self.async_send_once()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    self._stopped.wait(), timeout=max(1, self.config.interval)
                )

    async def async_handle_packet(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle one incoming SignalK plugin packet."""
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        if payload.get("IP") == self.config.advertise_ip:
            return
        if "URL" not in payload or "FeatureName" not in payload:
            return
        rewritten = rewrite_announcement(payload, self.config)
        encoded = json.dumps(rewritten, separators=(",", ":")).encode()
        key = str(rewritten.get("FeatureName") or rewritten.get("URL") or addr)
        self._announcements[key] = encoded
        await self.hass.async_add_executor_job(self._send_payload, encoded)

    def _send_payload(self, data: bytes) -> None:
        """Send one rewritten advertisement synchronously."""
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
                sock.sendto(data, (config.multicast_group, config.multicast_port))
        except OSError as err:
            _LOGGER.warning("Failed to send Navico advertisements: %s", err)


class _NavicoRelayProtocol(asyncio.DatagramProtocol):
    """UDP protocol that forwards packets to the relay."""

    def __init__(self, relay: NavicoAdvertiser) -> None:
        """Initialize protocol."""
        self.relay = relay

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle one UDP datagram."""
        self.relay.hass.async_create_task(self.relay.async_handle_packet(data, addr))


def multicast_interface_ips() -> list[str]:
    """Return IPv4 interface addresses to join multicast on."""
    ips = ["0.0.0.0"]
    ips.extend(_linux_interface_ips())
    return list(dict.fromkeys(ips))


def _linux_interface_ips() -> list[str]:
    """Return IPv4 addresses from Linux /proc net data."""
    ips: list[str] = []
    for name in os.listdir("/sys/class/net") if os.path.isdir("/sys/class/net") else []:
        if name == "lo":
            continue
        ip = _interface_ip(name)
        if ip:
            ips.append(ip)
    return ips


def _interface_ip(name: str) -> str | None:
    """Return IPv4 address for an interface name."""
    try:
        import fcntl
        import struct
    except ImportError:
        return None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            data = struct.pack("256s", name[:15].encode())
            result = fcntl.ioctl(sock.fileno(), 0x8915, data)
            return socket.inet_ntoa(result[20:24])
    except OSError:
        return None
