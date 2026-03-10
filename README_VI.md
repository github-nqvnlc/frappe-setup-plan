# Frappe Setup Server – `setup_menu.py` (Tiếng Việt)

## 1. Mục đích

`setup_menu.py` là menu Python tương tác giúp tự động hoá toàn bộ vòng đời của một server Frappe/Bench:

- Cài đặt hệ thống trên Debian/Ubuntu và macOS.
- Cài Bench CLI và khởi tạo workspace.
- Tạo site Frappe.
- Kiểm tra môi trường (tool đã cài, version).
- Cài wkhtmltopdf từ file `.deb` local.
- Reset/gỡ toàn bộ dependency.
- Cài đặt, kiểm tra và dọn dẹp Cloudflare Tunnel.
- Quản lý bench process (dừng tất cả, tạo/xóa service tự khởi động).

Mọi trạng thái được lưu trong `settings.json` — script có thể chạy lại nhiều lần an toàn.

---

## 2. Cấu trúc thư mục

```text
frappe-setup-plan/
  ├─ setup_menu.py         # Script menu chính
  ├─ settings.json         # Cấu hình & trạng thái cài đặt
  ├─ wkhtmltox/            # File .deb wkhtmltopdf (jammy / focal)
  ├─ README.md             # Tài liệu tiếng Anh
  ├─ README_VI.md          # File này (tiếng Việt)
  └─ ...
```

---

## 3. Yêu cầu hệ thống

- Debian/Ubuntu (kể cả WSL2) hoặc macOS.
- Quyền `sudo`.
- Python 3.
- Kết nối internet (apt, curl, nvm, uv…).

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

| Trường | Mô tả |
|--------|-------|
| `bench_name` | Tên bench trong `~/frappe/<bench_name>` |
| `mysql_root_password` | Mật khẩu MySQL root dùng cho `bench new-site` |
| `admin_password` | Mật khẩu Administrator site Frappe |
| `sites` | Danh sách site đã tạo |
| `installed_dependencies` | Cờ trạng thái, cập nhật bởi `check_environment()` |
| `platform` | Hệ điều hành phát hiện (`linux` / `macos`) |
| `frappe_dir` | Thư mục gốc chứa bench (mặc định `~/frappe`) |
| `auto_mode` | `true` → bỏ qua hầu hết câu hỏi xác nhận |
| `bench_start_service` | Tên service systemd tự khởi động (đặt bởi menu 11) |

---

## 5. Cách chạy

### Menu tương tác

```bash
cd ~/frappe-setup-plan
python3 setup_menu.py
```

### Auto mode (không hỏi confirm)

```bash
python3 setup_menu.py --auto   # hoặc -y
```

Auto mode tự phát hiện platform, chạy full setup, dùng password từ `settings.json`.

---

## 6. Các option trong menu

| # | Mô tả | Màu |
|---|-------|-----|
| **1** | Setup FULL (hệ thống + Node/Python + Bench + source Frappe) | cyan |
| **2** | Kiểm tra môi trường (tool đã cài & version) | xanh lá |
| **3** | Chỉ cài wkhtmltopdf từ file `.deb` local | cyan |
| **4** | RESET – gỡ toàn bộ dependency Frappe | đỏ |
| **5** | Tạo site Frappe mới (`bench new-site`) | cyan |
| **6** | Setup Cloudflare Tunnel (cài + tạo tunnel + route DNS) | cyan |
| **7** | Regenerate config + service cho Cloudflare Tunnel đã có | cyan |
| **8** | Xóa cloudflared và toàn bộ service systemctl khỏi server này | đỏ |
| **9** | Dừng tất cả bench process đang chạy (bench start / worker / gunicorn) | vàng |
| **10** | Xóa các service systemctl production của bench | đỏ |
| **11** | Tạo service tự động `bench start` sau reboot | cyan |
| **12** | Xóa service tự động bench start | đỏ |
| **13** | Kiểm tra trạng thái Cloudflare Tunnel | xanh lá |
| **0** | Thoát | cyan |

---

## 7. Chức năng chính

### 7.1 Setup theo platform

