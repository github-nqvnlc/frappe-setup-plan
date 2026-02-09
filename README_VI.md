## Frappe Setup Server – `setup_menu.py` (Tiếng Việt)

### 1. Mục đích

Script `setup_menu.py` cung cấp một menu tương tác giúp bạn:

- Cài đặt hệ thống cho Frappe/Bench trên Debian/Ubuntu và macOS.
- Cài Bench CLI (`frappe-bench`) và khởi tạo workspace `~/frappe/<bench_name>`.
- Tạo site Frappe mới với tên tùy chọn.
- Kiểm tra môi trường (các công cụ đã cài, phiên bản…).
- Cài wkhtmltopdf từ file `.deb` local.
- Reset/gỡ bỏ toàn bộ dependency liên quan đến Frappe.
- Thiết lập Cloudflare Tunnel cơ bản.

Toàn bộ cấu hình và trạng thái cài đặt được lưu trong `settings.json`, giúp bạn chạy lại script nhiều lần mà vẫn giữ được bench name, mật khẩu MySQL, danh sách site và trạng thái dependency.

---

### 2. Cấu trúc thư mục

```text
frappe-setup-server/
  ├─ setup_menu.py         # Script Python chính (menu setup)
  ├─ settings.json         # File cấu hình & trạng thái cài đặt
  ├─ wkhtmltox/            # Thư mục chứa file .deb wkhtmltopdf (jammy/focal)
  ├─ install-debian-ubuntu.md
  ├─ install-macos.md
  ├─ bench-setup.md
  └─ ...
```

---

### 3. Yêu cầu hệ thống

- Debian/Ubuntu (đã test trong WSL2) hoặc macOS.
- Quyền `sudo` để cài package hệ thống và cấu hình MariaDB.
- Python 3 (`python3`).
- Kết nối Internet để cài đặt dependency (apt, curl, uv, nvm, v.v.).

---

### 4. `settings.json` – file cấu hình

Ví dụ:

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

Giải thích:

- **`bench_name`** – Tên bench (workspace) được tạo trong `~/frappe/<bench_name>`.
- **`mysql_root_password`** – Mật khẩu MySQL root, dùng cho lệnh `bench new-site`.
- **`admin_password`** – Mật khẩu Administrator cho site Frappe.
- **`sites`** – Danh sách tên site đã tạo (để theo dõi).
- **`installed_dependencies`** – Trạng thái cài đặt các công cụ (được cập nhật bởi `check_environment()`).
- **`platform`** – Hệ điều hành phát hiện được (`linux` / `macos`).
- **`frappe_dir`** – Thư mục gốc chứa workspace bench (mặc định `~/frappe`).
- **`auto_mode`** – Nếu `true`, script tự động chọn “yes” cho đa số câu hỏi.

---

### 5. Cách chạy

#### 5.1. Chạy menu tương tác

```bash
cd ~/frappe-setup-server
python3 setup_menu.py
```

Menu sẽ hiển thị:

- Trạng thái dependency: `git`, `node`, `python`, `bench`, `mariadb`, `redis-server`, `wkhtmltopdf`, …
- Các lựa chọn:

1. Setup FULL cho hệ điều hành phát hiện  
   (hệ thống + môi trường + Bench + source Frappe)
2. Kiểm tra môi trường (các tool đã cài đặt)
3. Chỉ cài wkhtmltopdf từ file `.deb` local
4. RESET / gỡ toàn bộ dependency Frappe đã cài
5. Tạo site mới cho Bench (chạy `bench new-site`)
6. Setup Cloudflare Tunnel
0. Thoát

#### 5.2. Chạy Auto Mode (không hỏi confirm)

```bash
python3 setup_menu.py --auto
# hoặc
python3 setup_menu.py -y
```

Ở chế độ auto:

- Script tự phát hiện platform (`linux` / `macos`).
- Chạy full setup tương ứng.
- Sử dụng `auto_mode=true` trong `settings.json`.
- Dùng `mysql_root_password` và `admin_password` trong `settings.json` khi tạo site.

