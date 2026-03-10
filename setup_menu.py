import json
import os
import platform
import shlex
import subprocess
import sys
from typing import Dict, List


MACOS_SETUP_COMMANDS: List[str] = [
    # Xcode Command Line Tools
    "xcode-select --install",
    # Homebrew install
    '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
    # wkhtmltopdf for macOS
    "curl -L https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-2/wkhtmltox-0.12.6-2.macos-cocoa.pkg -O",
    "sudo installer -pkg wkhtmltox-0.12.6-2.macos-cocoa.pkg -target ~",
    # Core packages
    "brew install git redis mariadb@11.8 pkg-config mariadb-connector-c",
]


DEBIAN_UBUNTU_SETUP_COMMANDS: List[str] = [
    # Cập nhật danh sách package
    "sudo apt update",
    # Sửa các phụ thuộc bị lỗi (đặc biệt khi wkhtmltox đang ở trạng thái half-configured)
    "sudo apt --fix-broken install -y || true",
    # Cài gói fonts thiếu cho wkhtmltox
    "sudo apt install -y xfonts-75dpi || true",
    # Core packages
    "sudo apt install -y git redis-server libmariadb-dev mariadb-server mariadb-client pkg-config",
    # Build tools cần cho compile Python packages (mysqlclient, v.v.)
    "sudo apt install -y build-essential python3-dev || true",
    # wkhtmltopdf dependencies
    "sudo apt install -y xvfb libfontconfig || true",
    # Gợi ý: người dùng cần tự tải file .deb wkhtmltopdf và cài bằng dpkg
]


COMMON_NODE_PYTHON_COMMANDS: List[str] = [
    # nvm + Node + Yarn
    "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash",
    # Sau khi cài nvm, cần load script nvm trước khi gọi nvm (đặc biệt trong WSL / shell không tương tác)
    "bash -lc 'export NVM_DIR=\"$HOME/.nvm\" && "
    "[ -s \"$NVM_DIR/nvm.sh\" ] && . \"$NVM_DIR/nvm.sh\" && "
    "nvm install 24 && node -v && npm install -g yarn'",
    # uv + Python
    "curl -LsSf https://astral.sh/uv/install.sh | sh",
    "bash -lc 'uv python install 3.14 --default'",
]


def get_bench_setup_commands(bench_name: str) -> List[str]:
    """
    Trả về danh sách lệnh setup bench với tên bench tùy chỉnh.
    """
    return [
        # Cài frappe-bench, nếu đã tồn tại thì dùng --force để overwrite, hoặc bỏ qua lỗi
        "bash -lc 'uv tool install frappe-bench 2>/dev/null || uv tool install frappe-bench --force 2>/dev/null || true'",
        "bash -lc 'bench --version'",
        "mkdir -p ~/frappe",
        # Dùng bash -lc và load nvm trước khi chạy bench init để đảm bảo Node/Yarn có trong PATH
        f"bash -lc 'export NVM_DIR=\"$HOME/.nvm\" && "
        f"[ -s \"$NVM_DIR/nvm.sh\" ] && . \"$NVM_DIR/nvm.sh\" && "
        f"cd ~/frappe && bench init {bench_name}'",
    ]


WKHTMLTOX_DIR = os.path.join(os.path.dirname(__file__), "wkhtmltox")
WKHTMLTOX_DEBS = {
    "jammy": "wkhtmltox_0.12.6.1-2.jammy_amd64.deb",
    "focal": "wkhtmltox_0.12.6-1.focal_amd64.deb",
}


RESET_COMMANDS: List[str] = [
    # Xoá nvm (Node/Yarn cài qua nvm)
    "rm -rf \"$HOME/.nvm\"",
    # Xoá uv và dữ liệu liên quan
    "rm -rf \"$HOME/.local/bin/uv\" \"$HOME/.local/share/uv\"",
    # Gỡ bench cài qua uv (nếu còn)
    "bash -lc 'uv tool uninstall frappe-bench || true'",
    # Xoá workspace frappe (bench init)
    "rm -rf \"$HOME/frappe\"",
    # Gỡ cloudflared (Cloudflare Tunnel) và cấu hình liên quan
    "sudo systemctl stop cloudflared 2>/dev/null || true",
    "sudo systemctl disable cloudflared 2>/dev/null || true",
    "sudo apt remove -y cloudflared || true",
    "rm -rf \"$HOME/.cloudflared\" /etc/cloudflared 2>/dev/null || true",
    # Gỡ các gói hệ thống chính liên quan Frappe trên Debian/Ubuntu
    "sudo apt remove -y wkhtmltox wkhtmltopdf redis-server mariadb-server mariadb-client libmariadb-dev xvfb libfontconfig || true",
    "sudo apt autoremove -y || true",
]


# Mã màu ANSI đơn giản cho log / heading
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
FG_CYAN = "\033[96m"
FG_YELLOW = "\033[93m"
FG_GREEN = "\033[92m"
FG_RED = "\033[91m"

# Đường dẫn file settings JSON
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")


def load_settings() -> Dict:
    """Load settings từ file JSON."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    # Trả về default settings
    return {
        "bench_name": "my-bench",
        "node_version": "24",
        "python_version": "3.14",
        "nvm_version": "0.40.3",
        "auto_mode": False,
        "mysql_root_password": "",
        "admin_password": "",
        "sites": [],
        "installed_dependencies": {
            "git": False,
            "node": False,
            "npm": False,
            "yarn": False,
            "uv": False,
            "python": False,
            "bench": False,
            "mariadb": False,
            "mysql": False,
            "redis-server": False,
            "wkhtmltopdf": False,
            "cloudflared": False,
        },
        "platform": None,
        "frappe_dir": "~/frappe",
    }


def save_settings(settings: Dict) -> None:
    """Lưu settings vào file JSON."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def update_dependency_status(dep_name: str, installed: bool) -> None:
    """Cập nhật trạng thái dependency trong settings."""
    settings = load_settings()
    if dep_name in settings["installed_dependencies"]:
        settings["installed_dependencies"][dep_name] = installed
        save_settings(settings)


def ensure_local_bin_in_shell_rc() -> None:
    """
    Đảm bảo ~/.local/bin nằm trong PATH cho bash / zsh bằng cách append vào
    ~/.bashrc và ~/.zshrc (idempotent).
    """
    home = os.path.expanduser("~")
    local_bin = os.path.join(home, ".local", "bin")
    export_line = 'export PATH="$HOME/.local/bin:$PATH"'

    rc_files = [".bashrc", ".zshrc"]
    for rc_name in rc_files:
        rc_path = os.path.join(home, rc_name)
        try:
            existing = ""
            if os.path.exists(rc_path):
                with open(rc_path, encoding="utf-8") as f:
                    existing = f.read()
                # Nếu đã có .local/bin trong PATH thì bỏ qua
                if ".local/bin" in existing:
                    continue

            with open(rc_path, "a", encoding="utf-8") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write("\n# Added by Frappe setup script: ensure local tools are in PATH\n")
                f.write(export_line + "\n")

            print(f"{FG_GREEN}Đã thêm ~/.local/bin vào PATH trong {rc_path}{RESET}")
        except OSError:
            print(
                f"{FG_YELLOW}Không thể cập nhật {rc_path}. "
                f"Vui lòng tự thêm dòng: {export_line}{RESET}"
            )


