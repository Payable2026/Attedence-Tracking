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
# LIVE COUNT
# =========================================
@app.route('/live_count')
def live_count():
    records = sheet.get_all_records()
    today = datetime.now(IST).strftime('%d-%m-%Y')

    count = sum(1 for r in records if r['Date'] == today)

    return jsonify({'count': count})

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

    # ✅ EMPLOYEE CHECK
    if emp_id not in employees:
        return jsonify({'success': False, 'message': 'Invalid Employee ID ❌'})

    employee = employees[emp_id]

    # ✅ OTP CHECK
    if otp.strip() != employee['otp']:
        return jsonify({'success': False, 'message': 'Wrong Year ❌'})

    # ✅ LOCATION CHECK
    emp_radius = employee.get('radius', DEFAULT_RADIUS)
    distance = geodesic((OFFICE_LAT, OFFICE_LON), (lat, lon)).meters

    if distance > emp_radius:
        return jsonify({
            'success': False,
            'message': f'Outside Allowed Radius ({int(distance)}m > {emp_radius}m) ❌'
        })

    now = datetime.now(IST)
    date_str = now.strftime('%d-%m-%Y')
    time_str = now.strftime('%I:%M %p')

    records = sheet.get_all_records()
    found_row = None

    # ✅ FIND TODAY RECORD
    for i, rec in enumerate(records, start=2):
        if str(rec['Employee ID']) == emp_id and rec['Date'] == date_str:
            found_row = i
            break

    # ✅ DEVICE CHECK
    for rec in records:
        if (
            rec.get('Device ID') == device_id and
            str(rec['Employee ID']) != emp_id and
            rec['Date'] == date_str
        ):
            return jsonify({
                'success': False,
                'message': 'This Mobile Already Used Today ❌'
            })

    # ======================
    # ✅ PUNCH IN
    # ======================
    if action == 'in':

        if not found_row:
            # First punch
            sheet.append_row([
                date_str, emp_id, employee['name'],
                time_str, '', 'On Time ✅', '', '', device_id
            ])
        else:
            # Prevent double IN without OUT
            in_times = (sheet.cell(found_row, 4).value or "").split(" / ")
            out_times = (sheet.cell(found_row, 5).value or "").split(" / ")

            if len(in_times) > len(out_times):
                return jsonify({
                    'success': False,
                    'message': 'Already IN, please Punch OUT first ❌'
                })

            existing_in = sheet.cell(found_row, 4).value or ""
            new_in = existing_in + " / " + time_str if existing_in else time_str
            sheet.update_cell(found_row, 4, new_in)

        return jsonify({
            'success': True,
            'name': employee['name'],
            'time': time_str,
            'message': 'Punch IN Success ✅'
        })

    # ======================
    # ✅ PUNCH OUT
    # ======================
    elif action == 'out':

        if not found_row:
            return jsonify({'success': False, 'message': 'Punch IN Not Found ❌'})

        in_times = (sheet.cell(found_row, 4).value or "").split(" / ")
        out_times = (sheet.cell(found_row, 5).value or "").split(" / ")

        if len(out_times) >= len(in_times):
            return jsonify({
                'success': False,
                'message': 'Already OUT, please Punch IN first ❌'
            })

        # ✅ Append OUT
        existing_out = sheet.cell(found_row, 5).value or ""
        new_out = existing_out + " / " + time_str if existing_out else time_str
        sheet.update_cell(found_row, 5, new_out)

        # ✅ CALCULATE TOTAL WORKING HOURS
        in_times = sheet.cell(found_row, 4).value.split(" / ")
        out_times = sheet.cell(found_row, 5).value.split(" / ")

        total_minutes = 0

        for i in range(min(len(in_times), len(out_times))):
            in_dt = datetime.strptime(in_times[i].strip(), '%I:%M %p')
            out_dt = datetime.strptime(out_times[i].strip(), '%I:%M %p')

            if out_dt < in_dt:
                out_dt += timedelta(days=1)

            diff = out_dt - in_dt
            total_minutes += diff.seconds // 60

        hrs = total_minutes // 60
        mins = total_minutes % 60

        working_hours = f"{hrs} hrs {mins} mins"

        sheet.update_cell(found_row, 8, working_hours)

        return jsonify({
            'success': True,
            'name': employee['name'],
            'time': time_str,
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