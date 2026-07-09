"""Constants for the Navico Advertiser integration."""

DOMAIN = "navico_advertiser"

DEFAULT_ADVERTISE_INTERVAL = 10
DEFAULT_LISTEN_IP = "0.0.0.0"
DEFAULT_LISTEN_PORT = 2053
DEFAULT_MULTICAST_GROUP = "239.2.1.1"
DEFAULT_MULTICAST_PORT = 2053
DEFAULT_SOURCE = "Home Assistant"
DEFAULT_TTL = 1

CONF_ADVERTISE_IP = "advertise_ip"
CONF_INTERFACE = "interface"
CONF_INTERVAL = "interval"
CONF_LISTEN_IP = "listen_ip"
CONF_LISTEN_PORT = "listen_port"

SERVICE_RELOAD = "reload"
SERVICE_SEND_NOW = "send_now"
SERVICE_EXPORT_STATE = "export_state"
