"""Descubrimiento de cámaras SIN librerías externas.
 - ONVIF: WS-Discovery (UDP multicast) + SOAP con WS-UsernameToken para obtener las URL RTSP.
 - Red IPv4: escaneo de puertos típicos de cámaras (554, 8899, 34567...).
"""
import base64
import hashlib
import ipaddress
import os
import socket
import time
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlparse, urlunparse
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


class OnvifError(Exception):
    pass


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _find_all(root, name):
    return [e for e in root.iter() if _local(e.tag) == name]


def _find_text(root, name):
    for e in root.iter():
        if _local(e.tag) == name and e.text and e.text.strip():
            return e.text.strip()
    return None


# ---------------------------------------------------------------- red local
def local_ipv4s():
    ips = set()
    try:
        ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    for target in ("8.8.8.8", "10.255.255.255"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((target, 80))        # UDP: no envía nada, solo elige interfaz
            ips.add(s.getsockname()[0])
            s.close()
        except OSError:
            pass
    return sorted(i for i in ips if not i.startswith(("127.", "169.254.", "0.")))


def local_subnets():
    return [str(ipaddress.ip_network(ip + "/24", strict=False)) for ip in local_ipv4s()]


def parse_hosts(text, limit=4096):
    """'192.168.1.0/24, 10.0.0.5-10.0.0.40, 192.168.0.10-50' -> lista de IPs."""
    hosts = []
    for token in text.replace(";", ",").replace(" ", ",").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            if "/" in token:
                hosts += [str(h) for h in ipaddress.ip_network(token, strict=False).hosts()]
            elif "-" in token:
                a, b = token.split("-", 1)
                if b.isdigit():
                    b = a.rsplit(".", 1)[0] + "." + b
                ia, ib = int(ipaddress.IPv4Address(a)), int(ipaddress.IPv4Address(b))
                if ib < ia:
                    raise ValueError
                hosts += [str(ipaddress.IPv4Address(i)) for i in range(ia, ib + 1)]
            else:
                hosts.append(str(ipaddress.IPv4Address(token)))
        except ValueError:
            raise ValueError(f"Rango inválido: {token}")
        if len(hosts) > limit:
            raise ValueError(f"Rango demasiado grande (máximo {limit} direcciones)")
    if not hosts:
        raise ValueError("Indica un rango, por ejemplo 192.168.1.0/24")
    return list(dict.fromkeys(hosts))


# ---------------------------------------------------------- WS-Discovery
PROBE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" '
    'xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing" '
    'xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" '
    'xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
    '<e:Header><w:MessageID>uuid:{id}</w:MessageID>'
    '<w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>'
    '<w:Action e:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>'
    '</e:Header><e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body>'
    '</e:Envelope>'
)


def parse_probe_match(data, src_ip):
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    xaddrs = _find_text(root, "XAddrs") or ""
    scopes = _find_text(root, "Scopes") or ""
    urls = [u for u in xaddrs.split() if u.startswith("http")]
    if not urls:
        return None
    url, ip = urls[0], src_ip
    for u in urls:                               # prefiere una URL con IPv4
        try:
            ipaddress.IPv4Address(urlparse(u).hostname or "")
            url, ip = u, urlparse(u).hostname
            break
        except ValueError:
            continue
    name = hw = ""
    for sc in scopes.split():
        if "/name/" in sc:
            name = unquote(sc.split("/name/", 1)[1])
        elif "/hardware/" in sc:
            hw = unquote(sc.split("/hardware/", 1)[1])
    return {"ip": ip, "xaddr": url, "name": name or hw or "ONVIF", "hardware": hw}


def discover_onvif(timeout=4.0):
    probe = PROBE.format(id=uuid.uuid4()).encode()
    socks = []
    for ip in (local_ipv4s() or [""]):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            if ip:
                s.bind((ip, 0))
                s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ip))
            s.settimeout(0.25)
            s.sendto(probe, ("239.255.255.250", 3702))
            socks.append(s)
        except OSError:
            continue
    found = {}
    start = time.monotonic()
    resent = False
    while time.monotonic() - start < timeout:
        if not resent and time.monotonic() - start > timeout / 2:
            resent = True
            for s in socks:
                try:
                    s.sendto(probe, ("239.255.255.250", 3702))
                except OSError:
                    pass
        for s in socks:
            try:
                data, addr = s.recvfrom(65535)
            except OSError:
                continue
            dev = parse_probe_match(data, addr[0])
            if dev:
                found.setdefault(dev["ip"], dev)
    for s in socks:
        s.close()
    return sorted(found.values(), key=lambda d: [int(x) for x in d["ip"].split(".")])


