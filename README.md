## Frappe Setup Server – `setup_menu.py`

### 1. Purpose

This project provides a Python script (`setup_menu.py`) with an interactive menu to automate:

- System setup for Frappe/Bench on Debian/Ubuntu and macOS.
- Installation of the Bench CLI (`frappe-bench`) and initialization of a bench workspace.
- Creation of Frappe sites with custom names.
- Environment health checks (installed tools and their versions).
- Installing wkhtmltopdf from local `.deb` files.
- Resetting/removing all Frappe-related dependencies.
- Basic Cloudflare Tunnel setup.

All configuration and state are stored in `settings.json`, so the script can be run multiple times while remembering your bench name, MySQL password, created sites, and dependency status.

---

### 2. Project structure

```text
frappe-setup-server/
  ├─ setup_menu.py         # Main Python script (interactive menu)
  ├─ settings.json         # Configuration & installation state
  ├─ wkhtmltox/            # wkhtmltopdf .deb files (jammy/focal)
  ├─ install-debian-ubuntu.md
  ├─ install-macos.md
  ├─ bench-setup.md
  └─ ...
```

---

### 3. Requirements

- Debian/Ubuntu (tested in WSL2) or macOS.
- `sudo` privileges (for installing packages and configuring MariaDB).
- Python 3 (`python3` executable).
- Internet access to install dependencies (apt, curl, uv, nvm, etc.).

---

### 4. `settings.json` – configuration

Example:

```json
{
  "bench_name": "windify-hrms",
  "node_version": "24",
  "python_version": "3.14",
  "nvm_version": "0.40.3",
  "auto_mode": true,
  "mysql_root_password": "your-root-password",
  "admin_password": "your-admin-password",
  "sites": [
    "demo.test"
  ],
  "installed_dependencies": {
    "git": true,
    "node": false,
    "npm": true,
    "yarn": true,
    "uv": true,
    "python": true,
    "bench": true,
    "mariadb": true,
    "mysql": true,
    "redis-server": true,
    "wkhtmltopdf": true,
    "cloudflared": false
  },
  "platform": "linux",
  "frappe_dir": "~/frappe"
}
```

Key fields:

- **`bench_name`** – Name of the bench (workspace under `~/frappe/<bench_name>`).
- **`mysql_root_password`** – MySQL root password used for `bench new-site`.
- **`admin_password`** – Administrator password for the Frappe site.
- **`sites`** – List of created site names.
- **`installed_dependencies`** – Status flags updated by `check_environment()`.
- **`platform`** – Detected platform (`linux` / `macos`).
- **`frappe_dir`** – Base directory for benches (default `~/frappe`).
- **`auto_mode`** – When `true`, most confirmations are skipped (auto “yes”).

---

### 5. How to run

#### 5.1. Interactive menu

```bash
cd ~/frappe-setup-server
python3 setup_menu.py
```

You’ll see:

- A status block for core dependencies.
- Menu options:
  1. Full setup for the detected platform  
     (system + environment + Bench + Frappe source)
  2. Check environment (installed tools and versions)
  3. Install wkhtmltopdf from local `.deb` file
  4. RESET / remove all Frappe-related dependencies
  5. Create a new site for the current bench (`bench new-site`)
  6. Setup Cloudflare Tunnel
  0. Exit

#### 5.2. Auto mode (non-interactive)

```bash
python3 setup_menu.py --auto
# or
python3 setup_menu.py -y
```

In auto mode the script:

- Detects the platform (`linux` / `macos`).
- Runs the full setup for that platform.
- Uses `auto_mode=true` in `settings.json`.
- Uses `mysql_root_password` and `admin_password` from `settings.json` for `bench new-site`.

---

### 6. Core functions

#### 6.1. Platform setup

- **`setup_macos(auto: bool = False)`**
  - Installs Xcode CLI tools, Homebrew, wkhtmltopdf for macOS, git, redis, MariaDB, pkg-config, etc.
  - Then calls `setup_common_node_python(auto)` and `setup_bench(auto)`.

