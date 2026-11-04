import os
import sys
import socket
import urllib.parse

_orig_getaddrinfo = socket.getaddrinfo
_doh_cache = {}
_vault_conf_state = {"sig": None, "domains": ()}

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
            url = ep_fmt.format(urllib.parse.quote(host, safe=""))
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode("utf-8", "ignore"))
                answers = [
                    a["data"] for a in data.get("Answer", [])
                    if a.get("type") == 1 and "data" in a and _is_ip(a["data"])
                ]
                if answers:
                    if len(_doh_cache) >= 256:
                        _doh_cache.clear()
                    _doh_cache[host] = answers
                    return answers
        except Exception:
            continue
    return None

def _vault_domains(conf_path="/data/adb/hyperdl/vault_domains.conf"):
    """Read the shared vault list, refreshing only when the file changes."""
    try:
        st = os.stat(conf_path)
    except Exception:
        return ()
    sig = (st.st_mtime_ns, st.st_size)
    if sig == _vault_conf_state["sig"]:
        return _vault_conf_state["domains"]
    try:
        with open(conf_path, "r") as f:
            domains = tuple(
                line.strip().lower().lstrip(".") for line in f
                if line.strip() and not line.lstrip().startswith("#")
            )
    except Exception:
        domains = ()
    _vault_conf_state["sig"] = sig
    _vault_conf_state["domains"] = domains
    return domains

def _should_use_doh(host):
    low = (host or "").lower().rstrip(".")
    for dom in _vault_domains():
        # Match the domain itself and real subdomains only. A plain substring
        # check also matched lookalikes such as "notpornhub.com".
        if low == dom or low.endswith("." + dom):
            return True

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
    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
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
