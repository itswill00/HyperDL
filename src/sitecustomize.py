import os
import sys
import socket

_orig_getaddrinfo = socket.getaddrinfo
_doh_cache = {}

def _is_ip(host):
    try:
        socket.inet_aton(host)
        return True
    except Exception:
        return False

def _doh_query(host):
    import json
    import urllib.request
    if not host or _is_ip(host):
        return None
    if host in _doh_cache:
        return _doh_cache[host]

    endpoints = [
        ("https://1.1.1.1/dns-query?name={}&type=A", {"Accept": "application/dns-json", "User-Agent": "Mozilla/5.0"}),
        ("https://8.8.8.8/resolve?name={}&type=A", {"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    ]

    for ep_fmt, headers in endpoints:
        try:
            url = ep_fmt.format(host)
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode("utf-8", "ignore"))
                answers = [
                    a["data"] for a in data.get("Answer", [])
                    if a.get("type") == 1 and "data" in a and _is_ip(a["data"])
                ]
                if answers:
                    _doh_cache[host] = answers
                    return answers
        except Exception:
            continue
    return None

def _should_use_doh(host):
    low = (host or "").lower()
    conf_path = "/data/adb/hyperdl/vault_domains.conf"
    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r") as f:
                for line in f:
                    dom = line.strip().lower()
                    if dom and dom in low:
                        return True
        except Exception:
            pass

    try:
        res = _orig_getaddrinfo(host, None)
        if res:
            ip = res[0][4][0]
            if (ip.startswith("103.177.") or ip.startswith("103.10.") or
                ip.startswith("118.98.") or ip.startswith("36.86.") or
                ip.startswith("180.250.") or ip.startswith("202.152.")):
                return True
    except Exception:
        return True

    return False

def _hooked_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if not host or host in ("1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "localhost", "127.0.0.1"):
        return _orig_getaddrinfo(host, port, family, type, proto, flags)

    if _should_use_doh(host):
        doh_ips = _doh_query(host)
        if doh_ips:
            try:
                return _orig_getaddrinfo(doh_ips[0], port, family, type, proto, flags)
            except Exception:
                pass

    return _orig_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = _hooked_getaddrinfo
