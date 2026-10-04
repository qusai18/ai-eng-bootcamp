"""Local open-port checker.

Run: python app.py
Then open http://127.0.0.1:8765

Reads listening sockets on this computer (the same list as
``netstat -ano | find "LISTEN"``). It does not probe other machines.

Vulnerability notes come from public catalogs for this computer's own
public address: CISA Known Exploited Vulnerabilities, NIST NVD CVE
records, and Shodan InternetDB. They describe exposure and published
advisories. They do not confirm an unpatched version and they do not
include exploit steps.
"""

from __future__ import annotations

import csv
import io
import ipaddress
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8765"))
HOST = "0.0.0.0"
HOSTED = os.environ.get("RENDER") == "true"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# title, detail, category
PORT_INFO: dict[int, tuple[str, str, str]] = {
    20: ("FTP data", "File transfer data channel.", "File sharing"),
    21: ("FTP", "File transfer server.", "File sharing"),
    22: ("SSH", "Secure shell for remote login.", "Remote access"),
    23: ("Telnet", "Remote login. The traffic is unencrypted.", "Remote access"),
    25: ("SMTP", "Sending email.", "Mail"),
    53: ("DNS", "Turns names into IP addresses.", "Network"),
    80: ("HTTP", "A website or a local web app.", "Web"),
    110: ("POP3", "Downloading email.", "Mail"),
    123: ("NTP", "Clock synchronization.", "Network"),
    135: ("Windows RPC", "Windows remote procedure calls, used by many built-in Windows features.", "Windows"),
    137: ("NetBIOS names", "Windows name lookup on the local network.", "File sharing"),
    138: ("NetBIOS datagrams", "Windows network browsing.", "File sharing"),
    139: ("NetBIOS sessions", "Windows file and printer sharing on this adapter.", "File sharing"),
    143: ("IMAP", "Reading email.", "Mail"),
    443: ("HTTPS", "A secure website or a local web app.", "Web"),
    445: ("SMB file sharing", "Windows file sharing, the port shared folders use.", "File sharing"),
    500: ("VPN key exchange", "IKE, used to set up a VPN.", "VPN"),
    514: ("Syslog", "Collecting log messages.", "Network"),
    587: ("Mail submission", "Sending email from a mail app.", "Mail"),
    993: ("Secure IMAP", "Reading email over an encrypted connection.", "Mail"),
    995: ("Secure POP3", "Downloading email over an encrypted connection.", "Mail"),
    1433: ("SQL Server", "Microsoft SQL Server database.", "Database"),
    1434: ("SQL Server browser", "Helps clients find a SQL Server instance.", "Database"),
    1521: ("Oracle", "Oracle database.", "Database"),
    1883: ("MQTT", "Messaging, often used by smart-home devices.", "Network"),
    1900: ("Device discovery", "SSDP / UPnP. Finds TVs, printers, and similar devices on the local network.", "Network"),
    2179: ("Hyper-V console", "Virtual machine console traffic.", "Windows"),
    3000: ("Development server", "A common port for Node, React, and Next.js.", "Development"),
    3306: ("MySQL", "MySQL or MariaDB database.", "Database"),
    3389: ("Remote Desktop", "Windows Remote Desktop (RDP).", "Remote access"),
    3478: ("Call setup", "STUN. Helps voice and video calls through a router.", "Calls"),
    4500: ("VPN through a router", "IPsec NAT-T. VPN traffic when you are behind a home router.", "VPN"),
    5000: ("Development server", "A common port for Flask and other local APIs.", "Development"),
    5040: ("Connected devices", "Windows Connected Devices Platform, used for nearby-device features.", "Windows"),
    5173: ("Vite dev server", "The usual port for a Vite frontend development server.", "Development"),
    5353: ("mDNS", "Local device names, the same idea as Bonjour.", "Network"),
    5354: ("Hardware helper", "Often a PC-maker helper such as Intel local management.", "Hardware"),
    5355: ("LLMNR", "Windows local name resolution.", "Network"),
    5357: ("Device discovery", "Windows Web Services discovery for printers and other devices.", "Network"),
    5432: ("PostgreSQL", "PostgreSQL database.", "Database"),
    5672: ("Message queue", "AMQP, often RabbitMQ.", "Development"),
    5900: ("VNC", "Remote screen sharing.", "Remote access"),
    5938: ("TeamViewer", "TeamViewer remote support.", "Remote access"),
    5985: ("Windows remote management", "WinRM. Remote PowerShell and management.", "Remote access"),
    5986: ("Windows remote management", "WinRM over HTTPS.", "Remote access"),
    6379: ("Redis", "Redis cache or database.", "Database"),
    6568: ("AnyDesk", "AnyDesk remote desktop.", "Remote access"),
    7070: ("AnyDesk", "AnyDesk remote desktop.", "Remote access"),
    7680: ("Windows Update sharing", "Delivery Optimization. Windows can share update downloads on the local network.", "Windows"),
    8000: ("Development server", "A common port for Django, Uvicorn, and local APIs.", "Development"),
    8080: ("Web app", "A web app, proxy, or admin page on an alternate HTTP port.", "Web"),
    8443: ("Secure web app", "A web app or admin page on an alternate HTTPS port.", "Web"),
    8888: ("Jupyter or dev server", "Often Jupyter Notebook or another local development tool.", "Development"),
    9000: ("Local admin or dev tool", "Often a local admin page or a development server.", "Development"),
    9090: ("Metrics", "Often Prometheus.", "Development"),
    9200: ("Elasticsearch", "Search index.", "Database"),
    11434: ("Ollama", "A local AI model server.", "Development"),
    27017: ("MongoDB", "MongoDB database.", "Database"),
}

