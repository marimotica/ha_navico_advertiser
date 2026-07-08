"""Tests for Navico UDP relay helpers."""

from __future__ import annotations

from custom_components.navico_advertiser.advertiser import (
    AdvertiserConfig,
    rewrite_announcement,
    rewrite_url,
)


def test_rewrite_url_replaces_source_ip_and_port() -> None:
    """Test URL rewriting from SignalK container to advertised host."""
    config = AdvertiserConfig(advertise_ip="172.30.11.54", proxy_port=8080)

    assert rewrite_url("http://172.30.33.3:8080/app/", "172.30.33.3", config) == (
        "http://172.30.11.54:8080/app/"
    )


def test_rewrite_url_keeps_other_hosts() -> None:
    """Test unrelated URLs are left untouched."""
    config = AdvertiserConfig(advertise_ip="172.30.11.54", proxy_port=8080)

    assert rewrite_url("http://example.test/icon.png", "172.30.33.3", config) == (
        "http://example.test/icon.png"
    )


def test_rewrite_announcement_rewrites_ip_url_and_icon() -> None:
    """Test announcement payload rewriting."""
    payload = {
        "Version": "1",
        "Source": "signalk-navico-embedder",
        "IP": "172.30.33.3",
        "FeatureName": "Anchor Alarm",
        "URL": "http://172.30.33.3:8080/hoekens-anchor-alarm/",
        "Icon": "http://172.30.33.3:8080/hoekens-anchor-alarm/anchoralarm.png",
    }

    rewritten = rewrite_announcement(
        payload, AdvertiserConfig(advertise_ip="172.30.11.54", proxy_port=8080)
    )

    assert rewritten["IP"] == "172.30.11.54"
    assert rewritten["URL"] == "http://172.30.11.54:8080/hoekens-anchor-alarm/"
    assert rewritten["Icon"] == "http://172.30.11.54:8080/hoekens-anchor-alarm/anchoralarm.png"
