from datetime import datetime
from zoneinfo import ZoneInfo

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def vn_now():
    """Thời điểm hiện tại theo giờ Việt Nam, trả về datetime naive để lưu DB nhất quán."""
    return datetime.now(VN_TZ).replace(tzinfo=None)


def vn_today():
    return vn_now().date()


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)  # mã nhân viên
    name = db.Column(db.String(128), nullable=False)
    department = db.Column(db.String(128))
    pin_hash = db.Column(db.String(256), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=vn_now)

    orders = db.relationship("MealOrder", backref="employee", lazy=True)

    def set_pin(self, pin):
        self.pin_hash = generate_password_hash(pin)

    def check_pin(self, pin):
        return check_password_hash(self.pin_hash, pin)


class MealOrder(db.Model):
    __tablename__ = "meal_orders"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    order_date = db.Column(db.Date, nullable=False, index=True)
    registered_at = db.Column(db.DateTime, nullable=False)
    picked_up_at = db.Column(db.DateTime)  # null = chưa nhận cơm

    # Mỗi nhân viên chỉ có 1 suất/ngày -> chặn quét trùng ở tầng DB.
    __table_args__ = (
        db.UniqueConstraint("employee_id", "order_date", name="uq_employee_order_date"),
    )


class Admin(db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(256))


DEFAULT_SETTINGS = {
    "meal_price": "30000",          # giá 1 suất cơm (VND)
    "register_cutoff": "10:00",     # giờ chốt đăng ký trong ngày (HH:MM)
    "register_cutoff_enabled": "1", # 1 = bật giới hạn giờ đăng ký, 0 = đăng ký cả ngày
    "cancel_cutoff": "10:00",       # giờ chốt hủy đăng ký trong ngày (HH:MM)
    "cancel_cutoff_enabled": "1",   # 1 = bật giới hạn giờ hủy, 0 = cho hủy cả ngày
    "allow_next_day": "1",          # 1 = cho phép đặt cơm cho ngày mai, 0 = chỉ hôm nay
}


def get_setting(key, default=None):
    s = db.session.get(Setting, key)
    if s is not None:
        return s.value
    return DEFAULT_SETTINGS.get(key, default)


def set_setting(key, value):
    s = db.session.get(Setting, key)
    if s is None:
        s = Setting(key=key, value=str(value))
        db.session.add(s)
    else:
        s.value = str(value)