| Hàm | Mô tả |
|-----|-------|
| `setup_macos(auto)` | Xcode CLI, Homebrew, wkhtmltopdf, git, redis, MariaDB → node/python → bench |
| `setup_debian_ubuntu(auto)` | apt packages, wkhtmltopdf deb local, node/python → bench |
| `setup_common_node_python(auto)` | nvm + Node 24 + Yarn, uv + Python 3.14, thêm `~/.local/bin` vào PATH |
| `setup_bench(auto, bench_name)` | `uv tool install frappe-bench`, `bench init`, tùy chọn tạo site luôn |

### 7.2 Tạo site

Cả `setup_bench()` và `create_site()` dùng chung quy trình:

1. Đọc password từ `settings.json` (hỏi nếu thiếu).
2. `fix_mysql_root_authentication()` – đảm bảo `root@localhost`, `root@127.0.0.1`, `root@%` dùng password auth.
3. Chạy `bench new-site <tên> --db-root-password ... --admin-password ...`
4. Lưu tên site vào `settings["sites"]`.

### 7.3 Cloudflare Tunnel

| Hàm | Menu | Mô tả |
|-----|------|-------|
| `setup_cloudflare_tunnel()` | 6 | Cài cloudflared, login, tạo tunnel, route DNS, tạo service systemd |
| `regenerate_cloudflare_config_and_service()` | 7 | Tạo lại `config.yml` + `.service` (không đụng tunnel hay DNS) |
| `remove_cloudflare_tunnels()` | 8 | Stop/disable/xóa tất cả service cloudflared, xóa `~/.cloudflared`, gỡ package. **KHÔNG xóa tunnel trên Cloudflare dashboard.** |
| `check_cloudflare_status()` | 13 | Hiển thị version binary, trạng thái service, nội dung config.yml, danh sách tunnel, kết nối active, test DNS |

### 7.4 Quản lý bench process & service

| Hàm | Menu | Mô tả |
|-----|------|-------|
| `stop_all_benches()` | 9 | Tìm và kill tất cả process bench/frappe (SIGTERM → SIGKILL) |
| `remove_bench_services()` | 10 | Stop, disable, xóa file service production của bench; kiểm tra thêm supervisord |
| `create_bench_start_service()` | 11 | Tạo `/etc/systemd/system/bench-start-<tên>.service` chạy `bench start` lúc boot; tự xóa tạo lại nếu đã tồn tại |
| `remove_bench_start_service()` | 12 | Stop, disable, xóa service bench-start |

### 7.5 Tiện ích

| Hàm | Mô tả |
|-----|-------|
| `check_environment()` | Kiểm tra & in version tất cả dependency, cập nhật `settings.json` |
| `install_wkhtmltox_local(auto)` | Cài wkhtmltopdf từ `wkhtmltox/*.deb` |
| `reset_dependencies()` | Dọn sạch: nvm, uv, bench, ~/frappe, cloudflared, apt packages |
| `ensure_local_bin_in_shell_rc()` | Thêm `~/.local/bin` vào `~/.bashrc` / `~/.zshrc` (idempotent) |

---

## 8. Khắc phục sự cố

**`bench` không tìm thấy trong PATH**
```bash
export PATH="$HOME/.local/bin:$PATH"
# hoặc
source ~/.bashrc
```

**Lỗi MySQL `Access denied for 'root'@'localhost'`**

MariaDB có thể đang dùng socket auth. `fix_mysql_root_authentication()` chạy:
```sql
ALTER USER 'root'@'localhost' IDENTIFIED BY '<password>';
CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '<password>';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;
FLUSH PRIVILEGES;
```
Nếu không tự fix được, hãy chạy các lệnh SQL đó thủ công bằng `sudo mysql`.

**Service bench start không khởi động sau reboot**
```bash
sudo journalctl -u bench-start-<bench_name>.service -n 50
```
NVM và `~/.local/bin` được load qua `bash -lc` trong ExecStart nên Node và bench sẽ tìm thấy đúng.

**Cloudflare Tunnel không kết nối**

Dùng menu **13** để kiểm tra trạng thái service, nội dung config.yml và test DNS chỉ trong 1 lần chạy.