# key, category, title, note
PROCESS_RULES: list[tuple[str, str, str, str]] = [
    ("chrome.exe", "Browser", "Google Chrome", "Google Chrome is listening so its own windows on this PC can talk to each other."),
    ("msedge.exe", "Browser", "Microsoft Edge", "Microsoft Edge is listening so its own windows on this PC can talk to each other."),
    ("firefox.exe", "Browser", "Firefox", "Firefox is listening so its own windows on this PC can talk to each other."),
    ("brave.exe", "Browser", "Brave", "Brave is listening so its own windows on this PC can talk to each other."),
    ("opera.exe", "Browser", "Opera", "Opera is listening so its own windows on this PC can talk to each other."),
    ("cursor.exe", "Development", "Cursor", "Cursor, the code editor, is listening so the editor and its tools on this PC can talk to each other."),
    ("code.exe", "Development", "Visual Studio Code", "Visual Studio Code is listening so the editor and its tools on this PC can talk to each other."),
    ("devenv.exe", "Development", "Visual Studio", "Visual Studio is listening for its own local tools."),
    ("node.exe", "Development", "Node.js", "Node.js is running. This is usually a development server or a tool you started."),
    ("python.exe", "Development", "Python", "Python is running. This is usually a local web app, notebook, or script."),
    ("pythonw.exe", "Development", "Python", "Python is running without a console window. This is usually a local app."),
    ("com.docker", "Containers", "Docker Desktop", "Docker Desktop is listening. This is the container app, including its Linux backend."),
    ("docker", "Containers", "Docker", "Docker is listening. This is the container engine or one of its background services."),
    ("mdnsresponder.exe", "Network", "Bonjour", "Bonjour lets printers, Apple devices, and other machines on the local network find this PC."),
    ("postgres", "Database", "PostgreSQL", "PostgreSQL database is listening."),
    ("mysqld", "Database", "MySQL", "MySQL is listening."),
    ("mariadbd", "Database", "MariaDB", "MariaDB is listening."),
    ("redis-server", "Database", "Redis", "Redis is listening."),
    ("mongod", "Database", "MongoDB", "MongoDB is listening."),
    ("sqlservr", "Database", "SQL Server", "Microsoft SQL Server is listening."),
    ("nginx", "Web", "Nginx", "Nginx web server is listening."),
    ("httpd", "Web", "Apache", "Apache web server is listening."),
    ("caddy", "Web", "Caddy", "Caddy web server is listening."),
    ("java.exe", "Development", "Java", "A Java program is listening. That can be an IDE, a server, or another installed app."),
    ("javaw.exe", "Development", "Java", "A Java program is listening without a console window."),
    ("spoolsv.exe", "Windows", "Print spooler", "The Windows print spooler is listening. It handles printers."),
    ("lsass.exe", "Windows", "Windows sign-in", "The Windows sign-in process is listening. Leave it running."),
    ("services.exe", "Windows", "Service Control Manager", "Windows Service Control Manager is listening. It starts and watches Windows services."),
    ("wininit.exe", "Windows", "Windows startup", "A core Windows startup process is listening."),
    ("svchost.exe", "Windows", "Windows service", "A Windows service is listening. The service name below says which feature it is."),
    ("system", "Windows", "Windows system", "This socket belongs to Windows itself."),
    ("wsl.exe", "Development", "WSL", "Windows Subsystem for Linux is listening."),
    ("wslservice.exe", "Development", "WSL", "The WSL background service is listening."),
    ("wireguard", "VPN", "WireGuard", "WireGuard VPN is listening."),
    ("openvpn", "VPN", "OpenVPN", "OpenVPN is listening."),
    ("tailscale", "VPN", "Tailscale", "Tailscale is listening. It connects this PC to a private network."),
    ("nordvpn", "VPN", "NordVPN", "NordVPN is listening."),
    ("expressvpn", "VPN", "ExpressVPN", "ExpressVPN is listening."),
    ("anydesk", "Remote access", "AnyDesk", "AnyDesk remote desktop is listening."),
    ("teamviewer", "Remote access", "TeamViewer", "TeamViewer remote support is listening."),
    ("rustdesk", "Remote access", "RustDesk", "RustDesk remote desktop is listening."),
    ("discord", "Calls", "Discord", "Discord is listening for voice and chat on this PC."),
    ("zoom", "Calls", "Zoom", "Zoom is listening for meeting features on this PC."),
    ("teams", "Calls", "Microsoft Teams", "Microsoft Teams is listening for meeting features on this PC."),
    ("spotify", "Media", "Spotify", "Spotify is listening."),
    ("steam", "Media", "Steam", "Steam is listening."),
    ("onedrive", "Cloud", "OneDrive", "Microsoft OneDrive is listening."),
    ("dropbox", "Cloud", "Dropbox", "Dropbox is listening."),
    ("searchindexer", "Windows", "Windows Search", "Windows Search is listening while it indexes files."),
    ("explorer.exe", "Windows", "File Explorer", "File Explorer is listening."),
    ("dllhost.exe", "Windows", "Windows component", "A Windows component host is listening."),
    ("runtimebroker.exe", "Windows", "Windows app broker", "Windows is brokering permissions for an installed app."),
    ("msmpeng.exe", "Windows", "Microsoft Defender", "Microsoft Defender antivirus is listening."),
    ("nvidia", "Hardware", "NVIDIA software", "NVIDIA graphics software is listening."),
    ("intel", "Hardware", "Intel software", "Intel hardware helper software is listening."),
    ("amd", "Hardware", "AMD software", "AMD hardware helper software is listening."),
    ("realtek", "Hardware", "Realtek software", "Realtek audio or network software is listening."),
    ("lghub", "Hardware", "Logitech G HUB", "Logitech G HUB is listening for your Logitech devices."),
    ("razer", "Hardware", "Razer software", "Razer device software is listening."),
]

EXTRA_ADVICE = {
    "Remote access": "If you want this PC closed to remote control, turn that feature off in Windows settings or quit the remote-access app.",
    "File sharing": "This is how other computers on your network open shared folders and printers.",
    "Database": "Database ports are meant for apps on this PC or your home network. Keep them off the public internet.",
}

REACH_LABEL = {
    "loopback": "This PC only",
    "all-v4": "All IPv4 adapters",
    "all-v6": "All IPv6 adapters",
    "adapter": "This adapter",
    "linklocal": "Link-local only",
    "other": "This address",
}

REACH_SENTENCE = {
    "loopback": "Only this computer can connect.",
    "all-v4": "Every IPv4 adapter on this PC answers here, so other devices on your Wi-Fi or LAN can try it. Windows Firewall can still block them. Reaching it from the internet also takes a port-forward rule on your router.",
    "all-v6": "Every IPv6 adapter on this PC answers here. Windows Firewall can still block other devices.",
    "adapter": "Only this network adapter answers here. Devices on that same network can try it, and Windows Firewall can still block them.",
    "linklocal": "Only the local link can reach this address.",
    "other": "Connections are limited to this address.",
}


def decode(data: bytes) -> str:
    if not data:
        return ""
    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16-le", errors="replace")
    if data.startswith(b"\xfe\xff"):
        return data.decode("utf-16-be", errors="replace")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace")
    if b"\x00" in data[:80]:
        return data.decode("utf-16-le", errors="replace")
    return data.decode("utf-8", errors="replace")


