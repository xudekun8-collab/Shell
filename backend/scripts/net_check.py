"""打印本机 IPv4、8000 监听状态、网络位置类别与防火墙入站规则，真机联调排查用。"""
import socket
import subprocess

PORT = 8000
RULE_NAME = "elder_care_8000"

CATEGORY_MAP = {
    "Public": "公用",
    "Private": "专用",
    "DomainAuthenticated": "域",
}


def local_ipv4s() -> list[str]:
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return sorted(ips, key=lambda x: (x.startswith("127."), x))


def port_listening(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def network_profiles() -> list[tuple[str, str]]:
    """返回 [(名称, 类别英文)]；读不到返回空列表。"""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetConnectionProfile | ForEach-Object { $_.Name + '|' + $_.NetworkCategory }"],
            capture_output=True, timeout=10,
        ).stdout.decode("gbk", errors="replace")
        result = []
        for line in out.strip().splitlines():
            if "|" in line:
                name, cat = line.split("|", 1)
                result.append((name.strip(), cat.strip()))
        return result
    except Exception:
        return []


def firewall_rule_exists() -> bool | None:
    """True=存在，False=不存在，None=无法检测。"""
    try:
        out = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={RULE_NAME}"],
            capture_output=True, timeout=10,
        ).stdout.decode("gbk", errors="replace")
        if RULE_NAME in out:
            return True
        if "没有" in out or "No rules" in out:
            return False
        return None
    except Exception:
        return None


def main() -> None:
    ips = local_ipv4s()
    print("本机 IPv4 地址：")
    for ip in ips:
        print(" - " + ip)

    print(f"8000 端口状态：{'LISTENING' if port_listening(PORT) else '未监听'}")

    profiles = network_profiles()
    if profiles:
        print("网络位置：")
        for name, cat in profiles:
            zh = CATEGORY_MAP.get(cat, cat)
            print(f" - {name}（{zh}）")
            if cat == "Public":
                print("   注：公用网络下入站请求默认被防火墙拦")
    else:
        print("网络位置：无法检测（可能需要管理员权限）")

    rule = firewall_rule_exists()
    if rule is True:
        print(f"8000 端口入站规则：已存在（{RULE_NAME}）")
    elif rule is False:
        print("8000 端口入站规则：不存在")
    else:
        print("8000 端口入站规则：无法检测（可能需要管理员权限）")

    lan = next((ip for ip in ips if not ip.startswith("127.")), None)
    if lan:
        print(f"手机浏览器访问 http://{lan}:{PORT}/api/health 应返回 ok")

    print("若手机打不开 health，二选一（均需管理员权限）：")
    print(" 1. 把网络位置改为专用：设置 → 网络和 Internet → WLAN → 当前网络 → 网络配置文件选“专用”")
    print(f" 2. 运行 scripts/firewall_allow_8000.bat 放行 8000 端口入站")


if __name__ == "__main__":
    main()
