"""Tests for Navico Advertiser services."""

from __future__ import annotations

import pytest

from homeassistant.exceptions import HomeAssistantError

from custom_components.navico_advertiser import site_for_add


def _site(name: str, site_id: str | None = None) -> dict[str, object]:
    """Build service data for a test site."""
    data: dict[str, object] = {
        "name": name,
        "url": f"http://example.test/{name.lower().replace(' ', '-')}/",
        "icon": "http://example.test/icon.png",
    }
    if site_id is not None:
        data["id"] = site_id
    return data


def test_site_for_add_appends_unique_id_when_id_omitted() -> None:
    """Test add_site appends a new site instead of replacing by generated id."""
    sites = [site_for_add(_site("Home Assistant"), [])]

    added = site_for_add(_site("Home Assistant"), sites)

    assert [site["id"] for site in sites] == ["home_assistant", "home_assistant_2"]
    assert added["id"] == "home_assistant_2"


def test_site_for_add_rejects_duplicate_explicit_id() -> None:
    """Test add_site rejects duplicate explicit ids."""
    sites = [site_for_add(_site("Home Assistant", "home_assistant"), [])]

    with pytest.raises(HomeAssistantError, match="Use update_site"):
        site_for_add(_site("Different", "home_assistant"), sites)

    assert len(sites) == 1


def test_site_for_add_allows_unique_explicit_id() -> None:
    """Test add_site appends when an explicit id is unique."""
    sites = [site_for_add(_site("Home Assistant", "home_assistant"), [])]

    site_for_add(_site("Signal K", "signalk"), sites)

    assert [site["id"] for site in sites] == ["home_assistant", "signalk"]