def run_cmd(args: list[str], timeout: int = 25) -> str:
    completed = subprocess.run(
        args,
        capture_output=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    return decode(completed.stdout)


def parse_json(text: str):
    text = text.strip()
    positions = [index for index in (text.find("{"), text.find("[")) if index >= 0]
    if not positions:
        return None
    try:
        return json.loads(text[min(positions) :])
    except json.JSONDecodeError:
        return None


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def norm_ip(value: str) -> str:
    value = (value or "").strip().lower()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if "%" in value:
        value = value.split("%", 1)[0]
    return value


def split_local(endpoint: str) -> tuple[str, int]:
    if endpoint.startswith("["):
        host, port = endpoint[1:].rsplit("]:", 1)
    else:
        host, port = endpoint.rsplit(":", 1)
    return host, int(port)


def address_scope(host: str) -> str:
    bare = norm_ip(host)
    if bare in {"0.0.0.0", "*"}:
        return "all-v4"
    if bare == "::":
        return "all-v6"
    try:
        parsed = ipaddress.ip_address(bare)
    except ValueError:
        return "other"
    if parsed.is_loopback:
        return "loopback"
    if parsed.is_link_local:
        return "linklocal"
    return "adapter"


def describe_interface(alias: str) -> str:
    name = (alias or "").lower()
    if "docker" in name:
        return "Virtual network for Docker"
    if "wsl" in name:
        return "Virtual network for Windows Subsystem for Linux"
    if any(word in name for word in ("vpn", "wireguard", "tailscale", "nordlynx", "openvpn", "wintun", "tap-windows")):
        return "VPN network"
    if "bluetooth" in name:
        return "Bluetooth network"
    if any(word in name for word in ("wi-fi", "wifi", "wireless", "wlan")):
        return "Wi-Fi network"
    if "vethernet" in name or "hyper-v" in name or "virtual" in name:
        return "Virtual network adapter"
    if "ethernet" in name:
        return "Wired network"
    if alias:
        return f"Network adapter ({alias})"
    return "Network adapter on this PC"


def primary_ipv4() -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def family_of(item: dict, ip: str) -> str:
    family = item.get("AddressFamily")
    if family in (2, "2", "IPv4"):
        return "IPv4"
    if family in (23, "23", "IPv6"):
        return "IPv6"
    return "IPv6" if ":" in ip else "IPv4"


def read_internal() -> list[dict]:
    primary = primary_ipv4()
    found: list[dict] = []
    try:
        text = run_cmd(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-NetIPAddress | Select-Object IPAddress, AddressFamily, InterfaceAlias | ConvertTo-Json -Compress",
            ]
        )
        for item in as_list(parse_json(text)):
            ip = str(item.get("IPAddress") or "").strip()
            bare = norm_ip(ip)
            if not bare or bare.startswith("127.") or bare in {"::1", "0.0.0.0", "::"}:
                continue
            if bare.startswith("fe80:"):
                continue
            alias = str(item.get("InterfaceAlias") or "")
            found.append(address_record(ip, alias, family_of(item, ip), primary))
    except (OSError, subprocess.TimeoutExpired):
        found = []

    if not found:
        hostname = socket.gethostname()
        try:
            infos = socket.getaddrinfo(hostname, None)
        except OSError:
            infos = []
        seen: set[str] = set()
        for info in infos:
            ip = info[4][0]
            bare = norm_ip(ip)
            if not bare or bare.startswith("127.") or bare in {"::1"} or bare.startswith("fe80:") or bare in seen:
                continue
            seen.add(bare)
            family = "IPv6" if ":" in ip else "IPv4"
            found.append(address_record(ip, "This PC", family, primary))
        if primary and norm_ip(primary) not in seen:
            found.insert(0, address_record(primary, "This PC", "IPv4", primary))

    deduped: list[dict] = []
    seen_ips: set[str] = set()
    for item in found:
        bare = norm_ip(item["ip"])
        if bare in seen_ips:
            continue
        seen_ips.add(bare)
        deduped.append(item)
    deduped.sort(key=lambda item: (not item["configured"], not item["primary"], item["family"] != "IPv4", item["ip"]))
    return deduped


def address_record(ip: str, alias: str, family: str, primary: str | None) -> dict:
    bare = norm_ip(ip)
    unconfigured = bare.startswith("169.254.")
    try:
        unconfigured = ipaddress.ip_address(bare).is_link_local
    except ValueError:
        pass
    return {
        "ip": ip,
        "interface": alias,
        "family": family,
        "network": "No DHCP address on this adapter" if unconfigured else describe_interface(alias),
        "primary": bool(primary and norm_ip(str(primary)) == bare and not unconfigured),
        "configured": not unconfigured,
    }


def read_external() -> dict:
    request = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "port-check"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            ip = response.read().decode().strip()
        ipaddress.ip_address(ip)
    except (OSError, urllib.error.URLError, ValueError, TimeoutError):
        return {"ip": None, "error": "Public address lookup needs an internet connection."}
    return {"ip": ip, "error": None}


def read_processes() -> dict[int, str]:
    if os.name != "nt":
        names: dict[int, str] = {}
        proc = Path("/proc")
        if not proc.exists():
            return names
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                names[int(entry.name)] = (entry / "comm").read_text(encoding="utf-8").strip()
            except OSError:
                continue
        return names
    try:
        text = run_cmd(["tasklist", "/FO", "CSV", "/NH"])
    except (OSError, subprocess.TimeoutExpired):
        return {}
    mapping: dict[int, str] = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2 or not row[1].isdigit():
            continue
        mapping[int(row[1])] = row[0]
    return mapping


def read_services() -> dict[int, list[str]]:
    try:
        text = run_cmd(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-CimInstance Win32_Service | Select-Object ProcessId, DisplayName | ConvertTo-Json -Compress",
            ]
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    grouped: dict[int, list[str]] = {}
    for item in as_list(parse_json(text)):
        try:
            pid = int(item.get("ProcessId") or 0)
        except (TypeError, ValueError):
            continue
        name = str(item.get("DisplayName") or "").strip()
        if pid and name and name not in grouped.setdefault(pid, []):
            grouped[pid].append(name)
    return grouped


def parse_netstat(text: str) -> tuple[list[dict], list[dict]]:
    tcp: list[dict] = []
    udp: list[dict] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        proto = parts[0].upper()
        try:
            if proto == "TCP" and len(parts) >= 5 and parts[3].upper() == "LISTENING" and parts[4].isdigit():
                host, port = split_local(parts[1])
                tcp.append({"protocol": "TCP", "address": host, "port": port, "pid": int(parts[4])})
            elif proto == "UDP" and parts[-1].isdigit() and ":" in parts[1]:
                host, port = split_local(parts[1])
                udp.append({"protocol": "UDP", "address": host, "port": port, "pid": int(parts[-1])})
        except (ValueError, IndexError):
            continue
    return tcp, udp


def decode_proc_ip(hex_ip: str, ipv6: bool) -> str:
    raw = bytes.fromhex(hex_ip)
    if not ipv6:
        return socket.inet_ntoa(raw[::-1])
    words = b"".join(raw[index : index + 4][::-1] for index in range(0, 16, 4))
    return socket.inet_ntop(socket.AF_INET6, words)