# ------------------------------------------------------------ cliente SOAP
_WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
_WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
_PROF = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0"
_B64 = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary"


def make_envelope(body, user=None, password="", offset=timedelta(0)):
    header = ""
    if user is not None:
        nonce = os.urandom(16)
        created = (datetime.now(timezone.utc) + offset).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        digest = base64.b64encode(
            hashlib.sha1(nonce + created.encode() + (password or "").encode()).digest()).decode()
        header = (
            f'<s:Header><wsse:Security s:mustUnderstand="1" xmlns:wsse="{_WSSE}" xmlns:wsu="{_WSU}">'
            f'<wsse:UsernameToken><wsse:Username>{escape(user)}</wsse:Username>'
            f'<wsse:Password Type="{_PROF}#PasswordDigest">{digest}</wsse:Password>'
            f'<wsse:Nonce EncodingType="{_B64}">{base64.b64encode(nonce).decode()}</wsse:Nonce>'
            f'<wsu:Created>{created}</wsu:Created></wsse:UsernameToken></wsse:Security></s:Header>')
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
            f'{header}<s:Body>{body}</s:Body></s:Envelope>')


def _fault_msg(raw_text, fault_el=None):
    low = raw_text.lower()
    if "notauthorized" in low or "not authorized" in low or "authorized" in low:
        return "usuario o contraseña incorrectos"
    if fault_el is not None:
        texts = [e.text.strip() for e in fault_el.iter() if _local(e.tag) == "Text" and e.text]
        if texts:
            return texts[0]
    return "error ONVIF"


def _post(url, body, user=None, password="", offset=timedelta(0), timeout=5):
    data = make_envelope(body, user, password, offset).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/soap+xml; charset=utf-8"})
    try:
        with urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except HTTPError as e:
        raw = e.read()
        try:
            fault = _find_all(ET.fromstring(raw), "Fault")
        except ET.ParseError:
            fault = []
        if e.code == 401:
            raise OnvifError("usuario o contraseña incorrectos")
        raise OnvifError(_fault_msg(raw.decode("utf-8", "ignore"), fault[0] if fault else None))
    except OSError:
        raise OnvifError("sin respuesta del dispositivo")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise OnvifError("respuesta inválida")
    fault = _find_all(root, "Fault")
    if fault:
        raise OnvifError(_fault_msg(raw.decode("utf-8", "ignore"), fault[0]))
    return root


def get_time_offset(xaddr):
    """Diferencia de reloj con la cámara (muchas rechazan el login si está desfasada)."""
    try:
        root = _post(xaddr, '<tds:GetSystemDateAndTime xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>')
        utc = _find_all(root, "UTCDateTime")[0]
        v = {_local(e.tag): int(e.text) for e in utc.iter() if e.text and e.text.strip().isdigit()}
        cam = datetime(v["Year"], v["Month"], v["Day"], v["Hour"], v["Minute"], v["Second"], tzinfo=timezone.utc)
        return cam - datetime.now(timezone.utc)
    except Exception:
        return timedelta(0)


def get_media_url(xaddr, user, pw, offset):
    body = ('<tds:GetCapabilities xmlns:tds="http://www.onvif.org/ver10/device/wsdl">'
            '<tds:Category>Media</tds:Category></tds:GetCapabilities>')
    try:
        root = _post(xaddr, body, user, pw, offset)
        for media in _find_all(root, "Media"):
            x = _find_text(media, "XAddr")
            if x:
                return x
    except OnvifError as e:
        if "contraseña" in str(e):
            raise
    return xaddr


def get_profiles(media_url, user, pw, offset):
    root = _post(media_url, '<trt:GetProfiles xmlns:trt="http://www.onvif.org/ver10/media/wsdl"/>',
                 user, pw, offset)
    out = []
    for p in _find_all(root, "Profiles"):
        token = p.get("token")
        if not token:
            continue
        w = h = 0
        for res in _find_all(p, "Resolution"):
            try:
                w, h = int(_find_text(res, "Width")), int(_find_text(res, "Height"))
                break
            except (TypeError, ValueError):
                continue
        out.append({"token": token, "name": _find_text(p, "Name") or token, "w": w, "h": h})
    return out


