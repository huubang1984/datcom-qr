# 🍱 Đặt Cơm QR

Ứng dụng đăng ký đặt cơm trưa qua quét mã QR cho nhân viên, dành cho bộ phận HCNS theo dõi và trừ tiền cơm cuối tháng.

## Luồng sử dụng

**Nhân viên** (quét 1 mã QR dùng chung):
1. Quét QR → mở trang web → nhập **mã nhân viên**
2. Màn hình hiện **tên** để xác nhận đúng người + trạng thái
3. Chọn ngày **Hôm nay / Ngày mai**, rồi **Đăng ký** / **Hủy** / **Xác nhận đã nhận cơm**
4. Nhập **mã PIN** để xác nhận (tránh nhầm/đặt hộ)
5. Hệ thống tự ghi nhận ngày giờ

> Đặt trước cho **ngày mai** không bị giới hạn giờ chốt; HC có thể bật/tắt tính năng này trong Cấu hình. Nhận cơm chỉ áp dụng cho suất của hôm nay.

**Cơ chế chặn quét trùng:**
- Mỗi nhân viên chỉ đăng ký **1 suất/ngày** (chặn ở tầng DB bằng unique constraint).
- Khi nhận cơm: phải đã đăng ký trước đó; đã xác nhận nhận rồi thì **không xác nhận lại được**.
- Quá giờ chốt đăng ký (cấu hình được) sẽ bị từ chối.

**HCNS** (`/admin`):
- **Hôm nay**: số suất đăng ký, đã nhận, chưa nhận; danh sách chi tiết theo ngày.
- **Nhân viên**: thêm/sửa NV, đặt lại PIN, khóa/mở.
- **Báo cáo tháng**: số ngày đặt × đơn giá = tiền trừ mỗi NV; xuất **CSV (mở bằng Excel)**.
- **Mã QR**: sinh & in mã QR poster.
- **Cấu hình**: đơn giá suất cơm, giờ chốt đăng ký, bật/tắt đặt trước cho ngày mai.

## Chạy local (Windows / PowerShell)

```powershell
cd D:\Claude\DatCom_QR
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed.py        # tạo admin + vài NV mẫu
python app.py         # chạy ở http://localhost:5000
```

- Trang nhân viên: http://localhost:5000
- Trang HCNS: http://localhost:5000/admin (mặc định `hcns` / `hcns@123`)

Tài khoản & NV mẫu (xem `seed.py`): NV001/PIN 1234, NV002/2345, NV003/3456, NV004/4567.

## Deploy lên Render (khuyến nghị)

Repo đã có sẵn `render.yaml` (Blueprint) tự dựng **web service + PostgreSQL miễn phí**.

1. Đẩy code lên GitHub:
   ```powershell
   cd D:\Claude\DatCom_QR
   git init && git add . && git commit -m "Đặt cơm QR"
   git branch -M main
   git remote add origin https://github.com/<tai-khoan>/datcom-qr.git
   git push -u origin main
   ```
2. Vào [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint** → chọn repo vừa đẩy. Render đọc `render.yaml` và tạo:
   - Web service `datcom-qr` (Python 3.12, gunicorn)
   - Database PostgreSQL `datcom-db` (tự nối qua `DATABASE_URL`)
3. Khi được hỏi, **nhập `ADMIN_PASSWORD`** (mật khẩu đăng nhập HCNS). `SECRET_KEY` Render tự sinh.
4. Bấm **Apply** → chờ build xong. App tự tạo bảng + tài khoản admin (`ADMIN_USERNAME`/`ADMIN_PASSWORD`) ngay lần chạy đầu — **không cần chạy `seed.py`**.
5. Mở app tại URL Render cấp (vd `https://datcom-qr.onrender.com`), đăng nhập `/admin`, vào **Nhân viên → Import** để nạp danh sách, rồi **Mã QR** để in poster với tên miền thật.

> **Lưu ý gói free:** service "ngủ" sau ~15 phút không truy cập (lần quét đầu sẽ chậm vài giây để khởi động lại) và Postgres free có thời hạn — đủ cho pilot, nâng gói khi chạy chính thức.

## Deploy nền tảng khác (Railway / Heroku)

Dùng `Procfile` có sẵn. Đặt biến môi trường `SECRET_KEY`, `DATABASE_URL` (Postgres), `ADMIN_USERNAME`, `ADMIN_PASSWORD`. Admin được tạo tự động từ env lúc khởi động.

> SQLite trên cloud thường dùng filesystem tạm → mất dữ liệu khi restart. Luôn dùng PostgreSQL qua `DATABASE_URL` cho production (đã hỗ trợ sẵn).

## Cấu trúc

```
app.py              # Flask app + toàn bộ route (NV + admin)
models.py           # Employee, MealOrder, Admin, Setting + helper giờ VN
config.py           # cấu hình DB / secret
seed.py             # tạo admin + NV mẫu
templates/          # giao diện (index = NV, admin_* = HCNS)
static/             # style.css, app.js
```