def linux_socket_owners() -> dict[str, int]:
    owners: dict[str, int] = {}
    proc = Path("/proc")
    if not proc.exists():
        return owners
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        fd_dir = entry / "fd"
        try:
            descriptors = list(fd_dir.iterdir())
        except OSError:
            continue
        for descriptor in descriptors:
            try:
                target = os.readlink(descriptor)
            except OSError:
                continue
            if target.startswith("socket:[") and target.endswith("]"):
                owners[target[8:-1]] = int(entry.name)
    return owners


def read_proc_sockets(path: str, ipv6: bool, protocol: str, listening_only: bool, owners: dict[str, int]) -> list[dict]:
    rows: list[dict] = []
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[1:]
    except OSError:
        return rows
    for line in lines:
        parts = line.split()
        if len(parts) < 10 or ":" not in parts[1]:
            continue
        if listening_only and parts[3] != "0A":
            continue
        ip_hex, port_hex = parts[1].split(":", 1)
        try:
            rows.append(
                {
                    "protocol": protocol,
                    "address": decode_proc_ip(ip_hex, ipv6),
                    "port": int(port_hex, 16),
                    "pid": owners.get(parts[9], 0),
                }
            )
        except (ValueError, OSError):
            continue
    return rows


def linux_listeners() -> tuple[list[dict], list[dict]]:
    owners = linux_socket_owners()
    tcp = read_proc_sockets("/proc/net/tcp", False, "TCP", True, owners)
    tcp.extend(read_proc_sockets("/proc/net/tcp6", True, "TCP", True, owners))
    udp = read_proc_sockets("/proc/net/udp", False, "UDP", False, owners)
    udp.extend(read_proc_sockets("/proc/net/udp6", True, "UDP", False, owners))
    return tcp, udp


