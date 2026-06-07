from flask import Flask, request, jsonify
from sqlalchemy import create_engine, text
from datetime import datetime, date, timedelta
import os

try:
    from dateutil.parser import parse as parse_date
except Exception:
    def parse_date(v):
        if isinstance(v, (date, datetime)):
            return v
        return datetime.fromisoformat(v)

app = Flask(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///leave_demo.db')
engine = create_engine(DATABASE_URL, future=True)


def days_inclusive(a: date, b: date) -> int:
    return (b - a).days + 1


def count_business_days(a: date, b: date) -> int:
    days = 0
    cur = a
    while cur <= b:
        if cur.weekday() < 5:  # 0..4 => Mon..Fri
            days += 1
        cur += timedelta(days=1)
    return days


@app.route('/api/remaining_leave')
def remaining_leave():
    emp_id = request.args.get('employee_id', type=int)
    if not emp_id:
        return jsonify(error='employee_id required'), 400

    year = request.args.get('year', type=int) or datetime.now().year
    business_days = request.args.get('business_days', 'false').lower() == 'true'

    # Fetch employee quota
    with engine.connect() as conn:
        q = text('SELECT annual_leave_quota FROM employees WHERE id = :id')
        r = conn.execute(q, {'id': emp_id}).fetchone()
        quota = int(r[0]) if r and r[0] is not None else 20

        # Fetch approved leaves for employee
        q2 = text("SELECT start_date, end_date FROM leave_requests WHERE employee_id = :id AND status = 'approved'")
        rows = conn.execute(q2, {'id': emp_id}).fetchall()

    # compute used days within the requested year
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    used = 0
    for row in rows:
        s = parse_date(row[0]).date() if row[0] is not None else None
        e = parse_date(row[1]).date() if row[1] is not None else None
        if s is None or e is None:
            continue
        # find overlap with the year
        start = max(s, year_start)
        end = min(e, year_end)
        if start > end:
            continue
        if business_days:
            used += count_business_days(start, end)
        else:
            used += days_inclusive(start, end)

    available = max(quota - used, 0)

    return jsonify(
        employee_id=emp_id,
        year=year,
        annual_leave_quota=quota,
        used_days=used,
        leaves_available=available,
    )


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
