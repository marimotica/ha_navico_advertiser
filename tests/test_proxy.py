"""Tests for Navico compatibility proxy helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.navico_advertiser.proxy import (
    ProxyConfig,
    inject_html_compatibility,
    javascript_needs_transpile,
    proxied_advertisement_sites,
    target_url_for,
    transform_css,
    transform_javascript,
    transform_javascript_with_python_esbuild,
)


def test_proxied_advertisement_sites_rewrites_url_and_icon() -> None:
    """Test advertised sites use proxy URLs."""
    sites = [
        {
            "id": "anchor",
            "name": "Anchor",
            "url": "http://172.30.11.54:3000/hoekens-anchor-alarm/",
            "icon": "http://172.30.11.54:3000/hoekens-anchor-alarm/anchoralarm.png",
        }
    ]

    proxied = proxied_advertisement_sites(sites, ProxyConfig("172.30.11.54", 18099))

    assert proxied[0]["url"] == "http://172.30.11.54:18099/navico_advertiser/proxy/anchor/"
    assert proxied[0]["icon"] == (
        "http://172.30.11.54:18099/navico_advertiser/proxy/anchor/anchoralarm.png"
    )


def test_target_url_for_relative_and_absolute_signalk_paths() -> None:
    """Test target URL resolution."""
    site = {"url": "http://172.30.11.54:3000/hoekens-anchor-alarm/"}

    assert target_url_for(site, "assets/index.js") == (
        "http://172.30.11.54:3000/hoekens-anchor-alarm/assets/index.js"
    )
    assert target_url_for(site, "signalk/v1/stream") == (
        "http://172.30.11.54:3000/signalk/v1/stream"
    )
    assert target_url_for(site, "plugins/hoekens-anchor-alarm/ui-config") == (
        "http://172.30.11.54:3000/plugins/hoekens-anchor-alarm/ui-config"
    )


def test_inject_html_compatibility() -> None:
    """Test HTML compatibility scripts are injected."""
    html = "<html><head><title>x</title></head><body></body></html>"

    out = inject_html_compatibility(html, "/navico_advertiser/proxy/anchor/")

    assert "Object.fromEntries" in out
    assert "window.fetch" in out
    assert out.index("window.fetch") < out.index("</head>")


def test_transform_javascript_common_patterns() -> None:
    """Test modern JavaScript requires an available transpiler."""
    source = "const x = value ?? {}; const y = data?.name;"

    assert javascript_needs_transpile(source) is True
    with (
        patch(
            "custom_components.navico_advertiser.proxy.transform_javascript_with_python_esbuild",
            return_value=None,
        ),
        patch("shutil.which", return_value=None),
        pytest.raises(RuntimeError),
    ):
        transform_javascript(source)


def test_transform_javascript_with_python_esbuild_missing_module() -> None:
    """Test missing python esbuild wrapper falls back cleanly."""
    with patch("builtins.__import__", side_effect=ImportError):
        assert transform_javascript_with_python_esbuild("const x = a?.b;") is None


def test_transform_javascript_leaves_old_syntax_unchanged() -> None:
    """Test already-compatible JavaScript is left untouched."""
    source = "var x = value || {};"

    assert javascript_needs_transpile(source) is False
    assert transform_javascript(source) == source


def test_transform_css_min_fallback() -> None:
    """Test CSS min/max fallback insertion."""
    source = ".dialog {\n  width: min(92vw, 900px);\n}"

    out = transform_css(source)

    assert "width: 92vw;" in out
    assert "width: min(92vw, 900px);" in out
