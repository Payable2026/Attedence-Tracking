from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
from geopy.distance import geodesic
from zoneinfo import ZoneInfo
import json
import gspread
import os

from dotenv import load_dotenv
load_dotenv()

from google.oauth2.service_account import Credentials

app = Flask(__name__)

# =========================================
# TIMEZONE
# =========================================
IST = ZoneInfo("Asia/Kolkata")

# =========================================
# OFFICE LOCATION
# =========================================
OFFICE_LAT = 13.056600
OFFICE_LON = 80.2541370
DEFAULT_RADIUS = 35

# =========================================
# GOOGLE SHEETS AUTH
# =========================================
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_raw = os.environ.get("GOOGLE_CREDENTIALS")

if creds_raw:
    creds_dict = json.loads(creds_raw)
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=scope
    )
else:
    creds = Credentials.from_service_account_file(
        "service_account.json",
        scopes=scope
    )

client = gspread.authorize(creds)

# =========================================
# GOOGLE SHEET
# =========================================
SHEET_ID = "1KteRJa0GenikpFQpFCBGvh6HS_jSDl-HHItrORwWRcE"
sheet = client.open_by_key(SHEET_ID).sheet1

# =========================================
# EMPLOYEES
# =========================================
with open("employees.json", "r", encoding="utf-8") as f:
    employees = json.load(f)

# =========================================
# HOME
# =========================================
@app.route('/')
def home():
    return render_template('index.html')


# =========================================
# GET EMPLOYEE
# =========================================
@app.route('/get_employee', methods=['POST'])
def get_employee():
    data = request.json
    emp_id = data.get('emp_id')

    if emp_id in employees:
        emp = employees[emp_id]
        return jsonify({
            'success': True,
            'name': emp['name'],
            'phone': emp['phone']
        })

    return jsonify({
        'success': False,
        'message': 'Employee Not Found ❌'
    })


# =========================================
# ATTENDANCE
# =========================================
@app.route('/attendance', methods=['POST'])
def attendance():
    data = request.json

    emp_id = data.get('emp_id')
    otp = data.get('otp')
    lat = float(data.get('lat'))
    lon = float(data.get('lon'))
    action = data.get('action')
    device_id = data.get('device_id')

    # ✅ Employee check
    if emp_id not in employees:
        return jsonify({'success': False, 'message': 'Invalid Employee ID ❌'})

    employee = employees[emp_id]

    # ✅ OTP check
    if otp.strip() != employee['otp']:
        return jsonify({'success': False, 'message': 'Wrong OTP ❌'})

    # ✅ Location validation
    emp_radius = employee.get('radius', DEFAULT_RADIUS)
    distance = geodesic((OFFICE_LAT, OFFICE_LON), (lat, lon)).meters

    if distance > emp_radius:
        return jsonify({
            'success': False,
            'message': f'Outside Radius ({int(distance)}m > {emp_radius}m) ❌'
        })

    # ✅ Time
    now = datetime.now(IST)
    date_str = now.strftime('%d-%m-%Y')
    time_str = now.strftime('%I:%M %p')

    records = sheet.get_all_records()

    # ✅ Device restriction
    for rec in records:
        if (
            rec.get('Device ID') == device_id and
            str(rec['Employee ID']) != emp_id and
            rec['Date'] == date_str
        ):
            return jsonify({
                'success': False,
                'message': 'Device already used ❌'
            })

    # ======================
    # ✅ PUNCH IN
    # ======================
    if action == 'in':

        current_minutes = now.hour * 60 + now.minute
        office_in = 9 * 60
        grace = office_in + 5

        if current_minutes <= grace:
            in_status = "On Time ✅"
        else:
            late = current_minutes - office_in
            in_status = f"{late} mins Late ⏰"

        sheet.append_row([
            date_str, emp_id, employee['name'],
            time_str, '', in_status, '', '', device_id
        ])

        return jsonify({
            'success': True,
            'name': employee['name'],
            'time': time_str,
            'status': in_status
        })

    # ======================
    # ✅ PUNCH OUT
    # ======================
    elif action == 'out':

        sessions = []

        for i, rec in enumerate(records, start=2):
            if str(rec['Employee ID']) == emp_id and rec['Date'] == date_str:
                sessions.append((i, rec['In Time'], rec['Out Time']))

        if not sessions:
            return jsonify({'success': False, 'message': 'No Punch IN ❌'})

        # ✅ find last open session
        target = None

        for row, in_t, out_t in reversed(sessions):
            if not out_t:
                target = (row, in_t)
                break

        if not target:
            return jsonify({'success': False, 'message': 'Already OUT ✅'})

        row_index, in_time = target

        in_dt = datetime.strptime(in_time.strip(), '%I:%M %p')
        out_dt = datetime.strptime(time_str.strip(), '%I:%M %p')

        if out_dt < in_dt:
            out_dt += timedelta(days=1)

        sheet.update_cell(row_index, 5, time_str)

        # ✅ TOTAL WORK HOURS
        total_seconds = 0
        first_in = None

        for row, in_t, out_t in sessions:

            if not in_t:
                continue

            in_obj = datetime.strptime(in_t.strip(), '%I:%M %p')

            if not first_in:
                first_in = in_obj

            if out_t:
                out_obj = datetime.strptime(out_t.strip(), '%I:%M %p')
            else:
                out_obj = out_dt

            if out_obj < in_obj:
                out_obj += timedelta(days=1)

            total_seconds += (out_obj - in_obj).seconds

        hrs = total_seconds // 3600
        mins = (total_seconds % 3600) // 60

        working_hours = f"{hrs} hrs {mins} mins"

        # ✅ FIRST IN STATUS
        first_minutes = first_in.hour * 60 + first_in.minute
        office_in = 9 * 60

        if first_minutes <= office_in + 5:
            in_status = "On Time ✅"
        else:
            late = first_minutes - office_in
            in_status = f"{late} mins Late ⏰"

        # ✅ LAST OUT STATUS
        current_minutes = now.hour * 60 + now.minute
        office_out = 17 * 60 + 30

        if current_minutes < office_out:
            early = office_out - current_minutes
            out_status = f"{early} mins Early Exit 🚶"
        elif current_minutes <= office_out + 20:
            out_status = "On Time Exit ✅"
        else:
            extra = current_minutes - office_out
            out_status = f"{extra} mins Additional Stay 🔥"

        first_row = sessions[0][0]

        sheet.update_cell(first_row, 6, in_status)
        sheet.update_cell(row_index, 7, out_status)
        sheet.update_cell(row_index, 8, working_hours)

        return jsonify({
            'success': True,
            'name': employee['name'],
            'time': time_str,
            'status': out_status,
            'working_hours': working_hours,
            'message': 'Punch OUT Success ✅'
        })

    return jsonify({'success': False, 'message': 'Invalid Action ❌'})


# =========================================
# RUN
# =========================================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )