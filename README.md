
# 🧠 Skibidi Bot V3 — Sổ tay bảo trì nội bộ (Private)

> Phiên bản: `v3_full_embed_v2style`  
> Dev: **Khải Trần**  
> Mục tiêu: Ổn định – Nhẹ – Miễn phí – Không vòng lặp Render

---

## 🚀 Khởi động nhanh

Nếu bot ngưng hoặc Render deploy lại:

```bash
python3 skibidi_fixed_v3_full_embed_v2style.py
````

Bot sẽ:

1. Mở Flask server ở port `8080`
2. Tự tạo route `/` (cho UptimeRobot) và `/healthz` (cho Render check)
3. Delay 3 giây cho Flask bind port
4. Sau đó khởi động Discord bot

---

## 🧩 Biến môi trường cần có

Khai báo sẵn trong Render Secret hoặc `.env`:

```
TOKEN=discord_bot_token
ROLE_NAME=💤 Tín Đồ Ngủ Đông
INACTIVE_DAYS=30
PORT=8080
```

---

## ⚙️ Kiểm tra hoạt động

| Cách                | Mục đích                        | Kết quả mong đợi         |
| ------------------- | ------------------------------- | ------------------------ |
| Truy cập `/`        | Giữ bot sống (UptimeRobot ping) | 🟢 Bot đang chạy ổn định |
| Truy cập `/healthz` | Health check Render             | OK                       |
| `!test`             | Test bot có hoạt động không     | Embed xanh lá hiện ra    |
| `!runcheck`         | Kiểm tra thủ công               | Embed xanh lá khi xong   |
| `!config_info`      | Xem cấu hình hiện tại           | Hiển thị role, ngày, DB  |

---

## 💾 Database (`inactivity.db`)

* Tự tạo nếu chưa tồn tại.
* Lưu `member_id`, `guild_id`, `last_seen`, `role_added`.
* Không cần backup thường xuyên (nhưng có thể export nếu muốn).

### Backup thủ công:

```bash
!exportdb
```

### Xuất CSV (dễ đọc):

```bash
!exportcsv
```

---

## 🔁 Các task định kỳ

* Bot chạy `check_inactivity()` mỗi **24 giờ/lần**.
* Kiểm tra toàn bộ thành viên trong server:

  * Nếu offline ≥ 30 ngày → gán role “💤 Tín Đồ Ngủ Đông”
  * Cập nhật `last_seen` nếu offline.

---

## 🧰 Debug nhanh

| Vấn đề                                | Nguyên nhân thường gặp                   | Cách xử lý                               |
| ------------------------------------- | ---------------------------------------- | ---------------------------------------- |
| Bot không start trên Render           | Flask chiếm port chưa kịp mở             | Kiểm tra có `time.sleep(3)` ở cuối       |
| “Bad Gateway” / “Service Unavailable” | Chưa có `/healthz` hoặc Flask chưa start | Đảm bảo route `/healthz` tồn tại         |
| Không thấy role “💤 Tín Đồ Ngủ Đông”  | Role chưa tạo trên server                | Tạo role và cho bot quyền quản lý        |
| Bot không add role                    | Bot thiếu quyền `Manage Roles`           | Cấp quyền trong Discord                  |
| Database lỗi                          | File `.db` bị lock                       | Stop bot → xóa `inactivity.db` → restart |

---

## 🧹 Reset nhẹ (nếu cần)

Muốn bot “làm lại từ đầu” (xóa DB cũ):

```bash
rm inactivity.db
python3 skibidi_fixed_v3_full_embed_v2style.py
```

---

## 🧠 Ghi nhớ

* **Flask luôn chạy nền trước bot**
* **Không cần Replit keepalive** vì `/healthz` đã lo
* **SQLite an toàn và tự động**
* **Không nên auto deploy quá thường xuyên** (vì Render vẫn log restart như “loop” nếu ping trùng thời điểm build)

---

## 💬 Ghi chú riêng

> “Bot này không cần nhiều tiền — chỉ cần hiểu cách nó thở.”
> — *Khải Trần, 2025*

```

---

📄 Bạn chỉ cần lưu nó thành file `README_INTERNAL.md` trong repo là xong.  
Nếu muốn, mình có thể thêm **một block “Lịch sử thay đổi (Changelog)”** ở cuối file để bạn dễ theo dõi các phiên bản bot (v2, v3, v3_fix...) — muốn mình thêm luôn không?
```
