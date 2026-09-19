"""Tests for Navico Advertiser config entry setup."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.navico_advertiser.const import (
    CONF_ADVERTISE_IP,
    CONF_LISTEN_IP,
    CONF_LISTEN_PORT,
    DOMAIN,
)


@pytest.mark.timeout(10)
async def test_rebroadcast_loop_does_not_block_startup(
    hass: HomeAssistant, socket_enabled: None
) -> None:
    """Test the never-ending rebroadcast loop is not a tracked task.

    A tracked task makes Home Assistant bootstrap wait out its full startup
    timeout; here it would make async_block_till_done hang.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADVERTISE_IP: "127.0.0.1",
            CONF_LISTEN_IP: "127.0.0.1",
            CONF_LISTEN_PORT: 0,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    task = hass.data[DOMAIN][entry.entry_id]["advertiser"]._rebroadcast_task
    assert task is not None
    assert not task.done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert task.done()