def get_passwords_from_settings(auto: bool = False) -> tuple[str, str]:
    """
    Lấy MySQL root password và admin password từ settings.
    Nếu chưa có trong settings, sẽ hỏi user và lưu vào settings.
    Trả về (mysql_root_password, admin_password).
    """
    settings = load_settings()
    mysql_root_pwd = settings.get("mysql_root_password", "").strip()
    admin_pwd = settings.get("admin_password", "").strip()
    
    # Nếu chưa có password trong settings, hỏi user
    if not mysql_root_pwd:
        if auto:
            print(f"{FG_YELLOW}MySQL root password chưa được cấu hình trong settings.json{RESET}")
            print(f"{FG_YELLOW}Vui lòng cấu hình 'mysql_root_password' trong settings.json để tự động hóa.{RESET}")
            mysql_root_pwd = input(f"{FG_YELLOW}Nhập MySQL root password: {RESET}").strip()
        else:
            mysql_root_pwd = input(f"{FG_YELLOW}Nhập MySQL root password: {RESET}").strip()
        
        if mysql_root_pwd:
            settings["mysql_root_password"] = mysql_root_pwd
            save_settings(settings)
    
    if not admin_pwd:
        if auto:
            print(f"{FG_YELLOW}Admin password chưa được cấu hình trong settings.json{RESET}")
            print(f"{FG_YELLOW}Vui lòng cấu hình 'admin_password' trong settings.json để tự động hóa.{RESET}")
            admin_pwd = input(f"{FG_YELLOW}Nhập Administrator password: {RESET}").strip()
        else:
            admin_pwd = input(f"{FG_YELLOW}Nhập Administrator password: {RESET}").strip()
        
        if admin_pwd:
            settings["admin_password"] = admin_pwd
            save_settings(settings)
    
    return mysql_root_pwd, admin_pwd


def fix_mysql_root_authentication(mysql_root_pwd: str) -> bool:
    """
    Đổi mật khẩu MySQL root theo settings.json và fix authentication.
    Update password cho root@localhost và tạo root@127.0.0.1, root@% với password authentication.
    Trả về True nếu thành công, False nếu thất bại.
    """
    print(f"\n{FG_CYAN}=== Đổi mật khẩu MySQL root theo settings.json ==={RESET}")
    
    # Test kết nối với TCP/IP (127.0.0.1)
    test_cmd = f"mysql -h 127.0.0.1 -u root -p{shlex.quote(mysql_root_pwd)} -e 'SELECT 1' 2>&1"
    test_result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True)
    
    # Kiểm tra xem có lỗi "Access denied" không
    if "Access denied" not in test_result.stderr and test_result.returncode == 0:
        print(f"{FG_GREEN}✓ MySQL root authentication đã hoạt động với TCP/IP.{RESET}")
        # Vẫn cần đảm bảo root@localhost có password
        print(f"{DIM}Đang đảm bảo root@localhost có password...{RESET}")
    else:
        print(f"{FG_YELLOW}MySQL root chưa có password hoặc đang dùng socket authentication. Đang fix...{RESET}")
    
    # Escape password cho SQL
    mysql_root_pwd_escaped = mysql_root_pwd.replace("'", "''")
    
    # Update password cho root@localhost và tạo root@127.0.0.1, root@% với password authentication
    # MariaDB 10.6+ không cho UPDATE mysql.user trực tiếp (là VIEW), chỉ dùng ALTER USER và CREATE USER
    fix_sql = (
        f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{mysql_root_pwd_escaped}'; "
        f"CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '{mysql_root_pwd_escaped}'; "
        f"GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION; "
        f"CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '{mysql_root_pwd_escaped}'; "
        f"GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION; "
        f"FLUSH PRIVILEGES;"
    )
    
    fix_cmd = f"sudo mysql -e {shlex.quote(fix_sql)}"
    fix_result = subprocess.run(fix_cmd, shell=True, capture_output=True, text=True)
    
    if fix_result.returncode == 0:
        print(f"{FG_GREEN}✓ Đã đổi mật khẩu MySQL root theo settings.json.{RESET}")
        print(f"{DIM}  - root@localhost: password đã được cập nhật{RESET}")
        print(f"{DIM}  - root@127.0.0.1: đã được tạo với password{RESET}")
        print(f"{DIM}  - root@%: đã được tạo với password{RESET}")
        
        # Test lại với TCP/IP connection
        test_cmd2 = f"mysql -h 127.0.0.1 -u root -p{shlex.quote(mysql_root_pwd)} -e 'SELECT 1' 2>&1"
        test_result2 = subprocess.run(test_cmd2, shell=True, capture_output=True, text=True)
        if "Access denied" not in test_result2.stderr and test_result2.returncode == 0:
            print(f"{FG_GREEN}✓ Test TCP/IP connection thành công.{RESET}")
            return True
        else:
            print(f"{FG_YELLOW}⚠ Test TCP/IP connection vẫn lỗi, nhưng password đã được cập nhật.{RESET}")
            return True  # Vẫn return True vì đã update password
    
    print(f"{FG_YELLOW}⚠ Không thể đổi mật khẩu MySQL root tự động.{RESET}")
    if fix_result.stderr:
        print(f"{FG_YELLOW}Lỗi: {fix_result.stderr.strip()}{RESET}")
    print(f"\n{FG_YELLOW}Vui lòng chạy thủ công:{RESET}")
    print(f"  sudo mysql")
    print(f"  ALTER USER 'root'@'localhost' IDENTIFIED BY '{mysql_root_pwd}';")
    print(f"  CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '{mysql_root_pwd}';")
    print(f"  GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;")
    print(f"  CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '{mysql_root_pwd}';")
    print(f"  GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;")
    print(f"  FLUSH PRIVILEGES;")
    return False


