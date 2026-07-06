"""Compatibility proxy for Navico MFD browser panels."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from aiohttp import ClientError, ClientTimeout, WSMsgType, web

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ADVERTISE_IP,
    CONF_PROXY_PORT,
    DEFAULT_PROXY_PORT,
    DOMAIN,
    SITE_ICON,
    SITE_ID,
    SITE_URL,
)

_LOGGER = logging.getLogger(__name__)

PROXY_PREFIX = f"/{DOMAIN}/proxy"
ABSOLUTE_TARGET_PREFIXES = ("signalk/", "plugins/", "skServer/")

STRIP_REQUEST_HEADERS = {
    "host",
    "if-none-match",
    "if-modified-since",
    "if-match",
    "if-unmodified-since",
    "if-range",
    "accept-encoding",
}

STRIP_RESPONSE_HEADERS = {
    "content-length",
    "content-encoding",
    "transfer-encoding",
    "x-frame-options",
    "content-security-policy",
    "content-security-policy-report-only",
}

POLYFILLS_SCRIPT = """<script>
(function(w){
if(!Object.fromEntries){Object.fromEntries=function(entries){var o={};for(var e of entries){o[e[0]]=e[1];}return o;};}
if(!Array.prototype.flat){Array.prototype.flat=function flat(depth){var d=depth===undefined?1:Math.floor(depth);if(d<1)return Array.prototype.slice.call(this);return Array.prototype.reduce.call(this,function(acc,val){Array.isArray(val)?acc.push.apply(acc,Array.prototype.flat.call(val,d-1)):acc.push(val);return acc;},[]);};}
if(!Array.prototype.flatMap){Array.prototype.flatMap=function(fn,ctx){return Array.prototype.flat.call(Array.prototype.map.call(this,fn,ctx),1);};}
if(!Array.prototype.at){Array.prototype.at=function(i){var n=Math.trunc(i)||0;if(n<0)n+=this.length;return n>=0&&n<this.length?this[n]:undefined;};}
if(!String.prototype.at){String.prototype.at=function(i){var n=Math.trunc(i)||0;if(n<0)n+=this.length;return n>=0&&n<this.length?this.charAt(n):undefined;};}
if(!String.prototype.replaceAll){String.prototype.replaceAll=function(s,r){return s instanceof RegExp?this.replace(s,r):this.split(s).join(r);};}
if(!Object.hasOwn){Object.hasOwn=function(obj,prop){return Object.prototype.hasOwnProperty.call(obj,prop);};}
if(!Promise.allSettled){Promise.allSettled=function(ps){return Promise.all(Array.prototype.map.call(ps,function(p){return Promise.resolve(p).then(function(v){return{status:'fulfilled',value:v};},function(r){return{status:'rejected',reason:r};});}));};}
if(typeof globalThis==='undefined'){w.globalThis=w;}
if(typeof w.queueMicrotask!=='function'){w.queueMicrotask=function(fn){Promise.resolve().then(fn);};}
})(window);
</script>"""


def browser_shim_script(proxy_base: str) -> str:
    """Return browser-side URL rewrite shim for absolute Signal K calls."""
    return f"""<script>
