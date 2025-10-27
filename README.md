### 🧠 **Sleep Bot — Sổ tay bảo trì nội bộ (Private)**

> **Phiên bản:** `v6_full_embed_configsystem`
> **Dev:** Kiyaaaa (Khải Trần)
> **Mục tiêu:** Ổn định • Dễ bảo trì • Có cấu hình động qua slash command
> **Nền:** Flask + Discord.py + SQLite

---

## 🚀 Khởi động nhanh

Nếu bot ngừng hoạt động hoặc Render vừa redeploy, chạy:

```bash
python3 skibidi_v6.py
```

Bot sẽ tự động:

1. Mở Flask server tại cổng `8080`
2. Tạo route `/` (cho UptimeRobot) và `/healthz` (cho Render)
3. Delay 3 giây để Flask bind port
4. Khởi động bot Discord (các lệnh slash auto sync)

---

## 🧩 Biến môi trường cần có

Khai báo trong Render Secrets hoặc file `.env`:

```
TOKEN=discord_bot_token
ROLE_NAME=💤 Tín Đồ Ngủ Đông
PORT=8080
```

> ⚙️ **Không cần khai báo INACTIVE_DAYS hoặc AUTO_DELETE_ENABLED nữa**
> vì bot sẽ tự đọc / ghi vào `config.json`.

---

## ⚙️ Cấu hình động

File `config.json` lưu cài đặt runtime, ví dụ:

```json
{
  "INACTIVE_DAYS": 30,
  "AUTO_DELETE_ENABLED": true
}
```

Nếu file không tồn tại, bot sẽ **tự tạo mới** với giá trị mặc định.

---

## 🔧 Các lệnh Slash (v6)

| Lệnh                  | Mô tả                                                              | Ghi chú                  |
| --------------------- | ------------------------------------------------------------------ | ------------------------ |
| `/runcheck`           | Chạy kiểm tra thủ công, gán role ngủ đông cho ai inact quá số ngày | Embed kết quả            |
| `/config_info`        | Hiển thị thông tin cấu hình hiện tại                               | Gồm role, ngày, DB       |
| `/setinactive <days>` | Thay đổi số ngày inactive cần thiết để add role                    | Ghi vào `config.json`    |
| `/toggle_autodelete`  | Bật/tắt tự động xóa embed (v3s sau 3s)                             | Lưu vào `config.json`    |
| `/status`             | Hiển thị số lượng người đang có role ngủ đông                      | Embed trực quan          |
| `/exportdb`           | Xuất file `.db` để backup                                          | Gửi file SQLite          |
| `/exportcsv`          | Xuất dữ liệu CSV dễ đọc                                            | Gửi file CSV             |
| `/help`               | Danh sách lệnh với icon và thumbnail                               | Đã có ảnh, không bị mất  |
| `/list_off`           | Danh sách thành viên đang bị role ngủ đông                         | Tự động paginate nếu dài |

> 🔁 Tất cả các lệnh giữ nguyên style embed v5, thêm phần config logic của v6.

---

## 💾 Database: `inactivity.db`

* Tự tạo nếu chưa có.
* Lưu các cột:
  `member_id`, `guild_id`, `last_seen`, `role_added`.
* Có thể export hoặc xóa reset dễ dàng.

### 📤 Backup thủ công

```bash
/exportdb
```

### 📊 Xuất CSV dễ đọc

```bash
/exportcsv
```

---

## 🔁 Task định kỳ

Bot sẽ tự động chạy kiểm tra mỗi **24h/lần**:

* Nếu user **offline ≥ INACTIVE_DAYS** → add role ngủ đông
* Nếu user online → update last_seen

> Có thể chạy ngay bằng `/runcheck`.

---

## 🧰 Debug nhanh

| Vấn đề            | Nguyên nhân             | Giải pháp                         |
| ----------------- | ----------------------- | --------------------------------- |
| Bot không start   | Flask chưa bind port    | Kiểm tra `time.sleep(3)`          |
| Role không add    | Bot thiếu quyền         | Cấp quyền `Manage Roles`          |
| Flask log lỗi 503 | Render check quá sớm    | Ping lại sau 5s                   |
| Không lưu config  | Bot không ghi được file | Kiểm tra quyền ghi `config.json`  |
| Embed không xóa   | AUTO_DELETE = false     | Dùng `/toggle_autodelete` bật lại |

---

## ⚙️ Deployment nhanh trên Render

### 1️⃣ Fork hoặc upload repo lên GitHub

Đảm bảo repo có file:

```
skibidi_v6.py
requirements.txt
runtime.txt
```

### 2️⃣ Vào [Render.com](https://render.com) → **New + Web Service**

* **Environment:** Python
* **Build Command:** *(để trống)*
* **Start Command:**

  ```bash
  python3 skibidi_v6.py
  ```

### 3️⃣ Add các biến môi trường:

```
TOKEN=...
ROLE_NAME=💤 Tín Đồ Ngủ Đông
PORT=8080
```

### 4️⃣ Ping giữ online bằng UptimeRobot

* URL: `https://tên-dịch-vụ.onrender.com/`
* Ping mỗi 5 phút là đủ.

---

## 🧹 Reset nhẹ

Xóa database và cấu hình, sau đó restart:

```bash
rm inactivity.db config.json
python3 skibidi_v6.py
```

---

## 🧠 Ghi nhớ

* Flask luôn khởi động **trước bot**
* `/healthz` giúp Render không kill tiến trình
* SQLite + JSON config → gọn, dễ backup
* Không cần auto-deploy lại sau mỗi lần chỉnh config

---

## 🧩 Cấu trúc repo gợi ý

```
/ (root)
├── skibidi_v6.py
├── config.json
├── inactivity.db
├── requirements.txt
├── runtime.txt
├── README_INTERNAL_v6.md
└── .gitignore
```

---

> “Bot không cần sức mạnh — chỉ cần logic đủ nhẹ để tự sống.”
> — Kiyaaaa, 2025*
