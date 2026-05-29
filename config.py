import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # Cho phép đổi sang PostgreSQL khi deploy cloud qua biến môi trường DATABASE_URL.
    # Mặc định dùng SQLite file canteen.db trong thư mục instance.
    _db_url = os.environ.get("DATABASE_URL", "sqlite:///canteen.db")
    # Một số nhà cung cấp cloud trả về scheme cũ "postgres://" -> SQLAlchemy cần "postgresql://".
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