def read_sockets() -> tuple[list[dict], list[dict]]:
    if os.name != "nt":
        return linux_listeners()
    try:
        tcp, udp = parse_netstat(run_cmd(["netstat", "-ano"], timeout=20))
    except (OSError, subprocess.TimeoutExpired):
        tcp, udp = [], []
    if tcp:
        return tcp, udp
    try:
        text = run_cmd(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-NetTCPConnection -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess | ConvertTo-Json -Compress",
            ]
        )
    except (OSError, subprocess.TimeoutExpired):
        return tcp, udp
    for item in as_list(parse_json(text)):
        try:
            tcp.append(
                {
                    "protocol": "TCP",
                    "address": str(item.get("LocalAddress") or ""),
                    "port": int(item["LocalPort"]),
                    "pid": int(item.get("OwningProcess") or 0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tcp, udp


GENERIC_WINDOWS = {"svchost.exe", "system", "lsass.exe", "services.exe", "wininit.exe", "spoolsv.exe"}
PORT_HINT_CATEGORIES = {"Remote access", "Database", "File sharing", "Web", "VPN", "Mail"}


def token_match(name: str, token: str) -> bool:
    if name == token or name == f"{token}.exe":
        return True
    start = name.find(token)
    if start < 0 or len(token) < 3:
        return False
    end = start + len(token)
    before_ok = start == 0 or not name[start - 1].isalnum()
    after_ok = end == len(name) or not name[end].isalnum()
    return before_ok and after_ok


def normalize_process(name: str) -> str:
    name = name.lower()
    if not name.endswith(".exe"):
        return name
    stem = name[:-4]
    cut = len(stem)
    while cut > 0 and (stem[cut - 1].isdigit() or stem[cut - 1] == "."):
        cut -= 1
    if cut and cut < len(stem) and stem[cut - 1].isalpha():
        return stem[:cut] + ".exe"
    return name


def process_rule(process: str) -> tuple[str, str, str] | None:
    name = normalize_process(process or "")
    if not name:
        return None
    matches: list[tuple[int, str, str, str]] = []
    for key, category, title, note in PROCESS_RULES:
        token = key.lower()
        if token_match(name, token):
            matches.append((len(token), category, title, note))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1], matches[0][2], matches[0][3]


def category_from_text(text: str) -> str:
    name = text.lower()
    if any(word in name for word in ("bonjour", "mdns", "dns")):
        return "Network"
    if any(word in name for word in ("intel", "nvidia", "amd", "realtek", "logitech")):
        return "Hardware"
    if "docker" in name or "container" in name:
        return "Containers"
    if any(word in name for word in ("sql", "postgres", "mysql", "redis", "mongo")):
        return "Database"
    if any(word in name for word in ("remote desktop", "teamviewer", "anydesk", "rustdesk")):
        return "Remote access"
    return "Windows"


def describe_socket(row: dict, process: str, services: list[str], interface: dict | None) -> dict:
    port = row["port"]
    scope = address_scope(row["address"])
    known = PORT_INFO.get(port)
    rule = process_rule(process)
    ephemeral = 49152 <= port <= 65535
    generic = process.lower() in GENERIC_WINDOWS
    app_rule = rule if rule and rule[0] != "Windows" else None
    parts: list[str] = []
    checker = port == PORT and scope == "loopback" and normalize_process(process).startswith("python")

    if checker:
        title = "Open ports checker"
        category = "Development"
        parts.append("This is the checker you are using.")
    elif app_rule:
        category, title, note = app_rule
        parts.append(note)
        if known and known[2] in PORT_HINT_CATEGORIES and known[2] != category:
            parts.append(f"Port {port} is the usual {known[0]} port. Here it is {title}.")
    elif services and not generic:
        title = services[0]
        category = category_from_text(f"{services[0]} {process}")
        parts.append(f"{services[0]} is listening.")
        if ephemeral:
            parts.append("Windows assigned this high port, and the number can change after a restart.")
    elif known and (generic or rule is None):
        title, detail, category = known
        parts.append(detail)
        if rule and rule[0] == "Windows" and not ephemeral and not services and "windows" not in detail.lower():
            parts.append(rule[2])
    elif known:
        title, detail, category = known
        parts.append(detail)
    elif rule:
        category, title, note = rule
        parts.append(note)
        if ephemeral:
            parts.append("Windows assigned this high port, and the number can change after a restart.")
    elif services:
        title = services[0]
        category = category_from_text(services[0])
        parts.append(f"{services[0]} is listening.")
    else:
        title = process or "Unknown program"
        category = "Other"
        parts.append("This port number is not a well-known service. The program name is the best clue.")

    joined = " ".join(services).lower()
    if services and title.lower() not in joined and not any(name.lower() in title.lower() for name in services):
        shown = services[:6]
        extra = len(services) - len(shown)
        service_text = ", ".join(shown)
        if extra > 0:
            service_text += f", and {extra} more"
        parts.append(f"Windows services in this process: {service_text}.")

    if interface:
        parts.append(f"Network: {interface['network']} ({interface['interface']}).")
    parts.append(REACH_SENTENCE[scope])
    if category in EXTRA_ADVICE and scope != "loopback":
        parts.append(EXTRA_ADVICE[category])

    return {
        "protocol": row["protocol"],
        "address": row["address"],
        "port": port,
        "pid": row["pid"],
        "process": process or "Unknown",
        "services": services[:8],
        "title": title,
        "category": category,
        "advice": " ".join(parts),
        "reach": scope,
        "reach_label": REACH_LABEL[scope],
        "interface": interface["interface"] if interface else "",
        "network": interface["network"] if interface else "",
    }


def applies(address: str, kind: str, query: str) -> bool:
    scope = address_scope(address)
    host = norm_ip(address)
    if kind in {"all", "unknown"}:
        return True
    if kind == "external":
        return scope != "loopback"
    if kind == "loopback":
        return scope in {"loopback", "all-v4", "all-v6"}
    if host == norm_ip(query):
        return True
    if ":" in norm_ip(query):
        return scope == "all-v6"
    return scope in {"all-v4", "all-v6"}


def classify_query(query: str, internal: list[dict], external_ip: str | None) -> str:
    if not query:
        return "all"
    if query.lower() == "localhost":
        return "loopback"
    bare = norm_ip(query)
    try:
        ipaddress.ip_address(bare)
    except ValueError:
        return "unknown"
    if bare in {"127.0.0.1", "::1"}:
        return "loopback"
    if external_ip and bare == norm_ip(external_ip):
        return "external"
    if any(norm_ip(item["ip"]) == bare for item in internal):
        return "internal"
    return "unknown"


def banner_for(kind: str, query: str, internal: list[dict], external_ip: str | None, shown: int, total: int) -> str:
    if kind == "all":
        return (
            f"Showing all {total} TCP listeners on this computer. "
            'That is the same list as netstat -ano | find "LISTEN".'
        )
    if kind == "unknown":
        return (
            "This page reads listeners on this computer only. "
            f"{query} is outside this computer, so the table stays on the local netstat list ({total} TCP listeners)."
        )
    if kind == "external":
        return (
            f"{external_ip} is the public address other networks see. It belongs to your router or ISP connection. "
            f"Showing {shown} listeners on a real adapter or on every adapter. "
            "The internet can reach one of them when your router forwards that port and Windows Firewall allows it. "
            "Use Show all to include listeners that stay on this PC."
        )
    if kind == "loopback":
        return (
            "127.0.0.1 is the address this computer uses to talk to itself. "
            f"Showing {shown} listeners reachable that way. "
            "Rows marked “This PC only” stay on this machine. Rows marked “All adapters” also answer on your other addresses."
        )
    match = next((item for item in internal if norm_ip(item["ip"]) == norm_ip(query)), None)
    where = "this computer"
    if match:
        where = f"{match['interface']}: {match['network']}"
    return (
        f"{query} is an address on this computer ({where}). "
        f"Showing {shown} of {total} listeners that accept connections on it, "
        "including programs bound to every adapter."
    )


def enrich(rows: list[dict], processes: dict[int, str], services: dict[int, list[str]], internal: list[dict], kind: str, query: str) -> list[dict]:
    by_ip = {norm_ip(item["ip"]): item for item in internal}
    enriched = []
    for row in rows:
        if not applies(row["address"], kind, query):
            continue
        process = processes.get(row["pid"], "Unknown" if row["pid"] else "Windows")
        enriched.append(
            describe_socket(
                row,
                process,
                services.get(row["pid"], []),
                by_ip.get(norm_ip(row["address"])),
            )
        )
    enriched.sort(key=lambda item: (item["port"], item["address"]))
    return enriched


CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.IGNORECASE)
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0?cveId="
CATALOG_UA = "port-check/1.0 (local exposure check)"

# Practical exposure advice. CVE examples are added only when a catalog
# entry matches the program or Shodan has listed that CVE on this public address.
HIGH_RISK_PORTS = {21, 22, 23, 135, 139, 445, 1433, 3306, 3389, 5432, 5900, 5985, 5986, 6379, 27017}
ADVISORIES: dict[int, tuple[str, str, str]] = {
    21: (
        "Turn the FTP server off, or replace it with a current file-transfer service that uses encryption. Do not forward port 21 on the router.",
        "CISA and NIST",
        "FTP sends logins without encryption. CISA KEV and NIST NVD both track file-transfer flaws that are exploited when the service is reachable.",
    ),
    22: (
        "Keep the SSH server updated, allow it only from networks you trust, and use keys instead of passwords.",
        "CISA and NIST",
        "OpenSSH vulnerabilities in CISA's Known Exploited Vulnerabilities catalog are used against SSH that is reachable from the internet.",
    ),
    23: (
        "Turn Telnet off. Use SSH if you need remote login.",
        "CISA and NIST",
        "Telnet has no encryption. NIST and CISA treat exposed Telnet as an unsafe remote-login service.",
    ),
    135: (
        "Leave Windows Update on. Do not forward port 135 on the router, and let Windows Firewall block it on networks you do not trust.",
        "CISA and Microsoft",
        "Port 135 is Windows RPC, a built-in service. CISA KEV includes Windows vulnerabilities attackers use against exposed management services. An open port is not, by itself, proof of an unpatched CVE.",
    ),
    139: (
        "Turn off network discovery on networks you do not trust, and do not forward NetBIOS ports on the router.",
        "Microsoft and CISA",
        "NetBIOS supports file sharing on the local network. CISA's exposure guidance is to keep Windows file services off the public internet.",
    ),
    445: (
        "Keep Windows updated, leave SMBv1 off, and do not forward port 445. Share folders only on your home network.",
        "CISA and Microsoft",
        "Exposed SMB is a common ransomware path. CISA KEV lists Windows SMB vulnerabilities that are already exploited. This check did not read the installed patch level.",
    ),
    1433: (
        "Keep SQL Server updated and do not publish port 1433 on the router. Let only this PC, or a private network, connect.",
        "Microsoft and CISA",
        "CISA KEV includes Microsoft SQL Server vulnerabilities. Database ports are meant for applications, not for the public internet.",
    ),
    3306: (
        "Keep MySQL or MariaDB updated and do not forward port 3306.",
        "CISA and the database vendor",
        "CISA KEV and NIST NVD track MySQL and MariaDB flaws. A database listening on a network adapter should stay off the public internet.",
    ),
    3389: (
        "Do not forward Remote Desktop. If you use it, turn on Network Level Authentication, keep Windows updated, and reach it through a VPN.",
        "CISA and Microsoft",
        "CISA KEV includes Remote Desktop vulnerabilities that are already used in attacks. Those warnings apply when Windows Remote Desktop is reachable from other networks.",
    ),
    5432: (
        "Keep PostgreSQL updated and do not forward port 5432.",
        "CISA and the PostgreSQL project",
        "Database ports in NIST's CVE records are a risk when other networks can connect. This check did not confirm an unpatched version.",
    ),
    5900: (
        "Turn VNC off if you do not use remote screen sharing. If you do, require a password and do not forward the port.",
        "CISA and NIST",
        "VNC products appear in CISA KEV. Screen-sharing ports give control of the desktop when they are reachable.",
    ),
    5985: (
        "Keep Windows updated and do not expose WinRM. Allow remote management only from an admin network you trust.",
        "Microsoft and CISA",
        "WinRM is Windows remote management. CISA treats exposed management services as a priority to patch and to keep off the public internet.",
    ),
    5986: (
        "Keep Windows updated and do not expose WinRM. Allow remote management only from an admin network you trust.",
        "Microsoft and CISA",
        "WinRM over HTTPS is still a management service. CISA's guidance is to patch it and limit who can connect.",
    ),
    6379: (
        "Set a Redis password or bind Redis to this PC, and do not forward port 6379.",
        "CISA and the Redis project",
        "Open Redis has a long record in NIST NVD. CISA KEV has included caching-service flaws that matter when the port is reachable.",
    ),
    27017: (
        "Turn on MongoDB authentication and do not forward port 27017.",
        "CISA and MongoDB",
        "MongoDB instances without authentication are a known exposure. NIST CVE records for MongoDB apply when other networks can connect.",
    ),
}
PORT_TERMS: dict[int, tuple[str, ...]] = {
    21: ("ftp",),
    22: ("openssh", "ssh"),
    23: ("telnet",),
    135: ("remote procedure call",),
    139: ("smb", "netbios"),
    445: ("smb",),
    1433: ("sql server",),
    3306: ("mysql", "mariadb"),
    3389: ("remote desktop",),
    5432: ("postgresql", "postgres"),
    5900: ("vnc",),
    5985: ("winrm", "windows remote management"),
    5986: ("winrm", "windows remote management"),
    6379: ("redis",),
    27017: ("mongodb", "mongo"),
}
PROCESS_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("chrome", ("chrome", "chromium")),
    ("msedge", ("microsoft edge", "edge")),
    ("firefox", ("firefox",)),
    ("docker", ("docker",)),
    ("postgres", ("postgresql", "postgres")),
    ("mysql", ("mysql", "mariadb")),
    ("redis", ("redis",)),
    ("mongod", ("mongodb",)),
    ("sqlservr", ("sql server",)),
)

