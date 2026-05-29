import csv
import io
import os
from datetime import datetime, date, time
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, flash, Response, abort,
)
from sqlalchemy.exc import IntegrityError

from config import Config
from models import (
    db, Employee, MealOrder, Admin, Setting,
    vn_now, vn_today, get_setting, set_setting, DEFAULT_SETTINGS,
)


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        _bootstrap_admin()

    register_employee_routes(app)
    register_admin_routes(app)
    return app


def _bootstrap_admin():
    """Tự tạo tài khoản admin từ biến môi trường nếu chưa có (tiện cho deploy cloud)."""
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    if not (username and password):
        return
    if Admin.query.filter_by(username=username).first():
        return
    admin = Admin(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()


# ---------------------------------------------------------------------------
# Luồng nhân viên (sau khi quét QR)
# ---------------------------------------------------------------------------

def register_employee_routes(app):

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.post("/api/lookup")
    def api_lookup():
        """Bước 1: nhập mã NV -> trả tên để xác nhận đúng người + trạng thái hôm nay."""
        data = request.get_json(silent=True) or {}
        code = (data.get("code") or "").strip()
        if not code:
            return jsonify(ok=False, error="Vui lòng nhập mã nhân viên."), 400

        emp = Employee.query.filter_by(code=code).first()
        if emp is None or not emp.active:
            return jsonify(ok=False, error="Không tìm thấy mã nhân viên hoặc đã bị khóa."), 404

        order = MealOrder.query.filter_by(employee_id=emp.id, order_date=vn_today()).first()
        return jsonify(
            ok=True,
            name=emp.name,
            department=emp.department or "",
            registered=order is not None,
            picked_up=bool(order and order.picked_up_at),
        )

    @app.post("/api/register")
    def api_register():
        """Đăng ký đặt cơm cho hôm nay. Chặn nếu đã đặt rồi."""
        emp, err, status = _authenticate()
        if err:
            return jsonify(ok=False, error=err), status

        cutoff_err = _cutoff_blocked()
        if cutoff_err:
            return jsonify(ok=False, error=cutoff_err), 409

        existing = MealOrder.query.filter_by(employee_id=emp.id, order_date=vn_today()).first()
        if existing is not None:
            return jsonify(
                ok=False,
                error="Bạn đã đăng ký đặt cơm hôm nay rồi.",
                duplicate=True,
            ), 409

        now = vn_now()
        order = MealOrder(employee_id=emp.id, order_date=now.date(), registered_at=now)
        db.session.add(order)
        try:
            db.session.commit()
        except IntegrityError:
            # Trường hợp 2 lần quét gần như đồng thời -> unique constraint chặn
            db.session.rollback()
            return jsonify(ok=False, error="Bạn đã đăng ký đặt cơm hôm nay rồi.", duplicate=True), 409

        return jsonify(ok=True, message="Đăng ký đặt cơm thành công!",
                       time=now.strftime("%H:%M %d/%m/%Y"))

    @app.post("/api/pickup")
    def api_pickup():
        """Xác nhận đã nhận cơm. Chặn nếu chưa đăng ký hoặc đã nhận."""
        emp, err, status = _authenticate()
        if err:
            return jsonify(ok=False, error=err), status

        order = MealOrder.query.filter_by(employee_id=emp.id, order_date=vn_today()).first()
        if order is None:
            return jsonify(ok=False, error="Bạn chưa đăng ký đặt cơm hôm nay."), 409
        if order.picked_up_at is not None:
            return jsonify(
                ok=False,
                error="Bạn đã xác nhận nhận cơm rồi.",
                duplicate=True,
            ), 409

        now = vn_now()
        order.picked_up_at = now
        db.session.commit()
        return jsonify(ok=True, message="Đã xác nhận nhận cơm!",
                       time=now.strftime("%H:%M %d/%m/%Y"))

    @app.post("/api/cancel")
    def api_cancel():
        """Hủy đăng ký đặt cơm hôm nay. Chặn nếu chưa đăng ký, đã nhận, hoặc quá giờ chốt."""
        emp, err, status = _authenticate()
        if err:
            return jsonify(ok=False, error=err), status

        order = MealOrder.query.filter_by(employee_id=emp.id, order_date=vn_today()).first()
        if order is None:
            return jsonify(ok=False, error="Bạn chưa đăng ký đặt cơm hôm nay."), 409
        if order.picked_up_at is not None:
            return jsonify(ok=False, error="Đã nhận cơm rồi, không thể hủy."), 409

        cutoff_err = _cutoff_blocked()
        if cutoff_err:
            return jsonify(ok=False, error="Đã quá giờ, không thể hủy đăng ký."), 409

        db.session.delete(order)
        db.session.commit()
        return jsonify(ok=True, message="Đã hủy đăng ký đặt cơm.",
                       time=vn_now().strftime("%H:%M %d/%m/%Y"))


def _authenticate():
    """Xác thực mã NV + PIN. Trả (employee, error, http_status)."""
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    pin = (data.get("pin") or "").strip()
    if not code or not pin:
        return None, "Thiếu mã nhân viên hoặc mã PIN.", 400

    emp = Employee.query.filter_by(code=code).first()
    if emp is None or not emp.active:
        return None, "Không tìm thấy mã nhân viên hoặc đã bị khóa.", 404
    if not emp.check_pin(pin):
        return None, "Mã PIN không đúng.", 401
    return emp, None, None


def _parse_hhmm(s):
    try:
        h, m = s.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return None


def _cutoff_blocked():
    """Trả thông báo lỗi nếu đã quá giờ chốt đăng ký, ngược lại trả None."""
    if get_setting("register_cutoff_enabled", "1") != "1":
        return None
    cutoff_str = get_setting("register_cutoff", "10:00")
    cutoff = _parse_hhmm(cutoff_str)
    if cutoff and vn_now().time() > cutoff:
        return f"Đã quá giờ đăng ký ({cutoff_str}). Vui lòng đăng ký sớm hơn."
    return None


# ---------------------------------------------------------------------------
# Khu vực quản trị (HCNS)
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def register_admin_routes(app):

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            admin = Admin.query.filter_by(username=username).first()
            if admin and admin.check_password(password):
                session["admin_id"] = admin.id
                session["admin_username"] = admin.username
                nxt = request.args.get("next") or url_for("admin_dashboard")
                return redirect(nxt)
            flash("Sai tài khoản hoặc mật khẩu.", "error")
        return render_template("admin_login.html")

    @app.route("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect(url_for("admin_login"))

    @app.route("/admin")
    @login_required
    def admin_dashboard():
        d_str = request.args.get("date")
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date() if d_str else vn_today()
        except ValueError:
            d = vn_today()

        orders = (
            MealOrder.query.filter_by(order_date=d)
            .join(Employee).order_by(MealOrder.registered_at).all()
        )
        total = len(orders)
        picked = sum(1 for o in orders if o.picked_up_at)
        return render_template(
            "admin_dashboard.html",
            orders=orders, day=d, total=total, picked=picked,
            not_picked=total - picked,
        )

    # ----- Quản lý nhân viên -----
    @app.route("/admin/employees")
    @login_required
    def admin_employees():
        emps = Employee.query.order_by(Employee.code).all()
        return render_template("admin_employees.html", employees=emps)

    @app.post("/admin/employees/add")
    @login_required
    def admin_employee_add():
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        dept = request.form.get("department", "").strip()
        pin = request.form.get("pin", "").strip()
        if not (code and name and pin):
            flash("Mã NV, tên và PIN là bắt buộc.", "error")
            return redirect(url_for("admin_employees"))
        if Employee.query.filter_by(code=code).first():
            flash(f"Mã nhân viên '{code}' đã tồn tại.", "error")
            return redirect(url_for("admin_employees"))
        emp = Employee(code=code, name=name, department=dept, active=True)
        emp.set_pin(pin)
        db.session.add(emp)
        db.session.commit()
        flash(f"Đã thêm nhân viên {name}.", "success")
        return redirect(url_for("admin_employees"))

    @app.route("/admin/employees/template.csv")
    @login_required
    def admin_employee_template():
        buf = io.StringIO()
        buf.write("﻿")  # BOM cho Excel
        w = csv.writer(buf)
        w.writerow(["Ma NV", "Ho ten", "Phong ban", "PIN"])
        w.writerow(["NV010", "Nguyen Van Mau", "Ke toan", "1234"])
        w.writerow(["NV011", "Tran Thi Mau", "Kinh doanh", "5678"])
        return Response(
            buf.getvalue(), mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=mau_danh_sach_nv.csv"},
        )

    @app.post("/admin/employees/import")
    @login_required
    def admin_employee_import():
        f = request.files.get("file")
        if not f or not f.filename:
            flash("Vui lòng chọn file .xlsx hoặc .csv.", "error")
            return redirect(url_for("admin_employees"))
        try:
            rows = _parse_employee_file(f)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("admin_employees"))

        added, updated, skipped = 0, 0, 0
        for code, name, dept, pin in rows:
            if not code or not name:
                skipped += 1
                continue
            emp = Employee.query.filter_by(code=code).first()
            if emp is None:
                emp = Employee(code=code, name=name, department=dept, active=True)
                emp.set_pin(pin or code[-4:] or "0000")  # PIN mặc định = 4 ký tự cuối mã nếu trống
                db.session.add(emp)
                added += 1
            else:
                emp.name = name
                emp.department = dept
                if pin:
                    emp.set_pin(pin)
                updated += 1
        db.session.commit()
        flash(f"Import xong: thêm {added}, cập nhật {updated}, bỏ qua {skipped} dòng.", "success")
        return redirect(url_for("admin_employees"))

    @app.post("/admin/employees/<int:emp_id>/update")
    @login_required
    def admin_employee_update(emp_id):
        emp = db.session.get(Employee, emp_id) or abort(404)
        emp.name = request.form.get("name", emp.name).strip()
        emp.department = request.form.get("department", emp.department or "").strip()
        emp.active = request.form.get("active") == "on"
        new_pin = request.form.get("pin", "").strip()
        if new_pin:
            emp.set_pin(new_pin)
        db.session.commit()
        flash(f"Đã cập nhật {emp.name}.", "success")
        return redirect(url_for("admin_employees"))

    # ----- Báo cáo cuối tháng -----
    @app.route("/admin/report")
    @login_required
    def admin_report():
        month = request.args.get("month") or vn_today().strftime("%Y-%m")
        rows, price = _build_report(month)
        grand_total = sum(r["amount"] for r in rows)
        return render_template(
            "admin_report.html",
            month=month, rows=rows, price=price, grand_total=grand_total,
        )

    @app.route("/admin/report.csv")
    @login_required
    def admin_report_csv():
        month = request.args.get("month") or vn_today().strftime("%Y-%m")
        rows, price = _build_report(month)
        buf = io.StringIO()
        buf.write("﻿")  # BOM để Excel mở UTF-8 tiếng Việt đúng
        w = csv.writer(buf)
        w.writerow(["Ma NV", "Ho ten", "Phong ban", "So ngay dat", "So suat da nhan",
                    f"Don gia ({price:,} VND)", "Thanh tien (VND)"])
        for r in rows:
            w.writerow([r["code"], r["name"], r["department"], r["days"],
                        r["picked"], price, r["amount"]])
        out = buf.getvalue()
        return Response(
            out, mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=bao_cao_com_{month}.csv"},
        )

    # ----- QR poster -----
    @app.route("/admin/qr")
    @login_required
    def admin_qr():
        base_url = request.url_root  # URL gốc nơi app đang chạy
        return render_template("admin_qr.html", base_url=base_url)

    @app.route("/admin/qr.png")
    @login_required
    def admin_qr_png():
        import qrcode
        target = request.args.get("url") or request.url_root
        img = qrcode.make(target)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Response(buf.getvalue(), mimetype="image/png")

    # ----- Cấu hình -----
    @app.route("/admin/config", methods=["GET", "POST"])
    @login_required
    def admin_config():
        if request.method == "POST":
            set_setting("meal_price", request.form.get("meal_price", "30000").strip())
            set_setting("register_cutoff", request.form.get("register_cutoff", "10:00").strip())
            set_setting("register_cutoff_enabled",
                        "1" if request.form.get("register_cutoff_enabled") == "on" else "0")
            db.session.commit()
            flash("Đã lưu cấu hình.", "success")
            return redirect(url_for("admin_config"))
        cfg = {k: get_setting(k) for k in DEFAULT_SETTINGS}
        return render_template("admin_config.html", cfg=cfg)


def _match_columns(header):
    """Map tiêu đề cột -> chỉ số. Linh hoạt theo từ khóa tiếng Việt/Anh."""
    norm = [(h or "").strip().lower() for h in header]
    idx = {"code": None, "name": None, "dept": None, "pin": None}
    for i, h in enumerate(norm):
        if idx["code"] is None and ("mã" in h or "ma nv" in h or "code" in h or h == "ma"):
            idx["code"] = i
        elif idx["name"] is None and ("tên" in h or "ho ten" in h or "name" in h or h == "ten"):
            idx["name"] = i
        elif idx["dept"] is None and ("phòng" in h or "phong" in h or "dept" in h or "ban" in h):
            idx["dept"] = i
        elif idx["pin"] is None and "pin" in h:
            idx["pin"] = i
    return idx


def _parse_employee_file(f):
    """Đọc file NV (.xlsx/.csv) -> list (code, name, dept, pin)."""
    name = f.filename.lower()
    if name.endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        ws = wb.active
        table = [[("" if c is None else str(c)).strip() for c in row]
                 for row in ws.iter_rows(values_only=True)]
    elif name.endswith(".csv"):
        raw = f.read().decode("utf-8-sig", errors="replace")
        table = [row for row in csv.reader(io.StringIO(raw))]
    else:
        raise ValueError("Chỉ hỗ trợ file .xlsx hoặc .csv.")

    table = [r for r in table if any((c or "").strip() for c in r)]
    if not table:
        raise ValueError("File rỗng.")

    idx = _match_columns(table[0])
    if idx["code"] is not None and idx["name"] is not None:
        data_rows = table[1:]  # có dòng tiêu đề
    else:
        # Không nhận diện được tiêu đề -> giả định thứ tự cột: mã, tên, phòng ban, PIN
        idx = {"code": 0, "name": 1, "dept": 2, "pin": 3}
        data_rows = table

    def cell(row, key):
        i = idx[key]
        return row[i].strip() if (i is not None and i < len(row)) else ""

    out = []
    for row in data_rows:
        out.append((cell(row, "code"), cell(row, "name"), cell(row, "dept"), cell(row, "pin")))
    return out


def _build_report(month):
    """Tổng hợp số suất cơm theo nhân viên trong 1 tháng (YYYY-MM)."""
    try:
        year, mon = month.split("-")
        start = date(int(year), int(mon), 1)
    except (ValueError, AttributeError):
        start = vn_today().replace(day=1)
        month = start.strftime("%Y-%m")
    # Đầu tháng kế tiếp
    end = date(start.year + (1 if start.month == 12 else 0),
               1 if start.month == 12 else start.month + 1, 1)

    price = int(get_setting("meal_price", "30000") or 30000)

    orders = (
        MealOrder.query.filter(
            MealOrder.order_date >= start, MealOrder.order_date < end
        ).join(Employee).all()
    )
    agg = {}
    for o in orders:
        emp = o.employee
        r = agg.setdefault(emp.id, {
            "code": emp.code, "name": emp.name,
            "department": emp.department or "", "days": 0, "picked": 0,
        })
        r["days"] += 1
        if o.picked_up_at:
            r["picked"] += 1
    rows = sorted(agg.values(), key=lambda x: x["code"])
    for r in rows:
        r["amount"] = r["days"] * price
    return rows, price


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