(function(){{
var proxyBase={proxy_base!r};
function rewrite(input){{
  try {{
    var url = typeof input === 'string' ? input : input && input.url;
    if (!url) return input;
    var u = new URL(url, window.location.href);
    if (u.host === window.location.host && (/^[/](signalk|plugins|skServer)[/]/).test(u.pathname)) {{
      var path = proxyBase.replace(/[/]$/, '') + u.pathname + u.search + u.hash;
      if (u.protocol === 'ws:' || u.protocol === 'wss:') {{
        return (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host + path;
      }}
      return path;
    }}
  }} catch(e) {{}}
  return input;
}}
var nativeFetch=window.fetch;
if(nativeFetch) window.fetch=function(input,init){{return nativeFetch.call(this,rewrite(input),init);}};
var NativeWebSocket=window.WebSocket;
if(NativeWebSocket) window.WebSocket=function(url,protocols){{return protocols===undefined?new NativeWebSocket(rewrite(url)):new NativeWebSocket(rewrite(url),protocols);}};
if(NativeWebSocket){{window.WebSocket.prototype=NativeWebSocket.prototype;window.WebSocket.OPEN=NativeWebSocket.OPEN;window.WebSocket.CONNECTING=NativeWebSocket.CONNECTING;window.WebSocket.CLOSING=NativeWebSocket.CLOSING;window.WebSocket.CLOSED=NativeWebSocket.CLOSED;}}
}})();
</script>"""


@dataclass(slots=True)
class ProxyConfig:
    """Runtime proxy configuration."""

    advertise_ip: str
    proxy_port: int = DEFAULT_PROXY_PORT


def proxy_config_from_entry_data(data: dict[str, Any]) -> ProxyConfig:
    """Build proxy config from config entry data."""
    return ProxyConfig(
        advertise_ip=data[CONF_ADVERTISE_IP],
        proxy_port=int(data.get(CONF_PROXY_PORT, DEFAULT_PROXY_PORT)),
    )


def proxy_base_url(config: ProxyConfig, site_id: str) -> str:
    """Return public proxy base URL for a site."""
    return f"http://{config.advertise_ip}:{config.proxy_port}{PROXY_PREFIX}/{site_id}/"


def proxied_advertisement_sites(
    sites: list[dict[str, Any]], config: ProxyConfig
) -> list[dict[str, Any]]:
    """Return copies of sites with URLs rewritten to this proxy."""
    out: list[dict[str, Any]] = []
    for site in sites:
        copied = dict(site)
        base = proxy_base_url(config, copied[SITE_ID])
        copied[SITE_URL] = base
        copied[SITE_ICON] = proxied_icon_url(copied, config)
        out.append(copied)
    return out


def proxied_icon_url(site: dict[str, Any], config: ProxyConfig) -> str:
    """Return a proxy URL for an icon when it belongs to the target site."""
    icon = str(site.get(SITE_ICON) or "")
    target = str(site[SITE_URL])
    if not icon:
        return proxy_base_url(config, site[SITE_ID])
    try:
        icon_parts = urlsplit(icon)
        target_parts = urlsplit(target)
    except ValueError:
        return icon
    if icon_parts.scheme in ("http", "https") and (
        icon_parts.scheme,
        icon_parts.netloc,
    ) == (target_parts.scheme, target_parts.netloc):
        target_path = target_parts.path if target_parts.path.endswith("/") else target_parts.path + "/"
        path = icon_parts.path.lstrip("/")
        if icon_parts.path.startswith(target_path):
            path = icon_parts.path[len(target_path) :]
        return f"{proxy_base_url(config, site[SITE_ID])}{path}"
    return icon


def target_url_for(site: dict[str, Any], tail: str) -> str:
    """Return target URL for a proxied request tail."""
    base = str(site[SITE_URL])
    if not base.endswith("/"):
        base += "/"
    if not tail:
        return base
    if tail.startswith(ABSOLUTE_TARGET_PREFIXES):
        parts = urlsplit(base)
        return urlunsplit((parts.scheme, parts.netloc, "/" + tail, "", ""))
    return urljoin(base, tail)


def inject_html_compatibility(html: str, proxy_base: str) -> str:
    """Inject MFD compatibility scripts into HTML."""
    html = html.replace('type="module" crossorigin src=', 'src=')
    html = html.replace("type='module' crossorigin src=", "src=")
    html = html.replace('type="module" src=', 'src=')
    html = html.replace("type='module' src=", "src=")
    injection = POLYFILLS_SCRIPT + "\n" + browser_shim_script(proxy_base) + "\n"
    if "</head>" in html:
        return html.replace("</head>", injection + "</head>", 1)
    return injection + html


def transform_javascript(source: str) -> str:
    """Transpile JavaScript for the MFD browser."""
    if not javascript_needs_transpile(source):
        return source

    wrapper_result = transform_javascript_with_python_esbuild(source)
    if wrapper_result is not None:
        return wrapper_result

    esbuild = shutil.which("esbuild")
    if not esbuild:
        raise RuntimeError(
            "JavaScript uses syntax unsupported by the MFD browser, but no "
            "esbuild executable is available to transpile it"
        )

    result = subprocess.run(
        [esbuild, "--loader=js", "--target=chrome69", "--minify"],
        input=source,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "esbuild failed")
    return result.stdout


def transform_javascript_with_python_esbuild(source: str) -> str | None:
    """Transpile using the Python esbuild wrapper when installed."""
    try:
        from esbuild import EsBuildLauncher
    except ImportError:
        return None

    try:
        launcher = EsBuildLauncher(auto_install=True)
        return _run_python_esbuild(launcher, source)
    except Exception as err:  # pragma: no cover - depends on runtime install/network
        _LOGGER.warning("Python esbuild wrapper failed: %s", err)
        return None


def _run_python_esbuild(launcher: Any, source: str) -> str:
    """Run python-esbuild with stdin input."""
    if launcher.auto_install and not launcher.bin_path.exists():
        launcher.install()
    result = subprocess.run(
        [str(launcher.bin_path), "--loader=js", "--target=chrome69", "--minify"],
        input=source,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "python esbuild failed")
    return result.stdout


def javascript_needs_transpile(source: str) -> bool:
    """Return whether JavaScript contains syntax too new for Chromium 69."""
    return "?." in source or "??" in source


def transform_css(source: str) -> str:
    """Add simple CSS fallbacks for old Chromium."""
    lines: list[str] = []
    for line in source.splitlines():
        match = re.search(r"^([\s\w-]+:\s*)(min|max)\(([^,;]+),[^;]+(;.*)$", line)
        if match:
            lines.append(f"{match.group(1)}{match.group(3).strip()}{match.group(4)}")
        lines.append(line)
    return "\n".join(lines)


class NavicoProxy:
    """HTTP compatibility proxy for advertised MFD sites."""

    def __init__(
        self, hass: HomeAssistant, config: ProxyConfig, sites: list[dict[str, Any]]
    ) -> None:
        """Initialize proxy."""
        self.hass = hass
        self.config = config
        self.sites = sites
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._transform_cache: dict[tuple[str, str, str], bytes] = {}

    @callback
    def update(self, config: ProxyConfig, sites: list[dict[str, Any]]) -> bool:
        """Update runtime data. Return true when bind config changed."""
        changed = config.proxy_port != self.config.proxy_port
        self.config = config
        self.sites = sites
        return changed

    async def async_start(self) -> None:
        """Start proxy server."""
        if self._runner is not None:
            return
        app = web.Application()
        app.router.add_route("*", f"{PROXY_PREFIX}" + "/{site_id}/{tail:.*}", self._handle)
        app.router.add_route("*", f"{PROXY_PREFIX}" + "/{site_id}", self._handle)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", self.config.proxy_port)
        await self._site.start()
        _LOGGER.info("Navico compatibility proxy listening on port %s", self.config.proxy_port)

    async def async_stop(self) -> None:
        """Stop proxy server."""
        if self._runner is None:
            return
        with contextlib.suppress(Exception):
            await self._runner.cleanup()
        self._runner = None
        self._site = None

    async def async_restart(self) -> None:
        """Restart proxy server."""
        await self.async_stop()
        self._transform_cache.clear()
        await self.async_start()

    def _site_by_id(self, site_id: str) -> dict[str, Any] | None:
        """Return configured site by id."""
        for site in self.sites:
            if site.get(SITE_ID) == site_id:
                return site
        return None

    async def _handle(self, request: web.Request) -> web.StreamResponse:
        """Handle a proxied HTTP or WebSocket request."""
        site_id = request.match_info["site_id"]
        site = self._site_by_id(site_id)
        if site is None:
            raise web.HTTPNotFound(text="Unknown Navico proxy site")
        tail = request.match_info.get("tail", "")
        target = target_url_for(site, tail)
        if request.query_string:
            target += "?" + request.query_string
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await self._proxy_websocket(request, target)
        return await self._proxy_http(request, site_id, target)

    async def _proxy_http(
        self, request: web.Request, site_id: str, target: str
    ) -> web.Response:
        """Proxy one HTTP request."""
        session = async_get_clientsession(self.hass)
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in STRIP_REQUEST_HEADERS
        }
        body = await request.read()
        try:
            async with session.request(
                request.method,
                target,
                headers=headers,
                data=body if body else None,
                allow_redirects=False,
                timeout=ClientTimeout(total=30),
            ) as response:
                content = await response.read()
                response_headers = {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() not in STRIP_RESPONSE_HEADERS
                }
                status = response.status
                content_type = response.headers.get("content-type", "")
        except (asyncio.TimeoutError, ClientError) as err:
            raise web.HTTPBadGateway(text=f"Proxy error: {err}") from err

        if "location" in response_headers:
            response_headers["location"] = self._rewrite_location(
                response_headers["location"], site_id
            )

        if "text/html" in content_type:
            text = content.decode("utf-8", errors="replace")
            content = inject_html_compatibility(
                text, f"{PROXY_PREFIX}/{site_id}/"
            ).encode()
        elif "javascript" in content_type:
            cache_key = self._cache_key(target, response_headers)
            if cached := self._transform_cache.get(cache_key):
                content = cached
            else:
                try:
                    content = (
                        await self.hass.async_add_executor_job(
                            transform_javascript,
                            content.decode("utf-8", errors="replace"),
                        )
                    ).encode()
                    self._transform_cache[cache_key] = content
                except RuntimeError as err:
                    _LOGGER.error("JavaScript compatibility transform failed: %s", err)
                    return web.Response(status=502, text=f"Proxy JavaScript error: {err}")
        elif "text/css" in content_type:
            cache_key = self._cache_key(target, response_headers)
            if cached := self._transform_cache.get(cache_key):
                content = cached
            else:
                content = (
                    await self.hass.async_add_executor_job(
                        transform_css, content.decode("utf-8", errors="replace")
                    )
                ).encode()
                self._transform_cache[cache_key] = content

        return web.Response(
            body=content,
            status=status,
            headers=response_headers,
            content_type=None,
        )

    def _cache_key(self, target: str, headers: dict[str, str]) -> tuple[str, str, str]:
        """Return transform cache key."""
        return (target, headers.get("etag", ""), headers.get("last-modified", ""))

    async def _proxy_websocket(
        self, request: web.Request, target: str
    ) -> web.WebSocketResponse:
        """Proxy a WebSocket connection."""
        ws_server = web.WebSocketResponse()
        await ws_server.prepare(request)
        target_ws = target.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
        session = async_get_clientsession(self.hass)
        try:
            async with session.ws_connect(target_ws, timeout=ClientTimeout(total=30)) as ws_client:
                async def client_to_target() -> None:
                    async for msg in ws_server:
                        if msg.type == WSMsgType.TEXT:
                            await ws_client.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await ws_client.send_bytes(msg.data)
                        elif msg.type == WSMsgType.CLOSE:
                            await ws_client.close()

                async def target_to_client() -> None:
                    async for msg in ws_client:
                        if msg.type == WSMsgType.TEXT:
                            await ws_server.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await ws_server.send_bytes(msg.data)
                        elif msg.type == WSMsgType.CLOSE:
                            await ws_server.close()

                await asyncio.gather(client_to_target(), target_to_client())
        except (asyncio.TimeoutError, ClientError) as err:
            _LOGGER.debug("WebSocket proxy error for %s: %s", target_ws, err)
        return ws_server

    def _rewrite_location(self, location: str, site_id: str) -> str:
        """Rewrite target-origin redirects back through the proxy."""
        site = self._site_by_id(site_id)
        if not site:
            return location
        target_parts = urlsplit(str(site[SITE_URL]))
        try:
            location_parts = urlsplit(location)
        except ValueError:
            return location
        if (location_parts.scheme, location_parts.netloc) == (
            target_parts.scheme,
            target_parts.netloc,
        ):
            return f"{proxy_base_url(self.config, site_id)}{location_parts.path.lstrip('/')}"
        return location
