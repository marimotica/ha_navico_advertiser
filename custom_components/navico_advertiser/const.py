"""Constants for the Navico Advertiser integration."""

DOMAIN = "navico_advertiser"

DEFAULT_ADVERTISE_INTERVAL = 10
DEFAULT_MULTICAST_GROUP = "239.2.1.1"
DEFAULT_MULTICAST_PORT = 2053
DEFAULT_PROXY_PORT = 18099
DEFAULT_SOURCE = "Home Assistant"
DEFAULT_TTL = 1

CONF_ADVERTISE_IP = "advertise_ip"
CONF_INTERFACE = "interface"
CONF_INTERVAL = "interval"
CONF_PROXY_PORT = "proxy_port"
CONF_SITES = "sites"

SITE_ID = "id"
SITE_NAME = "name"
SITE_DESCRIPTION = "description"
SITE_URL = "url"
SITE_ICON = "icon"
SITE_LANGUAGE = "language"
SITE_SOURCE = "source"
SITE_PROGRESS_BAR = "progress_bar"
SITE_ONLY_SHOW_ON_CLIENT_IP = "only_show_on_client_ip"

SERVICE_ADD_SITE = "add_site"
SERVICE_REMOVE_SITE = "remove_site"
SERVICE_UPDATE_SITE = "update_site"
SERVICE_RELOAD = "reload"
SERVICE_SEND_NOW = "send_now"
SERVICE_EXPORT_STATE = "export_state"