def get_stream_uri(media_url, token, user, pw, offset):
    body = ('<trt:GetStreamUri xmlns:trt="http://www.onvif.org/ver10/media/wsdl" '
            'xmlns:tt="http://www.onvif.org/ver10/schema"><trt:StreamSetup><tt:Stream>RTP-Unicast</tt:Stream>'
            '<tt:Transport><tt:Protocol>RTSP</tt:Protocol></tt:Transport></trt:StreamSetup>'
            f'<trt:ProfileToken>{escape(token)}</trt:ProfileToken></trt:GetStreamUri>')
    return _find_text(_post(media_url, body, user, pw, offset), "Uri")


def fix_uri(uri, device_host, user, pw):
    """Corrige host 0.0.0.0 y añade user:pass a la URL RTSP."""
    p = urlparse(uri)
    host = p.hostname or ""
    if host in ("", "0.0.0.0", "127.0.0.1"):
        host = device_host
    try:
        port = f":{p.port}" if p.port else ""
    except ValueError:
        port = ""
    netloc = host + port
    if user:
        netloc = f"{quote(user, safe='')}:{quote(pw or '', safe='')}@{netloc}"
    return urlunparse(p._replace(netloc=netloc))


def resolve_streams(xaddr, user, pw):
    """-> {'url_main': ..., 'url_sub': ..., 'profiles': n}.  Convencional = mayor resolución."""
    host = urlparse(xaddr).hostname or ""
    offset = get_time_offset(xaddr)
    media = get_media_url(xaddr, user, pw, offset)
    profiles = get_profiles(media, user, pw, offset)
    if not profiles:
        raise OnvifError("el dispositivo no tiene perfiles de video")
    ok = []
    for p in profiles:
        try:
            uri = get_stream_uri(media, p["token"], user, pw, offset)
        except OnvifError as e:
            if "contraseña" in str(e):
                raise
            continue
        if uri:
            p["uri"] = fix_uri(uri, host, user, pw)
            ok.append(p)
    if not ok:
        raise OnvifError("no se pudo obtener la URL de video")
    ok.sort(key=lambda p: p["w"] * p["h"])
    return {"url_sub": ok[0]["uri"], "url_main": ok[-1]["uri"], "profiles": len(ok)}


# ------------------------------------------------------- escaneo de red
PORT_NAMES = {554: "RTSP", 8554: "RTSP", 8899: "ONVIF", 34567: "iCSee/XM", 2020: "ONVIF Tapo", 80: "Web"}
SCAN_PORTS = [554, 8554, 8899, 34567, 2020, 80]
CAMERA_PORTS = {554, 8554, 8899, 34567, 2020}


def _port_open(ip, port, timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((ip, port)) == 0
    except OSError:
        return False
    finally:
        s.close()


def scan_network(hosts, ports=None, cam_ports=None, progress_cb=None, stop=None, timeout=0.6):
    ports = ports or SCAN_PORTS
    cam_ports = cam_ports or CAMERA_PORTS
    total, done, out = len(hosts), 0, []

    def probe(ip):
        if stop is not None and stop.is_set():
            return ip, []
        return ip, [p for p in ports if _port_open(ip, p, timeout)]

    with ThreadPoolExecutor(max_workers=min(128, max(1, total))) as ex:
        for fut in as_completed([ex.submit(probe, ip) for ip in hosts]):
            ip, open_ports = fut.result()
            done += 1
            if any(p in cam_ports for p in open_ports):
                out.append({"ip": ip, "ports": open_ports})
            if progress_cb and (done % 4 == 0 or done == total):
                progress_cb(done, total)
    out.sort(key=lambda d: [int(x) for x in d["ip"].split(".")])
    return out


def onvif_candidates(dev):
    """URLs de servicio ONVIF a probar según los puertos abiertos."""
    ip, ports, urls = dev["ip"], dev["ports"], []
    if 8899 in ports:
        urls.append(f"http://{ip}:8899/onvif/device_service")
    if 80 in ports:
        urls.append(f"http://{ip}/onvif/device_service")
    if 2020 in ports:
        urls.append(f"http://{ip}:2020/onvif/device_service")
    return urls
