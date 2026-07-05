"""Tests for Navico advertisement payloads."""

from __future__ import annotations

import json

from custom_components.navico_advertiser.advertiser import build_announcement
from custom_components.navico_advertiser.config_flow import default_site, normalize_site


def test_build_announcement() -> None:
    """Test building a Navico announcement payload."""
    payload = json.loads(build_announcement("172.30.11.54", default_site("172.30.11.54")))

    assert payload["Version"] == "1"
    assert payload["Source"] == "Home Assistant"
    assert payload["IP"] == "172.30.11.54"
    assert payload["FeatureName"] == "Home Assistant"
    assert payload["URL"] == "http://172.30.11.54:8123/"
    assert payload["Icon"] == "http://172.30.11.54:8123/favicon.ico"
    assert payload["OnlyShowOnClientIP"] == "true"
    assert payload["BrowserPanel"]["Enable"] is True


def test_normalize_site_generates_id() -> None:
    """Test site normalization."""
    site = normalize_site(
        {
            "name": "Home Assistant Boat",
            "url": "http://172.30.11.54:8123/",
            "icon": "http://172.30.11.54:8123/favicon.ico",
        }
    )

    assert site["id"] == "home_assistant_boat"
    assert site["language"] == "en"
    assert site["progress_bar"] is True
