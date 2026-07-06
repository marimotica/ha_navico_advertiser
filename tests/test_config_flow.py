"""Tests for config_flow module."""

from __future__ import annotations

import json
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.navico_advertiser.config_flow import (
    NavicoAdvertiserOptionsFlow,
    default_site,
    get_interface_ip,
    sites_to_json,
    validate_sites_json,
)
from custom_components.navico_advertiser.const import DOMAIN


def test_default_site() -> None:
    """Test default Home Assistant site creation."""
    site = default_site("172.30.11.54")

    assert site["id"] == "home_assistant"
    assert site["name"] == "Home Assistant"
    assert site["url"] == "http://172.30.11.54:8123/"
    assert site["icon"] == "http://172.30.11.54:8123/favicon.ico"


def test_validate_sites_json() -> None:
    """Test site JSON parsing."""
    sites = validate_sites_json(sites_to_json([default_site("172.30.11.54")]))

    assert len(sites) == 1
    assert sites[0]["id"] == "home_assistant"


async def test_config_flow_user_step(hass: HomeAssistant) -> None:
    """Test the user config flow step."""
    with patch(
        "custom_components.navico_advertiser.config_flow.get_default_ip",
        return_value="172.30.11.54",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_config_flow_user_step_creates_entry(hass: HomeAssistant) -> None:
    """Test that submitting the user step creates an entry."""
    with patch(
        "custom_components.navico_advertiser.config_flow.get_default_ip",
        return_value="172.30.11.54",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "interface": "end0",
            "advertise_ip": "172.30.11.54",
            "interval": 10,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Navico Advertiser"
    assert result["data"]["advertise_ip"] == "172.30.11.54"
    assert result["options"]["sites"] == [default_site("172.30.11.54")]


async def test_config_flow_user_step_invalid_ip(hass: HomeAssistant) -> None:
    """Test that invalid IP shows an error."""
    with patch(
        "custom_components.navico_advertiser.config_flow.get_default_ip",
        return_value="172.30.11.54",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"interface": "end0", "advertise_ip": "bad", "interval": 10},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"advertise_ip": "invalid_ip"}


def test_sites_to_json_roundtrip() -> None:
    """Test site JSON serialization roundtrip."""
    raw = sites_to_json([default_site("172.30.11.54")])

    assert json.loads(raw)[0]["id"] == "home_assistant"


def test_get_interface_ip_missing() -> None:
    """Test missing interface IP lookup."""
    with patch("socket.socket", side_effect=OSError):
        assert get_interface_ip("definitely_missing") is None


def test_options_flow_stores_entry_privately() -> None:
    """Test options flow does not assign Home Assistant's read-only property."""
    entry = object()
    flow = NavicoAdvertiserOptionsFlow(entry)  # type: ignore[arg-type]

    assert flow._config_entry is entry