- **`setup_debian_ubuntu(auto: bool = False)`**
  - Runs `apt update` and installs git, `redis-server`, `mariadb-server`, `mariadb-client`, `libmariadb-dev`, `build-essential`, `python3-dev`, wkhtmltopdf dependencies, etc.
  - Calls `install_wkhtmltox_local(auto)` to install wkhtmltopdf from local `.deb` files if available.
  - Then calls `setup_common_node_python(auto)` and `setup_bench(auto)`.

#### 6.2. Node, Python, uv, Yarn

- **`setup_common_node_python(auto: bool = False)`**
  - Installs:
    - `nvm` + NodeJS 24 + Yarn.
    - `uv` and Python 3.14.
  - After installation, calls **`ensure_local_bin_in_shell_rc()`** to append:

    ```bash
    export PATH="$HOME/.local/bin:$PATH"
    ```

    to `~/.bashrc` / `~/.zshrc` (idempotent).  
    This ensures `~/.local/bin/bench` is on the `PATH` for **new shells** you open.

> For the current terminal session you still need to run:
>
> ```bash
> export PATH="$HOME/.local/bin:$PATH"
> # or
> source ~/.bashrc
> ```

#### 6.3. Bench installation and initialization

- **`get_bench_setup_commands(bench_name: str)`**
  - Returns a list of shell commands to:
    - Install `frappe-bench` via `uv tool install` (with `--force` if needed).
    - Run `bench --version` to verify.
    - Create `~/frappe`.
    - Run `bench init <bench_name>` in `~/frappe`, with `nvm` loaded to make Node/Yarn available.

- **`setup_bench(auto: bool = False, bench_name: str | None = None)`**
  - Reads `bench_name` from `settings.json` or prompts the user.
  - Runs the commands from `get_bench_setup_commands`.
  - Calls `ensure_local_bin_in_shell_rc()` to ensure `~/.local/bin` is on PATH.
  - Verifies that the bench directory exists and marks `bench` as installed.
  - Optionally (depending on mode and confirmation) creates a new site immediately after bench init.

#### 6.4. Site creation

Both `setup_bench()` (post-init) and `create_site()` share the same flow:

1. Read `mysql_root_password` and `admin_password` from `settings.json` (or prompt if missing).
2. Call **`fix_mysql_root_authentication(mysql_root_pwd)`**:
   - Attempts to set a password for `root@localhost`.
   - Creates `root@'127.0.0.1'` and `root@'%'` with the same password and full privileges.
   - Prints manual SQL commands if automatic fix fails.
3. Run:

   ```bash
   bench new-site <site_name> \
     --db-root-username root \
     --db-root-password <mysql_root_password> \
     --admin-password <admin_password> \
     --mariadb-user-host-login-scope=localhost
   ```

4. On success:
   - Append the site name to `settings["sites"]`.
   - Print instructions:
     - Add `127.0.0.1 <site_name>` to `/etc/hosts` if needed.
     - Run `bench --site <site_name> add-to-hosts`.
     - Access the site at `http://<site_name>:8000`.

> Depending on your MariaDB configuration (e.g. `unix_socket` auth), you may still need to run the suggested SQL commands manually using `sudo mysql`.

#### 6.5. Environment check

- **`check_environment()`**
  - Iterates over:
    - `git`, `node`, `npm`, `yarn`, `uv`, `python`, `bench`, `mariadb`, `mysql`, `redis-server`, `wkhtmltopdf`.
  - For each command:
    - Runs `command -v <cmd>` and `<cmd> --version`.
    - Prints location and version.
    - Updates `installed_dependencies[cmd]` in `settings.json`.

#### 6.6. Install wkhtmltopdf from local `.deb`

- **`install_wkhtmltox_local(auto: bool = False)`**
  - Detects the Ubuntu codename (`jammy`, `focal`, etc.).
  - Selects the appropriate `.deb` from the `wkhtmltox/` directory.
  - Installs using `sudo dpkg -i '<file>'`.
  - Calls `check_command("wkhtmltopdf")` to verify.

