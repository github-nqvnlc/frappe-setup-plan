# Frappe Setup Server – `setup_menu.py`

## 1. Purpose

`setup_menu.py` is an interactive Python menu that automates the full lifecycle of a Frappe/Bench server:

- System setup on Debian/Ubuntu and macOS.
- Bench CLI installation and workspace initialisation.
- Frappe site creation.
- Environment health checks.
- wkhtmltopdf installation from local `.deb` files.
- Full dependency reset/removal.
- Cloudflare Tunnel setup, status checking, and cleanup.
- Bench process management (stop all, create/remove auto-start services).

All state is persisted in `settings.json` so the script is safely re-entrant.

---

## 2. Project structure

```text
frappe-setup-plan/
  ├─ setup_menu.py         # Main menu script
  ├─ settings.json         # Config & installation state
  ├─ wkhtmltox/            # wkhtmltopdf .deb files (jammy / focal)
  ├─ README.md             # This file (English)
  ├─ README_VI.md          # Vietnamese version
  └─ ...
```

---

## 3. Requirements

- Debian/Ubuntu (incl. WSL2) or macOS.
- `sudo` privileges.
- Python 3.
- Internet access for apt, curl, nvm, uv, etc.

---

## 4. `settings.json`

```json
{
  "bench_name": "my-bench",
  "node_version": "24",
  "python_version": "3.14",
  "nvm_version": "0.40.3",
  "auto_mode": false,
  "mysql_root_password": "your-root-password",
  "admin_password": "your-admin-password",
  "sites": ["library.localhost"],
  "installed_dependencies": {
    "git": true, "node": true, "npm": true, "yarn": true,
    "uv": true, "python": true, "bench": true,
    "mariadb": true, "mysql": true,
    "redis-server": true, "wkhtmltopdf": true, "cloudflared": false
  },
  "platform": "linux",
  "frappe_dir": "~/frappe",
  "bench_start_service": "bench-start-my-bench.service"
}
```

| Key | Description |
|-----|-------------|
| `bench_name` | Bench workspace under `~/frappe/<bench_name>` |
| `mysql_root_password` | MySQL root password used by `bench new-site` |
| `admin_password` | Frappe site administrator password |
| `sites` | List of created site names |
| `installed_dependencies` | Flags updated by `check_environment()` |
| `platform` | Detected OS (`linux` / `macos`) |
| `frappe_dir` | Base directory for benches (default `~/frappe`) |
| `auto_mode` | Skip confirmations when `true` |
| `bench_start_service` | Name of the auto-start systemd service (set by menu 11) |

---

## 5. How to run

### Interactive menu

```bash
cd ~/frappe-setup-plan
python3 setup_menu.py
```

### Auto mode (non-interactive)

```bash
python3 setup_menu.py --auto   # or -y
```

Auto mode detects the platform, runs a full setup, and uses passwords from `settings.json`.

---

## 6. Menu options

| # | Description | Colour |
|---|-------------|--------|
| **1** | Full setup for detected platform (system + Node/Python + Bench + Frappe source) | cyan |
| **2** | Check environment (installed tools & versions) | green |
| **3** | Install wkhtmltopdf from local `.deb` file | cyan |
| **4** | RESET – remove all Frappe dependencies | red |
| **5** | Create a new Frappe site (`bench new-site`) | cyan |
| **6** | Setup Cloudflare Tunnel (install + create tunnel + route DNS) | cyan |
| **7** | Regenerate config + systemd service for an existing Cloudflare Tunnel | cyan |
| **8** | Remove cloudflared and all related systemd services from this server | red |
| **9** | Stop all running bench processes (bench start / workers / gunicorn) | yellow |
| **10** | Remove bench systemd services (frappe-bench-web, worker, schedule…) | red |
| **11** | Create auto-start systemd service for `bench start` after reboot | cyan |
| **12** | Remove the auto-start bench start service | red |
| **13** | Check Cloudflare Tunnel status | green |
| **0** | Exit | cyan |

---

## 7. Key functions

### 7.1 Platform setup

| Function | Description |
|----------|-------------|
| `setup_macos(auto)` | Xcode CLI, Homebrew, wkhtmltopdf, git, redis, MariaDB → node/python → bench |
| `setup_debian_ubuntu(auto)` | apt packages, wkhtmltopdf local deb, node/python → bench |
| `setup_common_node_python(auto)` | nvm + Node 24 + Yarn, uv + Python 3.14, adds `~/.local/bin` to PATH |
| `setup_bench(auto, bench_name)` | `uv tool install frappe-bench`, `bench init`, optionally creates a site |

### 7.2 Site creation

Both `setup_bench()` and `create_site()` share the same flow:

1. Read passwords from `settings.json` (prompt if missing).
2. `fix_mysql_root_authentication()` – ensures `root@localhost`, `root@127.0.0.1`, `root@%` all have password auth.
3. Run `bench new-site <name> --db-root-password ... --admin-password ...`
4. Save site name to `settings["sites"]`.

### 7.3 Cloudflare Tunnel

| Function | Menu | Description |
|----------|------|-------------|
| `setup_cloudflare_tunnel()` | 6 | Install cloudflared, login, create tunnel, route DNS, create systemd service |
| `regenerate_cloudflare_config_and_service()` | 7 | Recreate `config.yml` + `.service` without touching the tunnel or DNS |
| `remove_cloudflare_tunnels()` | 8 | Stop/disable/delete all cloudflared services, remove `~/.cloudflared`, uninstall package. **Does NOT delete tunnels on Cloudflare dashboard.** |
| `check_cloudflare_status()` | 13 | Show binary version, service states, config.yml contents, tunnel list with connection info, DNS resolution test |

### 7.4 Bench process & service management

| Function | Menu | Description |
|----------|------|-------------|
| `stop_all_benches()` | 9 | Find and kill all bench/frappe processes (SIGTERM → SIGKILL) |
| `remove_bench_services()` | 10 | Stop, disable, and delete bench production systemd services; also checks supervisord |
| `create_bench_start_service()` | 11 | Create `/etc/systemd/system/bench-start-<name>.service` that runs `bench start` on boot; recreates if already exists |
| `remove_bench_start_service()` | 12 | Stop, disable, and delete the bench-start service |

### 7.5 Utilities

| Function | Description |
|----------|-------------|
| `check_environment()` | Check & version all dependencies, update `settings.json` |
| `install_wkhtmltox_local(auto)` | Install wkhtmltopdf from `wkhtmltox/*.deb` |
| `reset_dependencies()` | Full cleanup: nvm, uv, bench, ~/frappe, cloudflared, apt packages |
| `ensure_local_bin_in_shell_rc()` | Idempotently add `~/.local/bin` to `~/.bashrc` / `~/.zshrc` |

---

## 8. Troubleshooting

**`bench` not found in PATH**
```bash
export PATH="$HOME/.local/bin:$PATH"
# or
source ~/.bashrc
```

**MySQL Access denied for `root@localhost`**

MariaDB may use socket auth. `fix_mysql_root_authentication()` runs:
```sql
ALTER USER 'root'@'localhost' IDENTIFIED BY '<password>';
CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '<password>';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;
FLUSH PRIVILEGES;
```
If it fails, run the printed SQL manually with `sudo mysql`.

**bench start service not starting after reboot**
```bash
sudo journalctl -u bench-start-<bench_name>.service -n 50
```
NVM and `~/.local/bin` are sourced via `bash -lc` in the ExecStart so Node and bench should be found correctly.

**Cloudflare Tunnel not connecting**

Use menu **13** to check service status, config.yml, and DNS resolution in one shot.