---

### 6. Chức năng chính trong `setup_menu.py`

#### 6.1. Setup theo platform

- **`setup_macos(auto=False)`**
  - Cài: Xcode CLI, Homebrew, wkhtmltopdf cho macOS, git, redis, MariaDB, pkg-config, …
  - Sau đó gọi `setup_common_node_python(auto)` và `setup_bench(auto)`.

- **`setup_debian_ubuntu(auto=False)`**
  - Chạy `apt update`, cài git, `redis-server`, `mariadb-server`, `mariadb-client`, `libmariadb-dev`, `build-essential`, `python3-dev`, wkhtmltopdf dependencies, v.v.
  - Gọi `install_wkhtmltox_local(auto)` để cài wkhtmltopdf từ `.deb` local nếu có.
  - Gọi tiếp `setup_common_node_python(auto)` và `setup_bench(auto)`.

#### 6.2. Cài Node, Python, uv, Yarn

- **`setup_common_node_python(auto=False)`**
  - Cài:
    - `nvm` + NodeJS 24 + Yarn.
    - `uv` và Python 3.14.
  - Sau khi cài xong, gọi **`ensure_local_bin_in_shell_rc()`** để thêm:

    ```bash
    export PATH="$HOME/.local/bin:$PATH"
    ```

    vào `~/.bashrc` / `~/.zshrc` nếu chưa có.  
    Việc này đảm bảo `~/.local/bin/bench` luôn có trong PATH cho **các terminal mở sau này**.

> Đối với terminal hiện tại, bạn cần chạy:
>
> ```bash
> export PATH="$HOME/.local/bin:$PATH"
> # hoặc
> source ~/.bashrc
> ```

#### 6.3. Cài Bench và khởi tạo bench

- **`get_bench_setup_commands(bench_name)`**
  - Trả về danh sách lệnh:
    - Cài `frappe-bench` bằng `uv tool install` (có `--force` nếu cần).
    - Chạy `bench --version` để verify.
    - Tạo thư mục `~/frappe`.
    - Chạy `bench init <bench_name>` trong `~/frappe` (đã load `nvm` để Node/Yarn có trong PATH).

- **`setup_bench(auto=False, bench_name=None)`**
  - Lấy `bench_name` từ `settings.json` hoặc hỏi người dùng.
  - Chạy chuỗi lệnh từ `get_bench_setup_commands`.
  - Gọi `ensure_local_bin_in_shell_rc()` để chắc chắn `~/.local/bin` nằm trong PATH (cho các shell sau).
  - Kiểm tra bench đã được init thành công, đánh dấu `bench` là đã cài trong `installed_dependencies`.
  - Hỏi (hoặc tự động) để **tạo site mới** sau khi bench init.

#### 6.4. Tạo site mới

Hai luồng `setup_bench()` (sau khi init) và `create_site()` đều dùng chung logic:

1. Đọc `mysql_root_password` và `admin_password` từ `settings.json` (hoặc hỏi nếu thiếu).
2. Gọi **`fix_mysql_root_authentication(mysql_root_pwd)`**:
   - Cố gắng đặt password cho `root@localhost`.
   - Tạo `root@127.0.0.1` và `root@'%'` với cùng password và full quyền.
   - Nếu không fix tự động được, in ra lệnh SQL để bạn chạy thủ công.
3. Chạy:

   ```bash
   bench new-site <site_name> \
     --db-root-username root \
     --db-root-password <mysql_root_password> \
     --admin-password <admin_password> \
     --mariadb-user-host-login-scope=localhost
   ```

4. Nếu thành công:
   - Thêm tên site vào `settings["sites"]`.
   - In hướng dẫn:
     - Thêm `127.0.0.1 <site_name>` vào `/etc/hosts` (nếu cần).
     - Chạy `bench --site <site_name> add-to-hosts`.
     - Truy cập `http://<site_name>:8000`.