#### 6.7. Reset all Frappe dependencies

- **`reset_dependencies()`**
  - Removes:
    - `~/.nvm`, uv binaries/data, `frappe-bench` (via `uv tool uninstall`).
    - Workspace directory `~/frappe`.
    - `cloudflared` and related systemd units/config.
    - System packages: `wkhtmltox`, `wkhtmltopdf`, `redis-server`,
      `mariadb-server`, `mariadb-client`, `libmariadb-dev`, `xvfb`, `libfontconfig`, etc.
  - Runs `sudo apt autoremove -y`.
  - Resets all `installed_dependencies` flags in `settings.json` (except `git`).

#### 6.8. Cloudflare Tunnel

- **`setup_cloudflare_tunnel()`**
  - Downloads and installs `cloudflared` from the official `.deb` package.
  - Optionally runs `cloudflared tunnel login`.
  - Creates a tunnel and DNS route:
    - `cloudflared tunnel create <tunnel_name>`
    - `cloudflared tunnel route dns <tunnel_name> <hostname>`
  - Prints a sample `config.yml` snippet to run the tunnel as a long-running service.

---

### 7. Notes and troubleshooting

- **Bench not found in PATH**
  - The script installs `bench` into `~/.local/bin/bench`.
  - It also appends `export PATH="$HOME/.local/bin:$PATH"` to `.bashrc` / `.zshrc` via `ensure_local_bin_in_shell_rc()`.
  - For the current shell, run:

    ```bash
    export PATH="$HOME/.local/bin:$PATH"
    # or
    source ~/.bashrc
    ```

- **MySQL authentication errors (e.g. `(1698, "Access denied for user 'root'@'localhost'")`)**
  - MariaDB may be using socket authentication for root.
  - `fix_mysql_root_authentication()` tries to:
    - Run `ALTER USER 'root'@'localhost' IDENTIFIED BY '<password>';`
    - Create `root@'127.0.0.1'` and `root@'%'` with the same password.
  - If the automatic fix fails, follow the printed SQL commands and run them manually with `sudo mysql`.

- **Auto mode vs interactive**
  - Auto mode is best used when:
    - You have already filled `mysql_root_password` and `admin_password` in `settings.json`.
    - You want to run a full setup without confirmations.
  - Interactive mode is recommended the first time you run the script, so you can review each step.

If you extend `setup_menu.py` (add new menu items or platforms), keep `README.md` and `README_VI.md` in sync so both English and Vietnamese docs stay up to date.

Frappe Setup Server
===================

Tài liệu này tóm tắt và chuẩn hoá lại hướng dẫn cài đặt Frappe Framework từ trang chính thức [`https://docs.frappe.io/framework/user/en/installation`](https://docs.frappe.io/framework/user/en/installation).

Nội dung chính:

- **Yêu cầu hệ thống & phiên bản dependency** (MariaDB, Python, NodeJS, Redis/Valkey, Yarn, pip, wkhtmltopdf, cron).
- **Chuẩn bị môi trường** cho:
  - macOS.
  - Debian / Ubuntu (bao gồm WSL trên Windows).
- **Cài đặt dependency chung**: nvm, Node, Yarn, uv, Python.
- **Cài đặt Bench CLI** và khởi tạo bench đầu tiên.

Các file liên quan:

- `requirements.md`: Yêu cầu hệ thống & phiên bản dependency.
- `install-macos.md`: Các bước cài đặt Frappe trên macOS.
- `install-debian-ubuntu.md`: Các bước cài đặt Frappe trên Debian / Ubuntu (bao gồm WSL).
- `bench-setup.md`: Các bước cài đặt Bench CLI, Python và NodeJS bằng uv & nvm.

Tham khảo gốc: [`https://docs.frappe.io/framework/user/en/installation`](https://docs.frappe.io/framework/user/en/installation).