_KEV_LOCK = threading.Lock()
_KEV: dict = {"at": 0.0, "by_cve": {}, "count": 0, "error": None}
_NVD_LOCK = threading.Lock()
_NVD: dict[str, dict | None] = {}


def catalog_json(url: str, timeout: int = 20):
    request = urllib.request.Request(url, headers={"User-Agent": CATALOG_UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def load_kev() -> dict:
    with _KEV_LOCK:
        if _KEV["by_cve"] and time.monotonic() - _KEV["at"] < 6 * 3600:
            return _KEV
        try:
            payload = catalog_json(KEV_URL, timeout=25)
            by_cve = {}
            for item in payload.get("vulnerabilities") or []:
                cve = str(item.get("cveID") or "").upper()
                if not CVE_RE.match(cve):
                    continue
                summary = str(item.get("shortDescription") or "").strip()
                sentence = summary.split(". ")[0].strip()
                if sentence and not sentence.endswith("."):
                    sentence += "."
                if len(sentence) > 240:
                    sentence = sentence[:237].rstrip() + "..."
                summary = sentence
                by_cve[cve] = {
                    "cve": cve,
                    "name": str(item.get("vulnerabilityName") or "").strip(),
                    "product": str(item.get("product") or "").strip(),
                    "vendor": str(item.get("vendorProject") or "").strip(),
                    "action": str(item.get("requiredAction") or "Apply the vendor security update.").strip(),
                    "summary": summary,
                    "date": str(item.get("dateAdded") or ""),
                }
            _KEV.update(at=time.monotonic(), by_cve=by_cve, count=len(by_cve), error=None)
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            if not _KEV["by_cve"]:
                _KEV["error"] = "CISA's Known Exploited Vulnerabilities catalog could not be downloaded."
        return _KEV


def load_shodan(public_ip: str | None) -> dict:
    empty = {"ip": public_ip, "ports": [], "vulns": [], "found": False, "error": None}
    if not public_ip:
        empty["error"] = "No public address to look up in Shodan InternetDB."
        return empty
    try:
        parsed = ipaddress.ip_address(public_ip)
    except ValueError:
        empty["error"] = "The public address was not a valid IP, so Shodan was not queried."
        return empty
    if parsed.is_private or parsed.is_loopback or parsed.is_link_local:
        empty["error"] = "Shodan InternetDB is for the public address, and this value is a local address."
        return empty
    try:
        payload = catalog_json(f"https://internetdb.shodan.io/{public_ip}", timeout=12)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return empty
        empty["error"] = "Shodan InternetDB did not respond."
        return empty
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        empty["error"] = "Shodan InternetDB did not respond."
        return empty
    vulns = []
    for vuln in payload.get("vulns") or []:
        cve = str(vuln).upper()
        if CVE_RE.match(cve):
            vulns.append(cve)
    ports = []
    for port in payload.get("ports") or []:
        try:
            ports.append(int(port))
        except (TypeError, ValueError):
            continue
    return {"ip": public_ip, "ports": ports, "vulns": vulns, "found": True, "error": None}


def fetch_nvd(cve: str) -> dict | None:
    try:
        payload = catalog_json(NVD_URL + cve, timeout=15)
    except urllib.error.HTTPError as exc:
        if exc.code in {403, 429}:
            raise
        return None
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
    vulnerabilities = payload.get("vulnerabilities") or []
    if not vulnerabilities:
        return None
    record = vulnerabilities[0].get("cve") or {}
    summary = ""
    for description in record.get("descriptions") or []:
        if description.get("lang") == "en":
            summary = str(description.get("value") or "").strip()
            break
    sentence = summary.split(". ")[0].strip()
    if sentence and not sentence.endswith("."):
        sentence += "."
    if len(sentence) > 240:
        sentence = sentence[:237].rstrip() + "..."
    return {"cve": cve, "summary": sentence}


def lookup_nvd(cve_ids: list[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    missing: list[str] = []
    with _NVD_LOCK:
        for cve in cve_ids:
            cached = _NVD.get(cve)
            if cached:
                found[cve] = cached
            elif cve not in _NVD:
                missing.append(cve)
    for cve in missing[:5]:
        try:
            detail = fetch_nvd(cve)
        except urllib.error.HTTPError:
            break
        with _NVD_LOCK:
            _NVD[cve] = detail
        if detail:
            found[cve] = detail
        time.sleep(0.6)
    return found


def row_terms(item: dict) -> tuple[str, ...]:
    terms = list(PORT_TERMS.get(item["port"], ()))
    process = item["process"].lower()
    title = item["title"].lower()
    for needle, words in PROCESS_TERMS:
        if needle in process or needle in title:
            terms.extend(words)
    return tuple(dict.fromkeys(terms))


def related_kevs(item: dict, kev_by_cve: dict, shodan_vulns: set[str]) -> list[dict]:
    terms = row_terms(item)
    if not terms:
        return []
    hits = []
    for record in kev_by_cve.values():
        blob = f"{record['vendor']} {record['product']} {record['name']}".lower()
        if any(term in blob for term in terms):
            hits.append(record)
    hits.sort(key=lambda record: record["date"], reverse=True)
    on_shodan = [record for record in hits if record["cve"] in shodan_vulns]
    if on_shodan:
        return on_shodan[:2]
    if item["port"] in HIGH_RISK_PORTS and item["reach"] != "loopback":
        return hits[:2]
    return []


def remediation_for(item: dict, kev_by_cve: dict, shodan: dict, nvd: dict[str, dict]) -> dict:
    port = item["port"]
    scope = item["reach"]
    process = item["process"].lower()
    exposed = scope != "loopback"
    shodan_ports = set(shodan.get("ports") or [])
    shodan_vulns = set(shodan.get("vulns") or [])
    public_ip = shodan.get("ip") or "the public address"
    seen = port in shodan_ports
    findings: list[dict] = []
    used: list[str] = []

    def add(source: str, action: str, why: str, cve: str = "", url: str = "") -> None:
        findings.append({"source": source, "action": action, "why": why, "cve": cve, "url": url})
        if cve:
            used.append(cve.upper())

    def result(level: str, label: str, action: str, who: str, why: str) -> dict:
        if any(finding["source"] == "CISA KEV" for finding in findings):
            why += " The CVE names are related catalog entries, not a test of the version installed on this PC."
        return {
            "level": level,
            "level_label": label,
            "remediation": action,
            "recommended_by": who,
            "why": why,
            "findings": findings[:4],
            "cves": used,
        }

    if port == PORT and scope == "loopback" and normalize_process(item["process"]).startswith("python"):
        return result(
            "ok",
            "This PC only",
            "Quit this checker when you are finished. Leave it bound to 127.0.0.1.",
            "This checker",
            "CISA KEV, NIST NVD, and Shodan describe services other networks can reach. This page answers only on this computer.",
        )

    if port == 3389 and "docker" in process and not exposed:
        return result(
            "ok",
            "This PC only",
            "Keep Docker Desktop updated. No router change is needed for this socket.",
            "Docker",
            "Port 3389 is the usual Remote Desktop port. CISA KEV tracks exploited Remote Desktop flaws for Windows Remote Desktop that other networks can reach. This listener is Docker, and it stays on this PC.",
        )

    if not exposed and seen:
        add(
            "Shodan InternetDB",
            "Check the router for a forward of this port number.",
            f"Shodan has observed port {port} on {public_ip}. The listener on this PC is limited to this computer, so the public observation points at the router or another device.",
        )
        return result(
            "watch",
            "Check the router",
            "This program listens only on this PC. The same port number is in Shodan's record of the public address, so review the router's port forwards.",
            "Shodan InternetDB",
            "Shodan InternetDB is a public observation of an address, not a live attack scan. A matching port number means that number was seen on the public address.",
        )

    if not exposed:
        return result(
            "ok",
            "This PC only",
            "No internet exposure to close. Keep this program updated.",
            "CISA, NIST, and Shodan",
            "Those catalogs describe services other networks can reach. This socket answers only on this computer, so they are not reporting it as an exposed vulnerability.",
        )

    for record in related_kevs(item, kev_by_cve, shodan_vulns):
        cve = record["cve"]
        add(
            "CISA KEV",
            record["action"],
            f"{record['vendor']} {record['product']}: {record['name']}. {record['summary']}".strip(),
            cve,
            f"https://nvd.nist.gov/vuln/detail/{cve}",
        )

    terms = row_terms(item)
    for cve, detail in nvd.items():
        if cve in used or cve not in shodan_vulns:
            continue
        summary = detail.get("summary") or ""
        if terms and any(term in summary.lower() for term in terms):
            add(
                "NIST NVD",
                "Apply the vendor update named for this CVE.",
                summary,
                cve,
                f"https://nvd.nist.gov/vuln/detail/{cve}",
            )

    if seen:
        add(
            "Shodan InternetDB",
            "Remove a port-forward rule for this port unless you intend to publish the service.",
            f"Shodan has observed port {port} on {public_ip}.",
        )

    advisory = ADVISORIES.get(port)
    if advisory and (port in HIGH_RISK_PORTS or seen):
        action, who, why = advisory
        level = "action"
        label = "Public record" if seen else "Keep it private"
        if "docker" in process and port == 3389:
            action = "Keep Docker Desktop updated. Confirm the router is not forwarding port 3389 to this PC."
            who = "Docker, plus CISA for Remote Desktop"
            why = "This listener is Docker on a port number CISA warns about for Windows Remote Desktop. Treat a public forward of 3389 as Remote Desktop exposure until you confirm it is not."
        return result(level, label, action, who, why)

    if seen:
        return result(
            "action",
            "Public record",
            f"Shodan has seen port {port} on the public address. Remove a forward for it unless you meant to publish this service, and keep the program updated.",
            "Shodan InternetDB",
            "A port in the Shodan InternetDB record has been observed from the internet. That shows exposure. It is not automatic proof of an unpatched CVE.",
        )

    if 49152 <= port <= 65535 and item["category"] == "Windows":
        return result(
            "watch",
            "Keep it private",
            "Keep Windows Update on, and do not create a router forward for this port.",
            "Microsoft",
            "Windows assigned this high port to a built-in service. CISA KEV and NIST NVD need a product version before they name a CVE. None was confirmed for this socket.",
        )

    return result(
        "watch",
        "Keep it private",
        "Keep the program updated and do not forward this port on the router.",
        "CISA and Microsoft",
        "CISA's standing advice is to patch software other networks can reach and to remove exposure you do not need. No CVE from CISA KEV, NIST NVD, or Shodan was tied to this socket.",
    )


def attach_remediation(items: list[dict], kev_by_cve: dict, shodan: dict, nvd: dict[str, dict]) -> None:
    for item in items:
        item.update(remediation_for(item, kev_by_cve, shodan, nvd))


_RAW: dict = {}
_RAW_AT = 0.0
_RAW_LOCK = threading.Lock()


def raw_snapshot() -> dict:
    global _RAW_AT
    with _RAW_LOCK:
        if _RAW and time.monotonic() - _RAW_AT < 60:
            return _RAW
        with ThreadPoolExecutor(max_workers=6) as pool:
            sockets_future = pool.submit(read_sockets)
            process_future = pool.submit(read_processes)
            service_future = pool.submit(read_services)
            internal_future = pool.submit(read_internal)
            external_future = pool.submit(read_external)
            kev_future = pool.submit(load_kev)
            tcp, udp = sockets_future.result()
            processes = process_future.result()
            services = service_future.result()
            internal = internal_future.result()
            external = external_future.result()
            kev = kev_future.result()
            shodan = load_shodan(external.get("ip"))
        _RAW.clear()
        _RAW.update(
            {
                "tcp": tcp,
                "udp": udp,
                "processes": processes,
                "services": services,
                "internal": internal,
                "external": external,
                "kev": kev,
                "shodan": shodan,
            }
        )
        _RAW_AT = time.monotonic()
        return _RAW


def scan(query: str) -> dict:
    query = (query or "").strip()
    if query.lower() == "localhost":
        query = "127.0.0.1"
    raw = raw_snapshot()
    tcp = raw["tcp"]
    udp = raw["udp"]
    processes = raw["processes"]
    services = raw["services"]
    internal = raw["internal"]
    external = raw["external"]
    kev = raw.get("kev") or {"by_cve": {}, "count": 0, "error": "CISA KEV was not loaded."}
    shodan = raw.get("shodan") or {"ports": [], "vulns": [], "found": False, "error": None, "ip": None}

    kind = classify_query(query, internal, external.get("ip"))
    catalog_query = HOSTED and bool(query) and is_public_ip(query) and kind == "unknown"
    message = None
    if catalog_query:
        shodan = load_shodan(query)
        listeners = []
        for row in published_sockets(shodan):
            known = PORT_INFO.get(row["port"])
            item = describe_socket(row, "Shodan InternetDB", [], None)
            item["process"] = "Shodan InternetDB"
            item["reach"] = "all-v4"
            item["reach_label"] = "Published record"
            item["title"] = known[0] if known else f"Port {row['port']}"
            item["category"] = known[2] if known else "Network"
            item["advice"] = (
                f"Shodan InternetDB lists port {row['port']} on {query}. "
                "QTerminator did not connect to that address."
            )
            listeners.append(item)
        udp_listeners = []
        if shodan.get("error"):
            message = shodan["error"]
        elif shodan.get("found") and listeners:
            message = (
                f"Published records for {query}. Shodan lists {len(listeners)} port numbers. "
                "QTerminator asked Shodan InternetDB, CISA KEV, and NIST NVD. It did not connect to that address."
            )
        elif shodan.get("found"):
            message = (
                f"Shodan has a record for {query} and did not list port numbers. "
                "QTerminator did not connect to that address."
            )
        else:
            message = (
                f"Shodan InternetDB has no published record for {query}. "
                "QTerminator did not connect to that address."
            )
        total_tcp = len(listeners)
    elif HOSTED and not query:
        listeners = []
        udp_listeners = []
        message = (
            "Enter your public IP address. QTerminator checks published Shodan, CISA KEV, and NIST records for that address. "
            "It does not connect to your computer."
        )
        total_tcp = 0
    else:
        listeners = enrich(tcp, processes, services, internal, kind, query)
        udp_listeners = enrich(udp, processes, services, internal, kind, query)
        total_tcp = len(tcp)
    kev_ids = set((kev.get("by_cve") or {}).keys())
    nvd = lookup_nvd([cve for cve in shodan.get("vulns") or [] if cve not in kev_ids])
    attach_remediation(listeners, kev.get("by_cve") or {}, shodan, nvd)
    attach_remediation(udp_listeners, kev.get("by_cve") or {}, shodan, nvd)
    used: set[str] = set()
    for item in listeners + udp_listeners:
        used.update(item.pop("cves", []))
    unmatched = [cve for cve in shodan.get("vulns") or [] if cve not in used]
    counts: dict[str, int] = {}
    for item in listeners:
        counts[item["category"]] = counts.get(item["category"], 0) + 1

    return {
        "hostname": socket.gethostname(),
        "internal": internal,
        "external": external,
        "query": query,
        "query_kind": kind,
        "message": message or banner_for(kind, query, internal, external.get("ip"), len(listeners), total_tcp),
        "total": total_tcp,
        "shown": len(listeners),
        "counts": counts,
        "listeners": listeners,
        "udp": udp_listeners,
        "feeds": {
            "kev_count": kev.get("count") or 0,
            "kev_error": kev.get("error"),
            "shodan_found": bool(shodan.get("found")),
            "shodan_error": shodan.get("error"),
            "shodan_ports": shodan.get("ports") or [],
            "shodan_vulns": (shodan.get("vulns") or [])[:12],
            "shodan_unmatched": unmatched[:8],
            "nvd_checked": list(nvd.keys()),
        },
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send(200, "text/plain; charset=utf-8", b"ok")
            return
        if parsed.path == "/":
            body = (ROOT / "index.html").read_bytes()
            self._send(200, "text/html; charset=utf-8", body)
            return
        if parsed.path == "/api/scan":
            ip = (parse_qs(parsed.query).get("ip") or [""])[0]
            try:
                payload = scan(ip)
                code = 200
            except Exception as exc:  # noqa: BLE001 - surface a short message to the page
                print(f"scan failed: {exc}")
                payload = {"error": "Could not read listeners on this computer."}
                code = 500
            body = json.dumps(payload).encode("utf-8")
            self._send(code, "application/json; charset=utf-8", body, {"Cache-Control": "no-store"})
            return
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self._send(404, "text/plain; charset=utf-8", b"Not found")

    def _send(self, code: int, content_type: str, body: bytes, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


def is_public_ip(value: str) -> bool:
    try:
        parsed = ipaddress.ip_address(norm_ip(value))
    except ValueError:
        return False
    return not (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_multicast
        or parsed.is_reserved
        or parsed.is_unspecified
    )


def published_sockets(shodan: dict) -> list[dict]:
    address = str(shodan.get("ip") or "")
    sockets = []
    for port in sorted(set(shodan.get("ports") or [])):
        sockets.append(
            {
                "protocol": "TCP",
                "address": address,
                "port": port,
                "pid": 0,
                "published": True,
            }
        )
    return sockets


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"QTerminator running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
