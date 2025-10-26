
# 🧠 Skibidi Bot — Sổ tay bảo trì nội bộ *(Private)*

> **Phiên bản:** `v5_full_embed_v2style`  
> **Dev:** Kiyaaaa  
> **Mục tiêu:** Ổn định • Nhẹ • Miễn phí • Không vòng lặp Render

---

## 🚀 Khởi động nhanh

Nếu bot ngừng hoạt động hoặc Render vừa redeploy, chạy:

```bash
python3 skibidi_fixed_v3_full_embed_v2style.py
````

Bot sẽ tự động:

1. Mở Flask server tại cổng `8080`
2. Tạo route `/` (cho UptimeRobot) và `/healthz` (cho Render)
3. Delay 3 giây để Flask bind port
4. Sau đó khởi động Discord bot

---

## 🧩 Biến môi trường cần có

Khai báo trong Render Secrets hoặc file `.env`:

```
TOKEN=discord_bot_token
ROLE_NAME=💤 Tín Đồ Ngủ Đông
INACTIVE_DAYS=30
PORT=8080
```

> ⚠️ Nếu bạn dùng Render, PORT sẽ được tự cấp.
> Chỉ cần khai báo TOKEN, các giá trị khác có thể để mặc định.

---

## ⚙️ Kiểm tra hoạt động

| Cách                | Mục đích                      | Kết quả mong đợi           |
| ------------------- | ----------------------------- | -------------------------- |
| Truy cập `/`        | Ping UptimeRobot giữ bot sống | 🟢 “Bot đang chạy ổn định” |
| Truy cập `/healthz` | Health check Render           | `OK`                       |
| `/test`             | Kiểm tra bot hoạt động        | Embed màu xanh lá hiện ra  |
| `/runcheck`         | Kiểm tra thủ công             | Embed xanh lá khi hoàn tất |
| `/config_info`      | Xem cấu hình hiện tại         | Hiển thị role, ngày, DB    |

---

## 💾 Database: `inactivity.db`

* Tự tạo nếu chưa tồn tại.
* Lưu trữ các cột:
  `member_id`, `guild_id`, `last_seen`, `role_added`.
* Không cần backup thường xuyên (có thể export khi cần).

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

Bot tự động kiểm tra hoạt động mỗi **24 giờ/lần**:

* Nếu thành viên **offline ≥ 30 ngày** → gán role **💤 Tín Đồ Ngủ Đông**
* Nếu thành viên **offline** → cập nhật `last_seen`

> Có thể chạy thủ công bất cứ lúc nào bằng `/runcheck`.

---

## 🧰 Debug nhanh

| Vấn đề                                | Nguyên nhân                           | Cách xử lý                               |
| ------------------------------------- | ------------------------------------- | ---------------------------------------- |
| Bot không start trên Render           | Flask chưa bind port kịp              | Kiểm tra có `time.sleep(3)` ở cuối file  |
| “Bad Gateway” / “Service Unavailable” | Thiếu `/healthz` hoặc Flask chưa chạy | Đảm bảo route `/healthz` tồn tại         |
| Không thấy role `💤 Tín Đồ Ngủ Đông`  | Role chưa tạo trên server             | Tạo role và cấp quyền quản lý cho bot    |
| Bot không add role                    | Thiếu quyền `Manage Roles`            | Kiểm tra quyền bot trên Discord          |
| Database lỗi                          | File `.db` bị khóa                    | Stop bot → xóa `inactivity.db` → restart |

---

## 🧹 Reset nhẹ (nếu cần)

Xóa DB cũ và khởi động lại:

```bash
rm inactivity.db
python3 skibidi_fixed_v3_full_embed_v2style.py
```

---

## 🧠 Ghi nhớ

* Flask luôn khởi động **trước bot**
* `/healthz` giữ cho Render không kill bot (không cần Replit keepalive)
* SQLite an toàn, nhẹ và tự động tạo
* Không nên auto-deploy quá thường xuyên (Render coi như “loop” nếu ping trùng build time)

---

## 💬 Ghi chú riêng

> “Bot này không cần nhiều tiền — chỉ cần hiểu cách nó thở.”
> — *Khải Trần, 2025*

---

## 📜 Lịch sử thay đổi (Changelog)

| Phiên bản      | Ngày    | Nội dung nổi bật                                 |
| -------------- | ------- | ------------------------------------------------ |
| **v1**         | 2024-12 | Khởi tạo Skibidi Bot (cơ bản)                    |
| **v2**         | 2025-02 | Thêm Flask uptime và SQLite                      |
| **v3**         | 2025-05 | Giao diện Embed đầy đủ, ổn định Render           |
| **v3_fix**     | 2025-07 | Tối ưu Flask threading + role logic              |
| **v4 (Slash)** | 2025-09 | Chuyển sang Slash Commands                       |
| **v5.1**       | 2025-10 | Thêm auto-delete embed & delay chống spam Render |

---

### 🧩 Cấu trúc repo gợi ý

```
/ (root)
├── skibidi_v5_slash_autodelete.py
├── requirements.txt
├── runtime.txt
├── README_INTERNAL.md
└── inactivity.db  (tự tạo)
```

---

*🫧 Document by Phoebe / Kiyaaaa – Internal Build Guide, 2025*

```

---

Bạn có muốn tôi **thêm thêm phần “Deployment nhanh trên Render (Quick Deploy Steps)”** ở ngay sau phần “Khởi động nhanh” không?  
Nó sẽ hướng dẫn copy repo → set env → nhấn deploy, dành riêng cho Render.
```
