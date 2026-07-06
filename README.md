# Navico Advertiser for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Tests](https://github.com/marimotica/ha_navico_advertiser/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/marimotica/ha_navico_advertiser/actions/workflows/tests.yml)
[![Linting](https://github.com/marimotica/ha_navico_advertiser/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/marimotica/ha_navico_advertiser/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/marimotica/ha_navico_advertiser/branch/main/graph/badge.svg)](https://codecov.io/gh/marimotica/ha_navico_advertiser)
[![Latest Release](https://img.shields.io/github/v/release/marimotica/ha_navico_advertiser)](https://github.com/marimotica/ha_navico_advertiser/releases/latest)

[![Open your Home Assistant instance and open the add repository dialog with a specific repository URL pre-filled](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=marimotica&repository=ha_navico_advertiser&category=integration)

A Home Assistant custom integration that advertises Home Assistant and other local web apps as browser tiles on Navico/B&G/Simrad MFDs.

## Features

- **Navico MFD Discovery**: Sends UDP multicast advertisements to `239.2.1.1:2053`
- **Host-Network Friendly**: Runs inside Home Assistant and can advertise the HAOS LAN IP directly
- **Configurable Interface/IP**: Configure the advertised IPv4 address and optional interface label from the integration UI
- **Multiple Advertised Sites**: Add Home Assistant, dashboards, Signal K, Scheiber, or other local URLs
- **Compatibility Proxy**: Advertises MFD-safe proxy URLs and rewrites web app responses for older Navico browsers
- **Runtime Updates**: Add, update, remove, reload, or send advertisements immediately via services
- **Persistent Options**: Advertised sites persist in the config entry options and can be edited later

## HACS Status

- Repository type: HACS Integration (Custom Repository)
- Installation mode: repository-based (`zip_release: false`)
- Add directly in HACS via the one-click badge above or by URL:
- `https://github.com/marimotica/ha_navico_advertiser`

## Installation

### Manual Installation

1. Copy the `custom_components/navico_advertiser` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to Settings -> Devices & Services -> Add Integration
4. Search for "Navico Advertiser"

### HACS Installation

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right and select "Custom repositories"
4. Add `https://github.com/marimotica/ha_navico_advertiser` as an Integration
5. Search for "Navico Advertiser"
6. Click Install
7. Restart Home Assistant

## Configuration

### Initial Setup

1. Add the integration via the UI
2. Enter the interface name for documentation, for example `end0`
3. Enter the IPv4 address that the MFD can reach, for example `172.30.11.54`
4. Enter the advertisement interval, normally `10` seconds
5. Enter the compatibility proxy port, normally `18099`
6. The integration creates a default `Home Assistant` advertised site pointing at `http://<advertise_ip>:8123/`

The interface name is currently stored for clarity. The actual multicast interface is selected by binding to the advertised IPv4 address, which is what Navico MFDs validate in the UDP payload.

Advertisements always point at the integration's compatibility proxy, for example `http://172.30.11.54:18099/navico_advertiser/proxy/home_assistant/`. The proxy forwards to the configured site URL and applies MFD compatibility fixes: conditional-cache header stripping, HTML polyfill injection, Signal K fetch/WebSocket URL routing, CSS fallbacks, and a conservative JavaScript downlevel pass.

### Managing Advertised Sites

To edit advertised sites after setup:

1. Go to Settings -> Devices & Services
2. Find "Navico Advertiser" and click "Configure"
3. Edit the advertised sites JSON
4. Save the options

You can also use services to add, update, or remove sites without editing JSON manually.

## Services

### `navico_advertiser.add_site`

Add an advertised site.

Adds a new advertised site. If `id` is omitted and another site has the same generated id, a unique suffix is added automatically, for example `home_assistant_2`. If `id` is explicitly provided and already exists, the service fails; use `navico_advertiser.update_site` to replace an existing site.

**Fields:**
- `id` (optional): Stable site id. Generated from `name` if omitted
- `name` (required): Name shown on the MFD tile
- `url` (required): URL opened by the MFD browser
- `icon` (required): Icon URL shown by the MFD
- `description` (optional): Tile description
- `language` (optional): Text language, defaults to `en`
- `source` (optional): Source field, defaults to `Home Assistant`
- `progress_bar` (optional): Show browser panel progress bar, defaults to `true`
- `only_show_on_client_ip` (optional): Emit `OnlyShowOnClientIP`, defaults to `true`

**Example:**
```yaml
service: navico_advertiser.add_site
data:
  id: home_assistant
  name: Home Assistant
  description: Home Assistant on HAOS
  url: http://172.30.11.54:8123/
  icon: http://172.30.11.54:8123/favicon.ico
```

### `navico_advertiser.update_site`

Update an existing advertised site. The `id` must already exist.

**Example:**
```yaml
service: navico_advertiser.update_site
data:
  id: signalk
  name: Signal K
  description: Signal K server
  url: http://172.30.11.54:3000/
  icon: http://172.30.11.54:3000/favicon.ico
```

### `navico_advertiser.remove_site`

Remove an advertised site.

**Example:**
```yaml
service: navico_advertiser.remove_site
data:
  id: signalk
```

### `navico_advertiser.send_now`

Send all configured advertisements immediately.

**Example:**
```yaml
service: navico_advertiser.send_now
```

### `navico_advertiser.reload`

Reload the current config entry data into the background advertiser and send once.

**Example:**
```yaml
service: navico_advertiser.reload
```

### `navico_advertiser.export_state`

Export current state via service response for debugging.

**Example:**
```yaml
service: navico_advertiser.export_state
response_variable: state
```

## Protocol

Navico MFDs listen for UDP multicast packets on:

- Multicast group: `239.2.1.1`
- Port: `2053`

The integration sends JSON payloads like this:

```json
{
  "Version": "1",
  "Source": "Home Assistant",
  "IP": "172.30.11.54",
  "FeatureName": "Home Assistant",
  "Text": [
    {
      "Language": "en",
      "Name": "Home Assistant",
      "Description": "Home Assistant on HAOS"
    }
  ],
  "Icon": "http://172.30.11.54:8123/favicon.ico",
  "URL": "http://172.30.11.54:8123/",
  "OnlyShowOnClientIP": "true",
  "BrowserPanel": {
    "Enable": true,
    "ProgressBarEnable": true,
    "MenuText": [
      {
        "Language": "en",
        "Name": "Home Assistant"
      }
    ]
  }
}
```

The `IP` field should match the source IP of the UDP packet. This is why the integration binds the socket to the configured advertised IPv4 address.

## Development

Run tests locally:

```bash
pytest \
  --timeout=10 \
  --durations=10 \
  --cov custom_components.navico_advertiser \
  --cov-report term-missing \
  tests
```

Run pre-commit locally:

```bash
pre-commit run --all-files --show-diff-on-failure --color=always
```
