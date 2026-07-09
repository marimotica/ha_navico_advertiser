"""Tests for config_flow module."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.navico_advertiser.config_flow import get_interface_ip
from custom_components.navico_advertiser.const import DOMAIN


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
            "listen_ip": "0.0.0.0",
            "listen_port": 2053,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Navico Advertiser"
    assert result["data"]["advertise_ip"] == "172.30.11.54"


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
        user_input={
            "interface": "end0",
            "advertise_ip": "bad",
            "interval": 10,
            "listen_ip": "0.0.0.0",
            "listen_port": 2053,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"advertise_ip": "invalid_ip"}


def test_get_interface_ip_missing() -> None:
    """Test missing interface IP lookup."""
    with patch("socket.socket", side_effect=OSError):
        assert get_interface_ip("definitely_missing") is None
