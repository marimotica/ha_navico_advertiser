# Changelog

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
