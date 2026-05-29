"""Khởi tạo dữ liệu mẫu: 1 tài khoản HCNS + vài nhân viên để thử nghiệm.

Chạy: python seed.py
"""
import os

from app import app
from models import db, Admin, Employee

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "hcns")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "hcns@123")

SAMPLE_EMPLOYEES = [
    # (mã NV, họ tên, phòng ban, PIN)
    ("NV001", "Nguyễn Văn An", "Kế toán", "1234"),
    ("NV002", "Trần Thị Bình", "HCNS", "2345"),
    ("NV003", "Lê Hoàng Cường", "Kỹ thuật", "3456"),
    ("NV004", "Phạm Thị Dung", "Kinh doanh", "4567"),
]


def main():
    with app.app_context():
        db.create_all()

        if not Admin.query.filter_by(username=ADMIN_USERNAME).first():
            admin = Admin(username=ADMIN_USERNAME)
            admin.set_password(ADMIN_PASSWORD)
            db.session.add(admin)
            print(f"Đã tạo admin: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
        else:
            print(f"Admin '{ADMIN_USERNAME}' đã tồn tại, bỏ qua.")

        for code, name, dept, pin in SAMPLE_EMPLOYEES:
            if Employee.query.filter_by(code=code).first():
                continue
            emp = Employee(code=code, name=name, department=dept, active=True)
            emp.set_pin(pin)
            db.session.add(emp)
            print(f"Đã thêm NV: {code} - {name} (PIN {pin})")

        db.session.commit()
        print("Hoàn tất seed.")


if __name__ == "__main__":
    main()