> Lưu ý: Một số cấu hình MariaDB (đặc biệt khi dùng `unix_socket`) yêu cầu bạn chạy lệnh SQL thủ công như gợi ý trong log.

#### 6.5. Kiểm tra môi trường

- **`check_environment()`**
  - Kiểm tra và in version cho:
    - `git`, `node`, `npm`, `yarn`, `uv`, `python`, `bench`,
      `mariadb`, `mysql`, `redis-server`, `wkhtmltopdf`.
  - Cập nhật `installed_dependencies` trong `settings.json`.

#### 6.6. Cài wkhtmltopdf từ file `.deb` local

- **`install_wkhtmltox_local(auto=False)`**
  - Detect Ubuntu codename (`jammy`, `focal`, …).
  - Chọn file `.deb` tương ứng trong thư mục `wkhtmltox/`.
  - Chạy `sudo dpkg -i '<file>'`.
  - Gọi `check_command("wkhtmltopdf")` để kiểm tra lại.

#### 6.7. Reset toàn bộ dependency

- **`reset_dependencies()`**
  - Xóa:
    - `~/.nvm`, uv, `frappe-bench` (qua `uv tool uninstall`), thư mục `~/frappe`.
    - Cloudflare Tunnel (`cloudflared`, systemd service, config).
    - Các gói apt: `wkhtmltox`, `wkhtmltopdf`, `redis-server`,
      `mariadb-server`, `mariadb-client`, `libmariadb-dev`, `xvfb`, `libfontconfig`, …
  - Chạy `sudo apt autoremove -y`.
  - Reset toàn bộ `installed_dependencies` trong `settings.json` (ngoại trừ `git`).

#### 6.8. Setup Cloudflare Tunnel

- **`setup_cloudflare_tunnel()`**
  - Tải và cài `cloudflared` từ file `.deb`.
  - Hỗ trợ chạy `cloudflared tunnel login`.
  - Tạo tunnel & cấu hình DNS:
    - `cloudflared tunnel create <tunnel_name>`
    - `cloudflared tunnel route dns <tunnel_name> <hostname>`
  - In mẫu `config.yml` để chạy tunnel dưới dạng service.

---

### 7. Lưu ý & khắc phục sự cố

- **`bench` không tìm thấy trong PATH**
  - `bench` được cài vào `~/.local/bin/bench`.
  - Script đã thêm `export PATH="$HOME/.local/bin:$PATH"` vào `.bashrc` / `.zshrc` thông qua `ensure_local_bin_in_shell_rc()`.
  - Với terminal hiện tại, cần chạy:

    ```bash
    export PATH="$HOME/.local/bin:$PATH"
    # hoặc
    source ~/.bashrc
    ```

- **Lỗi MySQL kiểu `(1698, "Access denied for user 'root'@'localhost'")`**
  - MariaDB có thể đang dùng `unix_socket` cho user root.
  - `fix_mysql_root_authentication()` cố gắng:
    - Chạy `ALTER USER 'root'@'localhost' IDENTIFIED BY '<password>';`
    - Tạo `root@127.0.0.1` và `root@'%'` với cùng password và full quyền.
  - Nếu không fix tự động được, hãy chạy các lệnh SQL được in ra bằng `sudo mysql`.

- **Khi nào nên dùng Auto Mode?**
  - Khi bạn đã:
    - Điền đúng `mysql_root_password` và `admin_password` vào `settings.json`.
    - Đã quen với flow cài đặt và muốn chạy “1 mạch” từ đầu tới cuối.
  - Lần chạy đầu tiên nên dùng chế độ tương tác để xem từng bước rõ ràng.

Nếu bạn mở rộng `setup_menu.py` (thêm menu, thêm platform), hãy cập nhật cả `README.md` và `README_VI.md` để tài liệu tiếng Anh và tiếng Việt luôn đồng bộ.

