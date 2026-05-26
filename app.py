from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
from geopy.distance import geodesic
from zoneinfo import ZoneInfo
import json
import gspread
import os

from oauth2client.service_account import ServiceAccountCredentials

# =========================================
# FLASK APP
# =========================================

app = Flask(__name__)

# =========================================
# INDIA TIMEZONE
# =========================================

IST = ZoneInfo("Asia/Kolkata")

# =========================================
# OFFICE LOCATION
# =========================================

OFFICE_LAT = 13.056600
OFFICE_LON = 80.2541370
ALLOWED_RADIUS = 35  # meters

# =========================================
# GOOGLE SHEETS SETUP ✅
# =========================================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# ✅ Use your JSON file directly
creds = ServiceAccountCredentials.from_json_keyfile_name(
    "D:/Profile/Documents/Attedence Tracking/Attedence Tracking/service_account.json",
    scope
)

client = gspread.authorize(creds)

# =========================================
# GOOGLE SHEET ✅
# =========================================

SHEET_ID = "1KteRJa0GenikpFQpFCBGvh6HS_jSDl-HHItrORwWRcE"

sheet = client.open_by_key(SHEET_ID).sheet1

# =========================================
# LOAD EMPLOYEES
# =========================================

with open("D:/Profile/Documents/Attedence Tracking/Attedence Tracking/employees.json", "r", encoding="utf-8") as f:
    employees = json.load(f)
# =========================================
# HOME PAGE
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

    # Employee check
    if emp_id not in employees:
        return jsonify({'success': False, 'message': 'Invalid Employee ID ❌'})

    employee = employees[emp_id]

    # OTP check
    if otp.strip() != employee['otp']:
        return jsonify({'success': False, 'message': 'Wrong OTP ❌'})

    # Location check
    distance = geodesic((OFFICE_LAT, OFFICE_LON), (lat, lon)).meters

    if distance > ALLOWED_RADIUS:
        return jsonify({
            'success': False,
            'message': f'Outside Office Radius ({int(distance)}m) ❌'
        })

    now = datetime.now(IST)
    date_str = now.strftime('%d-%m-%Y')
    time_str = now.strftime('%I:%M %p')

    records = sheet.get_all_records()
    found_row = None

    # Find today's record
    for i, rec in enumerate(records, start=2):
        if str(rec['Employee ID']) == emp_id and rec['Date'] == date_str:
            found_row = i
            break

    # Device check
    for rec in records:
        if (rec.get('Device ID') == device_id and
            str(rec['Employee ID']) != emp_id and
            rec['Date'] == date_str):
            return jsonify({
                'success': False,
                'message': 'Mobile already used today ❌'
            })

    # =====================================
    # PUNCH IN
    # =====================================

    if action == 'in':
        if found_row:
            return jsonify({'success': False, 'message': 'Already Punched IN ✅'})

        current_min = now.hour * 60 + now.minute

        if current_min <= (9 * 60 + 5):
            status = 'On Time ✅'
        else:
            late = current_min - (9 * 60)
            status = f'{late} mins Late ⏰'

        sheet.append_row([
            date_str, emp_id, employee['name'],
            time_str, '', status, '', '', device_id
        ])

        return jsonify({
            'success': True,
            'name': employee['name'],
            'time': time_str,
            'status': status,
            'message': 'Punch IN Success ✅'
        })

    # =====================================
    # PUNCH OUT
    # =====================================

    elif action == 'out':
        if not found_row:
            return jsonify({'success': False, 'message': 'Punch IN missing ❌'})

        if sheet.cell(found_row, 5).value:
            return jsonify({'success': False, 'message': 'Already Punched OUT ✅'})

        in_time = sheet.cell(found_row, 4).value

        current_min = now.hour * 60 + now.minute
        office_out = 17 * 60 + 30

        if current_min < office_out:
            status = f'{office_out - current_min} mins Early Exit 🚶'
        elif current_min <= office_out + 20:
            status = 'On Time Exit ✅'
        else:
            status = f'{current_min - office_out} mins Extra 🔥'

        # Working hours
        in_dt = datetime.strptime(in_time, '%I:%M %p')
        out_dt = datetime.strptime(time_str, '%I:%M %p')

        if out_dt < in_dt:
            out_dt += timedelta(days=1)

        diff = out_dt - in_dt
        hrs = diff.seconds // 3600
        mins = (diff.seconds % 3600) // 60

        work_time = f"{hrs} hrs {mins} mins"

        sheet.update_cell(found_row, 5, time_str)
        sheet.update_cell(found_row, 7, status)
        sheet.update_cell(found_row, 8, work_time)

        return jsonify({
            'success': True,
            'time': time_str,
            'status': status,
            'working_hours': work_time,
            'message': 'Punch OUT Success ✅'
        })

    return jsonify({'success': False, 'message': 'Invalid Action ❌'})

# =========================================
# RUN APP
# =========================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