def check_command(cmd: str, update_status: bool = True) -> bool:
    """
    Kiểm tra command có tồn tại không. Trả về True nếu có, False nếu không.
    Nếu update_status=True, sẽ cập nhật vào settings.json.
    """
    print(f"\n{FG_CYAN}--- Kiểm tra: {cmd} ---{RESET}")
    # Thêm ~/.local/bin vào PATH để tìm bench (cài qua uv tool install)
    home = os.path.expanduser("~")
    local_bin = os.path.join(home, ".local", "bin")
    path_with_local = f"PATH={local_bin}:$PATH"
    
    which_proc = subprocess.run(
        f"bash -lc '{path_with_local} && command -v {cmd}'",
        shell=True,
        capture_output=True,
        text=True
    )
    if which_proc.returncode != 0:
        # Thử kiểm tra trực tiếp file nếu là bench
        if cmd == "bench":
            bench_path = os.path.join(local_bin, "bench")
            if os.path.exists(bench_path) and os.access(bench_path, os.X_OK):
                path = bench_path
                print(f"{FG_GREEN}{cmd} nằm tại: {path}{RESET}")
                version_proc = subprocess.run(
                    f"bash -lc '{path_with_local} && {cmd} --version'",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if version_proc.returncode == 0:
                    print(f"{BOLD}Version:{RESET} {version_proc.stdout.strip()}")
                if update_status:
                    update_dependency_status(cmd, True)
                return True
        
        print(f"{FG_RED}{cmd}: CHƯA CÀI hoặc không có trong PATH{RESET}")
        if which_proc.stderr:
            print(f"{FG_RED}=== Lỗi / stderr (command -v) ==={RESET}")
            print(which_proc.stderr.strip())
        if update_status:
            update_dependency_status(cmd, False)
        return False
    
    path = which_proc.stdout.strip()
    print(f"{FG_GREEN}{cmd} nằm tại: {path}{RESET}")
    version_proc = subprocess.run(
        f"bash -lc '{path_with_local} && {cmd} --version'",
        shell=True,
        capture_output=True,
        text=True
    )
    if version_proc.returncode == 0:
        print(f"{BOLD}Version:{RESET} {version_proc.stdout.strip()}")
    else:
        print(f"{FG_YELLOW}Không đọc được version (lệnh --version lỗi).{RESET}")
        if version_proc.stderr:
            print(f"{FG_RED}=== Lỗi / stderr (--version) ==={RESET}")
            print(version_proc.stderr.strip())
    if update_status:
        update_dependency_status(cmd, True)
    return True


def check_environment() -> None:
    """Kiểm tra và cập nhật status tất cả dependencies."""
    print(f"\n{BOLD}=== Kiểm tra môi trường Frappe ==={RESET}")
    print("Kiểm tra sự tồn tại & version của các công cụ chính.")
    commands_to_check = [
        "git",
        "node",
        "npm",
        "yarn",
        "uv",
        "python",
        "bench",
        "mariadb",
        "mysql",
        "redis-server",
        "wkhtmltopdf",
    ]
    for c in commands_to_check:
        check_command(c, update_status=True)
    
    # Hiển thị tóm tắt
    settings = load_settings()
    deps = settings["installed_dependencies"]
    installed_count = sum(1 for v in deps.values() if v)
    total_count = len(deps)
    print(f"\n{BOLD}Tóm tắt:{RESET} {installed_count}/{total_count} dependencies đã cài đặt.")


def reset_dependencies() -> None:
    """
    Gỡ toàn bộ dependency Frappe đã cài qua script (nvm, uv, Bench, wkhtmltopdf, workspace, một số gói apt).
    """
    print("\n=== RESET / GỠ TOÀN BỘ DEPENDENCY FRAPPE ===")
    print(
        "Các bước sẽ thực hiện:\n"
        "- Xoá nvm (~/.nvm) và Node/Yarn cài qua nvm.\n"
        "- Xoá uv (~/.local/bin/uv, ~/.local/share/uv).\n"
        "- Gỡ Bench CLI (uv tool uninstall frappe-bench).\n"
        "- Xoá thư mục ~/frappe (workspace bench).\n"
        "- Thử gỡ các gói hệ thống: wkhtmltox, wkhtmltopdf, redis-server, mariadb-server, "
        "mariadb-client, libmariadb-dev, xvfb, libfontconfig.\n"
        "- Chạy apt autoremove để dọn dẹp phụ thuộc thừa.\n"
        "LƯU Ý: git và các công cụ hệ thống chung sẽ KHÔNG bị gỡ."
    )
    if not confirm("Tiếp tục RESET toàn bộ dependency Frappe ở trên? Hành động này có thể xoá dữ liệu ~/frappe."):
        print("Huỷ thao tác reset dependency.")
        return
    run_commands(RESET_COMMANDS)
    
    # Reset tất cả dependency status về False (trừ git)
    settings = load_settings()
    for dep in settings["installed_dependencies"]:
        if dep != "git":  # Giữ git vì không gỡ
            settings["installed_dependencies"][dep] = False
    save_settings(settings)
    print(f"{FG_GREEN}Đã reset dependency status trong settings.json{RESET}")


def setup_cloudflare_tunnel() -> None:
    """
    Setup Cloudflare Tunnel cơ bản: cài cloudflared, tạo tunnel, tạo config + service systemd và route DNS.
    """
    print("\n=== Setup Cloudflare Tunnel ===")
    print(
        "Yêu cầu trước khi chạy:\n"
        "- Đã có tài khoản Cloudflare và domain được quản lý bởi Cloudflare.\n"
        "- Đã update nameserver của domain về Cloudflare.\n"
        "- Biết hostname public muốn dùng (vd: frappe.example.com) và port local (vd: 8000)."
    )
    if not confirm("Tiếp tục setup Cloudflare Tunnel?"):
        print("Huỷ setup Cloudflare Tunnel.")
        return

    hostname = input(f"{FG_YELLOW}Nhập hostname public (vd: frappe.example.com): {RESET}").strip()
    tunnel_name = input(f"{FG_YELLOW}Nhập tên tunnel (vd: frappe-tunnel): {RESET}").strip()
    local_port = input(f"{FG_YELLOW}Nhập port local cần expose (vd: 8000): {RESET}").strip()

    if not hostname or not tunnel_name or not local_port:
        print("Thiếu thông tin hostname / tunnel_name / local_port. Dừng setup.")
        return

    default_service = f"http://localhost:{local_port}"
    service = input(
        f"{FG_YELLOW}Nhập URL service backend (Enter để dùng '{default_service}'): {RESET}"
    ).strip() or default_service

    install_cmds = [
        "curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb",
        "sudo dpkg -i /tmp/cloudflared.deb || sudo apt install -y /tmp/cloudflared.deb",
        "cloudflared --version",
    ]
    print("\n--- Cài đặt cloudflared ---")
    run_commands(install_cmds)

    print(
        "\nBước tiếp theo sẽ chạy 'cloudflared tunnel login' để liên kết với tài khoản Cloudflare.\n"
        "Lệnh này sẽ mở trình duyệt, hãy chọn account và zone tương ứng."
    )
    if confirm("Chạy 'cloudflared tunnel login' ngay bây giờ?"):
        run_commands(["cloudflared tunnel login"])
    else:
        print("Bỏ qua bước login, các lệnh tạo tunnel sau có thể sẽ thất bại nếu chưa login.")

    print("\n--- Tạo tunnel ---")
    create_cmd = ["cloudflared", "tunnel", "create", tunnel_name]
    create_proc = subprocess.run(create_cmd, capture_output=True, text=True)
    if create_proc.returncode != 0:
        msg = (create_proc.stderr or "") + "\n" + (create_proc.stdout or "")
        msg_lower = msg.lower()
        if "tunnel with name already exists" in msg_lower:
            print(
                f"{FG_YELLOW}Tunnel '{tunnel_name}' đã tồn tại. Sẽ xoá tunnel cũ và tạo lại.{RESET}"
            )
            delete_proc = subprocess.run(
                ["cloudflared", "tunnel", "delete", tunnel_name],
                capture_output=True,
                text=True,
            )
            if delete_proc.returncode != 0:
                msg = (delete_proc.stderr or "") + "\n" + (delete_proc.stdout or "")
                msg_lower_del = msg.lower()

                # Nếu Cloudflare báo còn active connections, thử cleanup rồi xoá lại
                if "cannot delete tunnel because it has active connections" in msg_lower_del:
                    print(f"{FG_YELLOW}Tunnel '{tunnel_name}' còn kết nối active. Đang chạy 'cloudflared tunnel cleanup {tunnel_name}' rồi xoá lại...{RESET}")
                    cleanup_proc = subprocess.run(
                        ["cloudflared", "tunnel", "cleanup", tunnel_name],
                        capture_output=True,
                        text=True,
                    )
                    if cleanup_proc.returncode != 0:
                        print(
                            f"{FG_RED}Không thể cleanup tunnel '{tunnel_name}'. Dừng setup Cloudflare Tunnel.{RESET}"
                        )
                        if cleanup_proc.stderr:
                            print(cleanup_proc.stderr.strip())
                        return

                    # Thử xoá lại sau khi cleanup
                    delete_proc2 = subprocess.run(
                        ["cloudflared", "tunnel", "delete", tunnel_name],
                        capture_output=True,
                        text=True,
                    )
                    if delete_proc2.returncode != 0:
                        print(
                            f"{FG_RED}Không thể xoá tunnel cũ '{tunnel_name}' sau khi cleanup. Dừng setup Cloudflare Tunnel.{RESET}"
                        )
                        if delete_proc2.stderr:
                            print(delete_proc2.stderr.strip())
                        return
                else:
                    print(
                        f"{FG_RED}Không thể xoá tunnel cũ '{tunnel_name}'. Dừng setup Cloudflare Tunnel.{RESET}"
                    )
                    if delete_proc.stderr:
                        print(delete_proc.stderr.strip())
                    return

            # Thử tạo lại sau khi xoá
            create_proc2 = subprocess.run(create_cmd, capture_output=True, text=True)
            if create_proc2.returncode != 0:
                print(
                    f"{FG_RED}Không thể tạo lại tunnel '{tunnel_name}'. Dừng setup Cloudflare Tunnel.{RESET}"
                )
                if create_proc2.stderr:
                    print(create_proc2.stderr.strip())
                return
        else:
            print(
                f"{FG_RED}Không thể tạo tunnel '{tunnel_name}'. Dừng setup Cloudflare Tunnel.{RESET}"
            )
            if create_proc.stderr:
                print(create_proc.stderr.strip())
            return

    print("\n--- Tự động tạo config và service systemd cho Cloudflare Tunnel ---")
    created_ok = create_cloudflared_config_and_service(
        hostname=hostname,
        tunnel_name=tunnel_name,
        service=service,
    )

    print("\n--- Tạo hoặc cập nhật DNS cho tunnel ---")
    route_proc = subprocess.run(
        ["cloudflared", "tunnel", "route", "dns", tunnel_name, hostname],
        capture_output=True,
        text=True,
    )
    if route_proc.returncode != 0:
        msg = (route_proc.stderr or "") + "\n" + (route_proc.stdout or "")
        msg_lower = msg.lower()
        # Nếu bản ghi DNS đã tồn tại, coi như thành công (giữ nguyên bản ghi hiện có)
        if "an a, aaaa, or cname record with that host already exists" in msg_lower:
            print(
                f"{FG_YELLOW}Bản ghi DNS cho {hostname} đã tồn tại trong Cloudflare. Giữ nguyên bản ghi hiện tại.{RESET}"
            )
        else:
            print(
                f"{FG_RED}Không thể tạo/route DNS cho hostname {hostname}. Dừng setup Cloudflare Tunnel.{RESET}"
            )
            if route_proc.stderr:
                print(route_proc.stderr.strip())
            return
    else:
        if route_proc.stdout.strip():
            print(route_proc.stdout.strip())

    if created_ok:
        print(
            "\nThông tin Cloudflare Tunnel:\n"
        f"- Tunnel name: {tunnel_name}\n"
        f"- Hostname: {hostname}\n"
            f"- Local service: {service}\n"
            "- Config YAML đã được tạo trong ~/.cloudflared.\n"
            "- Service systemd đã được tạo và enable để chạy tunnel liên tục.\n"
            "\nĐể kiểm tra trạng thái service, dùng lệnh:\n"
            f"  sudo systemctl status cloudflared-{tunnel_name}.service\n"
        )
    else:
        print(
            f"{FG_YELLOW}⚠ Tunnel và route DNS đã tồn tại, nhưng không thể tự tạo config.yml/service tự động.{RESET}\n"
            f"Boss có thể tạo lại config.yml thủ công bằng cách chạy lại tuỳ chọn này sau khi đảm bảo tunnel có credentials file trong ~/.cloudflared."
        )


def create_cloudflared_config_and_service(
    hostname: str,
    tunnel_name: str,
    service: str,
) -> bool:
    home = os.path.expanduser("~")
    cloudflared_dir = os.path.join(home, ".cloudflared")
    os.makedirs(cloudflared_dir, exist_ok=True)

    print("\n--- Đọc danh sách tunnel để lấy tunnel ID ---")
    list_proc = subprocess.run(
        ["cloudflared", "tunnel", "list", "--output", "json"],
        capture_output=True,
        text=True,
    )
    if list_proc.returncode != 0:
        print(
            f"{FG_RED}Không thể lấy danh sách tunnel (cloudflared tunnel list). Bỏ qua bước tạo config/service.{RESET}"
        )
        if list_proc.stderr:
            print(list_proc.stderr.strip())
        return False

    tunnel_id = ""
    try:
        tunnels = json.loads(list_proc.stdout)
        if isinstance(tunnels, list):
            for t in tunnels:
                if t.get("name") == tunnel_name and "id" in t:
                    tunnel_id = t["id"]
                    break
    except json.JSONDecodeError:
        print(
            f"{FG_RED}Không parse được JSON từ cloudflared tunnel list. Bỏ qua bước tạo config/service.{RESET}"
        )
        return False

    if not tunnel_id:
        print(
            f"{FG_RED}Không tìm thấy tunnel '{tunnel_name}' trong danh sách. Bỏ qua bước tạo config/service.{RESET}"
        )
        return False

    credentials_file = os.path.join(cloudflared_dir, f"{tunnel_id}.json")
    if not os.path.exists(credentials_file):
        print(
            f"{FG_RED}Không tìm thấy credentials file cho tunnel ID {tunnel_id}: {credentials_file}{RESET}\n"
            "Vui lòng kiểm tra lại lệnh 'cloudflared tunnel create' hoặc đảm bảo đã login trên máy này."
        )
        return False

    config_path = os.path.join(cloudflared_dir, "config.yml")
    config_content = (
        f"tunnel: {tunnel_id}\n"
        f"credentials-file: {credentials_file}\n"
        "ingress:\n"
        f"  - hostname: {hostname}\n"
        f"    service: {service}\n"
        "  - service: http_status:404\n"
    )

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
        print(f"{FG_GREEN}Đã tạo config Cloudflare Tunnel: {config_path}{RESET}")
    except OSError as e:
        print(f"{FG_RED}Không thể ghi file config: {e}{RESET}")
        return False

    service_name = f"cloudflared-{tunnel_name}.service"
    temp_service_path = os.path.join("/tmp", service_name)
    service_content = (
        "[Unit]\n"
        f"Description=Cloudflare Tunnel ({tunnel_name})\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"User={os.getlogin()}\n"
        f"ExecStart=/usr/bin/cloudflared --config {config_path} --no-autoupdate tunnel run {tunnel_name}\n"
        "Restart=always\n"
        "RestartSec=5s\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )

    try:
        with open(temp_service_path, "w", encoding="utf-8") as f:
            f.write(service_content)
        print(f"{FG_GREEN}Đã tạo tạm file service: {temp_service_path}{RESET}")
    except OSError as e:
        print(f"{FG_RED}Không thể ghi file service tạm: {e}{RESET}")
        return False

    commands = [
        f"sudo mv '{temp_service_path}' '/etc/systemd/system/{service_name}'",
        f"sudo chown root:root '/etc/systemd/system/{service_name}'",
        "sudo systemctl daemon-reload",
        f"sudo systemctl enable {service_name}",
        f"sudo systemctl restart {service_name}",
    ]
    run_commands(commands)
    return True


def regenerate_cloudflare_config_for_existing_tunnel() -> None:
    """
    Chỉ regenerate config.yml + systemd service cho một tunnel Cloudflare đã tồn tại.
    Không xoá / tạo lại tunnel, không động tới DNS.
    """
    print("\n=== Regenerate config + service cho Cloudflare Tunnel đã tồn tại ===")
    hostname = input(
        f"{FG_YELLOW}Nhập hostname public (vd: frappe.example.com): {RESET}"
    ).strip()
    tunnel_name = input(
        f"{FG_YELLOW}Nhập tên tunnel đã tồn tại (vd: frappe-tunnel): {RESET}"
    ).strip()
    service = input(
        f"{FG_YELLOW}Nhập URL service backend (vd: http://localhost:8000): {RESET}"
    ).strip()

    if not hostname or not tunnel_name or not service:
        print(
            f"{FG_RED}Thiếu hostname / tunnel_name / service. Dừng regenerate config.{RESET}"
        )
        return

    ok = create_cloudflared_config_and_service(
        hostname=hostname,
        tunnel_name=tunnel_name,
        service=service,
    )

    if ok:
        print(
            f"{FG_GREEN}✓ Đã regenerate config.yml và systemd service cho tunnel '{tunnel_name}'.{RESET}"
        )
        print(
            f"{DIM}Kiểm tra trạng thái service với:{RESET} sudo systemctl status cloudflared-{tunnel_name}.service"
        )
    else:
        print(
            f"{FG_YELLOW}⚠ Không thể regenerate config/service cho tunnel '{tunnel_name}'. "
            f"Vui lòng kiểm tra lại credentials và danh sách tunnel.{RESET}"
    )


def remove_cloudflare_tunnels() -> None:
    """
    Xóa toàn bộ cloudflared và các service systemctl liên quan trên server này.
    KHÔNG xóa tunnel hay DNS records trên Cloudflare dashboard.
    """
    print("\n=== XÓA CLOUDFLARED VÀ SERVICE SYSTEMCTL TRÊN SERVER ===")
    print(
        "Các bước sẽ thực hiện:\n"
        "- Dừng và disable toàn bộ service cloudflared-*.service trong systemd.\n"
        "- Xóa các file service cloudflared-*.service khỏi /etc/systemd/system/.\n"
        "- Chạy systemctl daemon-reload để reload cấu hình systemd.\n"
        "- Xóa thư mục ~/.cloudflared và /etc/cloudflared (credentials, config, cert.pem).\n"
        "- Gỡ package cloudflared khỏi hệ thống (apt remove).\n"
        "LƯU Ý: Tunnel và DNS records trên Cloudflare dashboard sẽ KHÔNG bị xóa."
    )
    if not confirm("Tiếp tục xóa cloudflared và service liên quan trên server này?"):
        print("Huỷ thao tác xóa cloudflared.")
        return

    # Bước 1: Tìm và dừng toàn bộ service cloudflared-* trong systemd
    print(f"\n{FG_CYAN}--- Bước 1: Dừng và disable toàn bộ service cloudflared-* ---{RESET}")
    list_services_proc = subprocess.run(
        "systemctl list-unit-files 'cloudflared-*.service' --no-legend --plain 2>/dev/null | awk '{print $1}'",
        shell=True, capture_output=True, text=True
    )
    cf_services = [s.strip() for s in list_services_proc.stdout.splitlines() if s.strip()]

    # Cũng tìm service cloudflared (không có hậu tố tunnel name)
    base_service_proc = subprocess.run(
        "systemctl list-unit-files 'cloudflared.service' --no-legend --plain 2>/dev/null | awk '{print $1}'",
        shell=True, capture_output=True, text=True
    )
    if base_service_proc.stdout.strip():
        cf_services.append("cloudflared.service")

    if cf_services:
        print(f"Tìm thấy {len(cf_services)} service(s): {', '.join(cf_services)}")
        for svc in cf_services:
            print(f"{DIM}  Dừng: {svc}{RESET}")
            subprocess.run(f"sudo systemctl stop '{svc}' 2>/dev/null || true", shell=True)
            print(f"{DIM}  Disable: {svc}{RESET}")
            subprocess.run(f"sudo systemctl disable '{svc}' 2>/dev/null || true", shell=True)
        print(f"{FG_GREEN}✓ Đã dừng và disable tất cả service cloudflared.{RESET}")
    else:
        print(f"{FG_YELLOW}Không tìm thấy service cloudflared-* nào đang chạy.{RESET}")

    # Bước 2: Xóa file service khỏi /etc/systemd/system/
    print(f"\n{FG_CYAN}--- Bước 2: Xóa file service khỏi /etc/systemd/system/ ---{RESET}")
    find_proc = subprocess.run(
        "find /etc/systemd/system/ -maxdepth 1 -name 'cloudflared*.service' 2>/dev/null",
        shell=True, capture_output=True, text=True
    )
    service_files = [f.strip() for f in find_proc.stdout.splitlines() if f.strip()]
    if service_files:
        for sf in service_files:
            print(f"{DIM}  Xóa: {sf}{RESET}")
            subprocess.run(f"sudo rm -f '{sf}'", shell=True)
        print(f"{FG_GREEN}✓ Đã xóa {len(service_files)} file service.{RESET}")
    else:
        print(f"{FG_YELLOW}Không tìm thấy file service cloudflared nào trong /etc/systemd/system/.{RESET}")

    # Bước 3: Reload systemd daemon
    print(f"\n{FG_CYAN}--- Bước 3: Reload systemd daemon ---{RESET}")
    subprocess.run("sudo systemctl daemon-reload", shell=True)
    print(f"{FG_GREEN}✓ Đã reload systemd daemon.{RESET}")

    # Bước 4: Xóa thư mục ~/.cloudflared và /etc/cloudflared
    print(f"\n{FG_CYAN}--- Bước 4: Xóa thư mục cấu hình cloudflared ---{RESET}")
    cloudflared_dir = os.path.expanduser("~/.cloudflared")
    if os.path.exists(cloudflared_dir):
        subprocess.run(f"rm -rf '{cloudflared_dir}'", shell=True)
        print(f"{FG_GREEN}✓ Đã xóa thư mục {cloudflared_dir}.{RESET}")
    else:
        print(f"{FG_YELLOW}Thư mục {cloudflared_dir} không tồn tại.{RESET}")

    etc_cloudflared = "/etc/cloudflared"
    etc_proc = subprocess.run(
        f"test -d '{etc_cloudflared}' && sudo rm -rf '{etc_cloudflared}' && echo 'ok' || true",
        shell=True, capture_output=True, text=True
    )
    if "ok" in etc_proc.stdout:
        print(f"{FG_GREEN}✓ Đã xóa thư mục {etc_cloudflared}.{RESET}")
    else:
        print(f"{FG_YELLOW}Thư mục {etc_cloudflared} không tồn tại.{RESET}")

    # Bước 5: Gỡ package cloudflared
    print(f"\n{FG_CYAN}--- Bước 5: Gỡ package cloudflared ---{RESET}")
    subprocess.run(
        "sudo apt remove -y cloudflared 2>/dev/null || sudo dpkg -r cloudflared 2>/dev/null || true",
        shell=True
    )
    print(f"{FG_GREEN}✓ Đã thử gỡ package cloudflared (nếu cài qua apt/dpkg).{RESET}")

    # Cập nhật dependency status trong settings
    update_dependency_status("cloudflared", False)

    print(f"\n{FG_GREEN}=== Hoàn thành! Đã xóa cloudflared và các service liên quan trên server. ==={RESET}")
    print(f"{DIM}Tunnel và DNS records trên Cloudflare dashboard vẫn còn nguyên.{RESET}")


def detect_ubuntu_codename() -> str:
    """
    Trả về codename Ubuntu (vd: jammy, focal), hoặc 'unknown' nếu không xác định được.
    """
    os_release = "/etc/os-release"
    if not os.path.exists(os_release):
        return "unknown"
    codename = "unknown"
    try:
        with open(os_release, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("VERSION_CODENAME="):
                    codename = line.split("=", 1)[1].strip().strip('"')
                    break
                if line.startswith("UBUNTU_CODENAME="):
                    codename = line.split("=", 1)[1].strip().strip('"')
    except OSError:
        return "unknown"
    return codename or "unknown"


def choose_wkhtml_deb() -> tuple[str | None, str]:
    """
    Chọn file .deb wkhtmltox dựa trên codename Ubuntu và file có sẵn trong thư mục wkhtmltox.
    """
    codename = detect_ubuntu_codename()
    # Ưu tiên đúng codename nếu có
    if codename in WKHTMLTOX_DEBS:
        filename = WKHTMLTOX_DEBS[codename]
        candidate = os.path.join(WKHTMLTOX_DIR, filename)
        if os.path.exists(candidate):
            return candidate, codename

    # Fallback: dùng file nào có sẵn
    for filename in WKHTMLTOX_DEBS.values():
        candidate = os.path.join(WKHTMLTOX_DIR, filename)
        if os.path.exists(candidate):
            return candidate, codename

    return None, codename


def install_wkhtmltox_local(auto: bool = False) -> None:
    """
    Cài wkhtmltopdf từ file .deb đã tải sẵn trong thư mục wkhtmltox.
    """
    print("\n--- Cài wkhtmltopdf từ file .deb local ---")
    deb_path, codename = choose_wkhtml_deb()
    if not deb_path:
        print(
            "Không tìm thấy file .deb wkhtmltox phù hợp trong thư mục 'wkhtmltox'.\n"
            "Vui lòng tải file .deb đúng bản Ubuntu từ https://wkhtmltopdf.org/downloads.html "
            "và đặt vào thư mục này."
        )
        return

    print(f"Distro codename phát hiện: {codename}")
    print(f"Sử dụng file: {deb_path}")
    if not auto and not confirm("Tiếp tục cài wkhtmltopdf từ file này bằng sudo dpkg -i?"):
        print("Bỏ qua cài wkhtmltopdf.")
        return

    run_commands([f"sudo dpkg -i '{deb_path}'"])
    print("\n--- Kiểm tra lại wkhtmltopdf sau khi cài đặt ---")
    check_command("wkhtmltopdf")


def run_commands(commands: List[str]) -> None:
    for cmd in commands:
        print(f"\n{FG_CYAN}=== Chạy lệnh: {cmd}{RESET}")
        
        # Dùng Popen để đọc output real-time
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        
        # Đọc và in từng dòng real-time
        stderr_lines = []
        for line in process.stdout:
            line = line.rstrip()
            # Lọc warning "apt does not have a stable CLI interface..."
            if "apt does not have a stable CLI interface" in line:
                continue
            print(line)
            # Lưu lại các dòng có thể là stderr để phân tích sau
            if line.strip():
                stderr_lines.append(line)
        
        # Đợi process kết thúc
        process.wait()
        
        if process.returncode != 0:
            print(f"{FG_RED}⚠️ Lệnh lỗi (exit code {process.returncode}). Dừng chuỗi lệnh.{RESET}")
            return


def confirm(prompt: str) -> bool:
    settings = load_settings()
    auto_mode = settings.get("auto_mode", False)
    if auto_mode:
        print(f"{FG_YELLOW}{prompt} [y/N]: y (auto mode){RESET}")
        return True
    answer = input(f"{FG_YELLOW}{prompt} [y/N]: {RESET}").strip().lower()
    return answer in {"y", "yes"}


def setup_macos(auto: bool = False) -> None:
    print("\n--- Thiết lập Frappe FULL cho macOS ---")
    print(
        "Bao gồm: Xcode CLI, Homebrew, wkhtmltopdf, MariaDB, Redis, pkg-config,\n"
        "- cộng với: nvm, Node, Yarn, uv, Python và Bench CLI + bench nguồn Frappe."
    )
    if not auto and not confirm("Tiếp tục chạy toàn bộ chuỗi setup cho macOS?"):
        print("Bỏ qua setup macOS.")
        return
    run_commands(MACOS_SETUP_COMMANDS)
    setup_common_node_python(auto=auto)
    setup_bench(auto=auto)


def setup_debian_ubuntu(auto: bool = False) -> None:
    print("\n--- Thiết lập Frappe FULL cho Debian / Ubuntu ---")
    print(
        "Bao gồm: apt update, git, redis, MariaDB, pkg-config, wkhtmltopdf dependencies,\n"
        "- cộng với: nvm, Node, Yarn, uv, Python và Bench CLI + bench nguồn Frappe."
    )
    if not auto and not confirm("Tiếp tục chạy toàn bộ chuỗi setup cho Debian / Ubuntu?"):
        print("Bỏ qua setup Debian / Ubuntu.")
        return
    run_commands(DEBIAN_UBUNTU_SETUP_COMMANDS)
    install_wkhtmltox_local(auto=auto)
    setup_common_node_python(auto=auto)
    setup_bench(auto=auto)


def setup_common_node_python(auto: bool = False) -> None:
    print("\n--- Cài đặt dependency chung: nvm, Node, Yarn, uv, Python ---")
    print(
        "Script sẽ cài nvm, NodeJS 24, Yarn, uv và Python 3.14 (mặc định). "
        "Một số bước yêu cầu mở lại shell hoặc source ~/.bashrc / ~/.zshrc sau khi chạy."
    )
    if auto or confirm("Chạy chuỗi lệnh cài đặt dependency chung (nvm/Node/Yarn/uv/Python)?"):
        run_commands(COMMON_NODE_PYTHON_COMMANDS)
        # Sau khi cài uv / bench, đảm bảo ~/.local/bin có trong PATH của shell người dùng
        ensure_local_bin_in_shell_rc()


def setup_bench(auto: bool = False, bench_name: str | None = None) -> None:
    print("\n--- Cài đặt Bench CLI và khởi tạo bench ---")
    
    settings = load_settings()
    if bench_name is None:
        bench_name = settings.get("bench_name", "my-bench")
        default_name = bench_name
        if auto:
            print(f"Các bước chính: uv tool install frappe-bench, kiểm tra version, tạo bench.")
            bench_name_input = input(f"{FG_YELLOW}Nhập tên bench (Enter để dùng '{default_name}'): {RESET}").strip()
            bench_name = bench_name_input if bench_name_input else default_name
        else:
            print("Các bước chính: uv tool install frappe-bench, kiểm tra version, tạo bench.")
            bench_name_input = input(f"{FG_YELLOW}Nhập tên bench (Enter để dùng '{default_name}'): {RESET}").strip()
            bench_name = bench_name_input if bench_name_input else default_name
    
    # Lưu bench_name vào settings
    settings["bench_name"] = bench_name
    save_settings(settings)
    
    print(f"{BOLD}Tên bench sẽ được tạo: {bench_name}{RESET}")
    if auto or confirm(f"Tiếp tục cài Bench CLI và khởi tạo bench '{bench_name}'?"):
        run_commands(get_bench_setup_commands(bench_name))
        # Đảm bảo ~/.local/bin (chứa bench) có trong PATH cho các shell sau này
        ensure_local_bin_in_shell_rc()
        
        # Kiểm tra bench đã được init thành công
        frappe_dir = os.path.expanduser(settings.get("frappe_dir", "~/frappe"))
        bench_path = os.path.join(frappe_dir, bench_name)
        
        if os.path.exists(bench_path):
            print(f"\n{FG_GREEN}✓ Bench '{bench_name}' đã được khởi tạo thành công!{RESET}")
            
            # Cập nhật status sau khi cài
            check_command("bench", update_status=True)
            
            # Tự động tạo site sau khi bench init thành công
            print(f"\n{BOLD}--- Tạo Site mới cho Bench ---{RESET}")
            default_site = "library.localhost"
            
            # Hỏi user có muốn tạo site không (cả auto và interactive mode)
            if auto:
                # Auto mode: dùng tên site mặc định
                site_name = default_site
                print(f"{DIM}Auto mode: Sẽ tạo site '{site_name}'{RESET}")
            else:
                # Interactive mode: hỏi user
                site_name = input(f"{FG_YELLOW}Nhập tên site (Enter để dùng '{default_site}' hoặc 'skip' để bỏ qua): {RESET}").strip()
                if not site_name:
                    site_name = default_site
                elif site_name.lower() == "skip":
                    print("Bỏ qua tạo site.")
                    return
            
            # Kiểm tra site đã tồn tại chưa
            sites_dir = os.path.join(bench_path, "sites")
            site_path = os.path.join(sites_dir, site_name)
            
            if os.path.exists(site_path):
                print(f"{FG_YELLOW}Site '{site_name}' đã tồn tại.{RESET}")
                if not auto and not confirm("Tiếp tục tạo lại site này? (sẽ xoá site cũ)"):
                    print("Bỏ qua tạo site.")
                    return
                elif auto:
                    print(f"{DIM}Auto mode: Site đã tồn tại, sẽ tạo lại.{RESET}")
            
            if auto or confirm(f"Tiếp tục tạo site '{site_name}' trong bench '{bench_name}'?"):
                print(f"\n{FG_CYAN}=== Đang tạo site '{site_name}' ==={RESET}")
                
                # Lấy password từ settings
                mysql_root_pwd, admin_pwd = get_passwords_from_settings(auto=auto)
                
                if not mysql_root_pwd or not admin_pwd:
                    print(f"{FG_RED}Thiếu password. Không thể tạo site.{RESET}")
                    return
                
                print(f"{DIM}Sử dụng password từ settings.json{RESET}")
                
                # Kiểm tra và fix MySQL root authentication nếu cần
                if not fix_mysql_root_authentication(mysql_root_pwd):
                    if not auto and not confirm("Tiếp tục tạo site dù MySQL authentication có thể lỗi?"):
                        print("Huỷ tạo site.")
                        return
                print()
                
                # Chạy bench new-site với password từ settings
                # Escape password để tránh shell injection và đảm bảo truyền đúng
                mysql_root_pwd_escaped = shlex.quote(mysql_root_pwd)
                admin_pwd_escaped = shlex.quote(admin_pwd)
                
                # Dùng root@localhost với password đã được update
                cmd = (
                    f"bash -lc 'export NVM_DIR=\"$HOME/.nvm\" && "
                    f"[ -s \"$NVM_DIR/nvm.sh\" ] && . \"$NVM_DIR/nvm.sh\" && "
                    f"cd {bench_path} && "
                    f"bench new-site {site_name} "
                    f"--db-root-username root "
                    f"--db-root-password {mysql_root_pwd_escaped} "
                    f"--admin-password {admin_pwd_escaped} "
                    f"--mariadb-user-host-login-scope=localhost"
                    f"'"
                )
                
                try:
                    process = subprocess.run(cmd, shell=True)
                    
                    if process.returncode == 0 and os.path.exists(site_path):
                        print(f"\n{FG_GREEN}✓ Site '{site_name}' đã được tạo thành công!{RESET}")
                        print(f"{DIM}Site path: {site_path}{RESET}")
                        
                        # Lưu site vào settings
                        if "sites" not in settings:
                            settings["sites"] = []
                        if site_name not in settings["sites"]:
                            settings["sites"].append(site_name)
                        save_settings(settings)
                        
                        # Hướng dẫn truy cập
                        print(f"\n{BOLD}Để truy cập site:{RESET}")
                        if not site_name.endswith(".localhost"):
                            print(f"  - Thêm vào /etc/hosts: 127.0.0.1 {site_name}")
                            print(f"  - Hoặc chạy: {FG_CYAN}bench --site {site_name} add-to-hosts{RESET}")
                        print(f"  - Truy cập: {FG_CYAN}http://{site_name}:8000{RESET}")
                    elif process.returncode != 0:
                        print(f"\n{FG_RED}✗ Tạo site '{site_name}' thất bại (exit code {process.returncode}).{RESET}")
                        print(f"{FG_YELLOW}Vui lòng kiểm tra lại logs ở trên.{RESET}")
                    else:
                        print(f"\n{FG_YELLOW}⚠ Site '{site_name}' có thể chưa được tạo thành công.{RESET}")
                        print(f"{FG_YELLOW}Vui lòng kiểm tra lại thư mục {site_path}{RESET}")
                except Exception as e:
                    print(f"{FG_RED}Lỗi khi tạo site: {e}{RESET}")
        else:
            print(f"{FG_YELLOW}⚠ Bench '{bench_name}' có thể chưa được khởi tạo thành công.{RESET}")
            print(f"{FG_YELLOW}Vui lòng kiểm tra lại thư mục {bench_path}{RESET}")


def create_site() -> None:
    """Tạo site mới cho bench đã có sẵn."""
    print("\n--- Tạo Site mới cho Bench ---")
    
    settings = load_settings()
    bench_name = settings.get("bench_name", "my-bench")
    frappe_dir = os.path.expanduser(settings.get("frappe_dir", "~/frappe"))
    bench_path = os.path.join(frappe_dir, bench_name)
    
    # Kiểm tra bench đã được init chưa
    if not os.path.exists(bench_path):
        print(f"{FG_RED}Bench '{bench_name}' chưa được khởi tạo tại {bench_path}{RESET}")
        print(f"{FG_YELLOW}Vui lòng chạy Setup FULL (option 1) trước để tạo bench.{RESET}")
        return
    
    # Kiểm tra bench command có sẵn không
    bench_check = subprocess.run("command -v bench", shell=True, capture_output=True, text=True)
    if bench_check.returncode != 0:
        print(f"{FG_RED}Bench CLI chưa được cài đặt.{RESET}")
        print(f"{FG_YELLOW}Vui lòng chạy Setup FULL (option 1) trước.{RESET}")
        return
    
    # Nhập tên site
    default_site = "library.localhost"
    site_name = input(f"{FG_YELLOW}Nhập tên site (Enter để dùng '{default_site}'): {RESET}").strip()
    if not site_name:
        site_name = default_site
    
    # Kiểm tra site đã tồn tại chưa
    sites_dir = os.path.join(bench_path, "sites")
    site_path = os.path.join(sites_dir, site_name)
    if os.path.exists(site_path):
        print(f"{FG_YELLOW}Site '{site_name}' đã tồn tại tại {site_path}{RESET}")
        if not confirm("Tiếp tục tạo lại site này? (sẽ xoá site cũ)"):
            print("Huỷ tạo site.")
            return
    
    print(f"{BOLD}Tên site sẽ được tạo: {site_name}{RESET}")
    print(f"{DIM}Bench path: {bench_path}{RESET}")
    
    if not confirm(f"Tiếp tục tạo site '{site_name}' trong bench '{bench_name}'?"):
        print("Huỷ tạo site.")
        return
    
    # Chạy lệnh bench new-site
    print(f"\n{FG_CYAN}=== Đang tạo site '{site_name}' ==={RESET}")
    
    # Lấy password từ settings
    settings = load_settings()
    auto_mode = settings.get("auto_mode", False)
    mysql_root_pwd, admin_pwd = get_passwords_from_settings(auto=auto_mode)
    
    if not mysql_root_pwd or not admin_pwd:
        print(f"{FG_RED}Thiếu password. Không thể tạo site.{RESET}")
        return
    
    print(f"{DIM}Sử dụng password từ settings.json{RESET}")
    
    # Kiểm tra và fix MySQL root authentication nếu cần
    if not fix_mysql_root_authentication(mysql_root_pwd):
        if not auto_mode and not confirm("Tiếp tục tạo site dù MySQL authentication có thể lỗi?"):
            print("Huỷ tạo site.")
            return
    print()
    
    # Chạy bench new-site với password từ settings
    # Escape password để tránh shell injection và đảm bảo truyền đúng
    mysql_root_pwd_escaped = shlex.quote(mysql_root_pwd)
    admin_pwd_escaped = shlex.quote(admin_pwd)
    
    # Dùng root@localhost với password đã được update
    cmd = (
        f"bash -lc 'export NVM_DIR=\"$HOME/.nvm\" && "
        f"[ -s \"$NVM_DIR/nvm.sh\" ] && . \"$NVM_DIR/nvm.sh\" && "
        f"cd {bench_path} && "
        f"bench new-site {site_name} "
        f"--db-root-username root "
        f"--db-root-password {mysql_root_pwd_escaped} "
        f"--admin-password {admin_pwd_escaped} "
        f"--mariadb-user-host-login-scope=localhost"
        f"'"
    )
    
    try:
        # Chạy trực tiếp với subprocess.run
        process = subprocess.run(cmd, shell=True)
        
        # Kiểm tra site đã được tạo thành công
        if process.returncode == 0 and os.path.exists(site_path):
            print(f"\n{FG_GREEN}✓ Site '{site_name}' đã được tạo thành công!{RESET}")
            print(f"{DIM}Site path: {site_path}{RESET}")
            
            # Lưu site vào settings
            if "sites" not in settings:
                settings["sites"] = []
            if site_name not in settings["sites"]:
                settings["sites"].append(site_name)
            save_settings(settings)
            
            # Hướng dẫn truy cập
            print(f"\n{BOLD}Để truy cập site:{RESET}")
            if not site_name.endswith(".localhost"):
                print(f"  - Thêm vào /etc/hosts: 127.0.0.1 {site_name}")
                print(f"  - Hoặc chạy: {FG_CYAN}bench --site {site_name} add-to-hosts{RESET}")
            print(f"  - Truy cập: {FG_CYAN}http://{site_name}:8000{RESET}")
        elif process.returncode != 0:
            print(f"\n{FG_RED}✗ Tạo site '{site_name}' thất bại (exit code {process.returncode}).{RESET}")
            print(f"{FG_YELLOW}Vui lòng kiểm tra lại logs ở trên.{RESET}")
        else:
            print(f"\n{FG_YELLOW}⚠ Site '{site_name}' có thể chưa được tạo thành công.{RESET}")
            print(f"{FG_YELLOW}Vui lòng kiểm tra lại thư mục {site_path}{RESET}")
    except Exception as e:
        print(f"{FG_RED}Lỗi khi tạo site: {e}{RESET}")


def detect_platform() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    return "unknown"


def get_status_icon(installed: bool) -> str:
    """Trả về icon cho trạng thái cài đặt."""
    return f"{FG_GREEN}✓{RESET}" if installed else f"{FG_RED}✗{RESET}"


def print_menu(detected: str) -> None:
    """In menu với status dependency."""
    settings = load_settings()
    deps = settings["installed_dependencies"]
    
    print(f"\n{BOLD}========================{RESET}")
    print(f"{BOLD}  Frappe Setup Menu{RESET}")
    print(f"{BOLD}========================{RESET}")
    print(f"Hệ điều hành phát hiện: {FG_CYAN}{detected}{RESET}")
    
    # Hiển thị status dependency ngắn gọn
    print(f"\n{DIM}Dependency Status:{RESET}")
    core_deps = ["git", "node", "python", "bench"]
    db_deps = ["mariadb", "redis-server", "wkhtmltopdf"]
    
    core_status = " ".join([f"{get_status_icon(deps.get(d, False))} {d}" for d in core_deps])
    db_status = " ".join([f"{get_status_icon(deps.get(d, False))} {d}" for d in db_deps])
    print(f"  Core: {core_status}")
    print(f"  DB/Cache: {db_status}")
    
    print(f"\n{BOLD}Chọn tác vụ:{RESET}")
    print(f"  {FG_CYAN}1{RESET}) Setup FULL cho {detected} (hệ thống + môi trường + Bench/source Frappe)")
    print(f"  {FG_CYAN}2{RESET}) Kiểm tra môi trường (các tool đã cài đặt)")
    print(f"  {FG_CYAN}3{RESET}) Chỉ cài wkhtmltopdf từ file .deb local")
    print(f"  {FG_CYAN}4{RESET}) RESET / gỡ toàn bộ dependency Frappe đã cài")
    print(f"  {FG_CYAN}5{RESET}) Tạo Site mới cho Bench (bench new-site)")
    print(f"  {FG_CYAN}6{RESET}) Setup Cloudflare Tunnel (cloudflared + tạo tunnel + route DNS)")
    print(f"  {FG_CYAN}7{RESET}) Regenerate config + service cho Cloudflare Tunnel đã tồn tại")
    print(f"  {FG_RED}8{RESET}) Xóa toàn bộ tunnel cloudflared và service systemctl liên quan")
    print(f"  {FG_CYAN}0{RESET}) Thoát")


def main() -> None:
    # Kiểm tra tham số command line
    if len(sys.argv) > 1:
        if sys.argv[1] in ("--auto", "-y", "--yes"):
            detected = detect_platform()
            settings = load_settings()
            settings["platform"] = detected
            settings["auto_mode"] = True
            save_settings(settings)
            print(f"{BOLD}=== AUTO MODE: Chạy setup tự động cho {detected} ==={RESET}")
            if detected == "macos":
                setup_macos(auto=True)
            elif detected == "linux":
                setup_debian_ubuntu(auto=True)
            else:
                print(f"{FG_RED}Không xác định được platform. Vui lòng chạy menu tương tác.{RESET}")
            return
        elif sys.argv[1] in ("--help", "-h"):
            print("Frappe Setup Menu")
            print("\nCách dùng:")
            print("  python3 setup_menu.py              # Chạy menu tương tác")
            print("  python3 setup_menu.py --auto        # Chạy auto mode (không hỏi confirm, tự chọn platform)")
            print("  python3 setup_menu.py -y            # Tương tự --auto")
            sys.exit(0)
    
    detected = detect_platform()
    # Cập nhật platform vào settings
    settings = load_settings()
    settings["platform"] = detected
    save_settings(settings)

    while True:
        print_menu(detected)
        choice = input(f"{FG_YELLOW}\nNhập lựa chọn: {RESET}").strip()

        if choice == "1":
            if detected == "macos":
                setup_macos()
            elif detected == "linux":
                setup_debian_ubuntu()
            else:
                print(f"{FG_RED}Platform không được hỗ trợ.{RESET}")
        elif choice == "2":
            check_environment()
        elif choice == "3":
            install_wkhtmltox_local()
        elif choice == "4":
            reset_dependencies()
        elif choice == "5":
            create_site()
        elif choice == "6":
            setup_cloudflare_tunnel()
        elif choice == "7":
            regenerate_cloudflare_config_for_existing_tunnel()
        elif choice == "8":
            remove_cloudflare_tunnels()
        elif choice == "0":
            print("Thoát Frappe setup menu.")
            break
        else:
            print("Lựa chọn không hợp lệ, vui lòng nhập lại.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBị huỷ bởi người dùng.")
        sys.exit(1)

