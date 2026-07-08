# Navico Advertiser for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Tests](https://github.com/marimotica/ha_navico_advertiser/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/marimotica/ha_navico_advertiser/actions/workflows/tests.yml)
[![Linting](https://github.com/marimotica/ha_navico_advertiser/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/marimotica/ha_navico_advertiser/actions/workflows/lint.yml)
[![Latest Release](https://img.shields.io/github/v/release/marimotica/ha_navico_advertiser)](https://github.com/marimotica/ha_navico_advertiser/releases/latest)

[![Open your Home Assistant instance and open the add repository dialog with a specific repository URL pre-filled](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=marimotica&repository=ha_navico_advertiser&category=integration)

A small Home Assistant custom integration that relays `signalk-navico-embedder` UDP announcements onto the real boat LAN.

## What It Does

- Listens for Navico/B&G/Simrad web-app tile announcements on `239.2.1.1:2053`.
- Rewrites the announcement `IP`, `URL`, and `Icon` from SignalK's Docker-internal address to the configured HAOS boat-LAN address.
- Re-broadcasts the rewritten announcements from the configured HAOS interface.
- Leaves browser compatibility, proxying, transpilation, and SignalK authentication to `signalk-navico-embedder`.

## Required SignalK Setup

Install and enable `signalk-navico-embedder` in SignalK.

The SignalK plugin must run its compatibility proxy on a port that is reachable from the MFD boat LAN. In the HAOS SignalK add-on inspected during development, SignalK published `3000`, `3443`, `10110`, and `8375`, but did not publish the plugin default proxy port `8080`. The add-on must expose whichever proxy port `signalk-navico-embedder` is configured to use.

This integration does not replace that proxy. It only fixes the UDP multicast part that fails from a bridged SignalK container.

## Configuration

- `advertise_ip`: HAOS/Raspberry Pi IP on the boat Ethernet, for example `172.30.11.54`.
- `interface`: Output interface name, for example `end0`.
- `proxy_port`: External port where the SignalK Navico proxy is reachable from the MFD, usually `8080` if published.
- `interval`: How often cached announcements are re-broadcast.
- `listen_ip`: UDP listen address, normally `0.0.0.0`.
- `listen_port`: UDP listen port, normally `2053`.

## Services

### `navico_advertiser.reload`

Reload config entry data and rebroadcast cached announcements.

### `navico_advertiser.send_now`

Rebroadcast cached announcements immediately.

### `navico_advertiser.export_state`

Return relay config and cached announcement count for debugging.
