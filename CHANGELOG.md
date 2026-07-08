# Changelog

## 0.3.1

- Apply formatter changes for CI linting after the UDP relay refactor.

## 0.3.0

- Roll back the HA compatibility proxy and site management features.
- Refactor the integration into a slim UDP relay for `signalk-navico-embedder` announcements.
- Rewrite SignalK Docker-internal announcement IP/URL/Icon fields to the configured boat-LAN IP and external proxy port.

## 0.2.2

- Fix proxy icon URL rewriting for same-origin target icons.

## 0.2.1

- Apply formatter changes for CI linting.

## 0.2.0

- Add a configurable compatibility proxy for advertised sites.
- Advertise proxy URLs instead of raw target URLs.
- Add HTML polyfills, Signal K request routing, header cleanup, CSS fallbacks, and conservative JavaScript downleveling in the proxy.

## 0.1.6

- Fix test formatting for CI linting.

## 0.1.5

- Change `remove_site` to remove only one matching site id and fail if the id is absent.
- Restore the default Home Assistant site for old entries that have no stored site list.

## 0.1.4

- Fix lint issue in `add_site` service implementation.

## 0.1.3

- Change `add_site` so it appends new sites instead of replacing an existing site with the same generated id.
- Reject duplicate explicit site ids in `add_site`; use `update_site` to replace an existing site.

## 0.1.2

- Stop the background advertiser cleanly during Home Assistant shutdown.

## 0.1.1

- Fix options flow compatibility with Home Assistant versions where `OptionsFlow.config_entry` is read-only.

## 0.1.0

- Initial Navico MFD UDP multicast advertiser custom integration.
- Adds config flow for interface/IP and interval.
- Creates a default Home Assistant advertised site.
- Adds services to add, update, remove, reload, send, and export advertised sites.
