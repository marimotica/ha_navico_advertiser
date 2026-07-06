"""Tests for Navico Advertiser services."""

from __future__ import annotations

import pytest

from homeassistant.exceptions import HomeAssistantError

from custom_components.navico_advertiser import (
    _entry_sites,
    remove_site_by_id,
    site_for_add,
)


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


def test_remove_site_by_id_removes_one_matching_site() -> None:
    """Test remove_site removes only one entry even if ids are duplicated."""
    sites = [
        {"id": "duplicate", "name": "First"},
        {"id": "duplicate", "name": "Second"},
        {"id": "other", "name": "Other"},
    ]

    remaining = remove_site_by_id(sites, "duplicate")

    assert remaining == [
        {"id": "duplicate", "name": "Second"},
        {"id": "other", "name": "Other"},
    ]


def test_remove_site_by_id_rejects_missing_site() -> None:
    """Test remove_site errors when the requested id is absent."""
    with pytest.raises(HomeAssistantError, match="Unknown site id"):
        remove_site_by_id([{"id": "home_assistant"}], "missing")


def test_entry_sites_falls_back_to_default_site() -> None:
    """Test old entries without stored sites still advertise Home Assistant."""

    class Entry:
        data = {"advertise_ip": "172.30.11.54"}
        options = {}

    assert _entry_sites(Entry())[0]["id"] == "home_assistant"


def test_entry_sites_preserves_explicit_empty_sites() -> None:
    """Test explicitly empty sites stay empty."""

    class Entry:
        data = {"advertise_ip": "172.30.11.54"}
        options = {"sites": []}

    assert _entry_sites(Entry()) == []
