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

    # ✅ VALIDATION
    if emp_id not in employees:
        return jsonify({'success': False, 'message': 'Invalid Employee ❌'})

    employee = employees[emp_id]

    if otp.strip() != employee['otp']:
        return jsonify({'success': False, 'message': 'Wrong OTP ❌'})

    # ✅ LOCATION CHECK
    distance = geodesic((OFFICE_LAT, OFFICE_LON), (lat, lon)).meters
    if distance > employee.get('radius', DEFAULT_RADIUS):
        return jsonify({'success': False, 'message': 'Outside Radius ❌'})

    now = datetime.now(IST)
    date_str = now.strftime('%d-%m-%Y')
    time_str = now.strftime('%I:%M %p')

    records = sheet.get_all_records()
    found_row = None

    for i, rec in enumerate(records, start=2):
        if str(rec['Employee ID']) == emp_id and rec['Date'] == date_str:
            found_row = i
            break

    # ======================
    # ✅ PUNCH IN
    # ======================
    if action == 'in':

        current_minutes = now.hour * 60 + now.minute
        office_in = 9 * 60
        grace = office_in + 5

        if current_minutes <= grace:
            in_status = 'On Time ✅'
        else:
            late = current_minutes - office_in
            in_status = f'{late} mins Late ⏰'

        if not found_row:
            # ✅ First IN
            sheet.append_row([
                date_str, emp_id, employee['name'],
                time_str, '', in_status, '', '', json.dumps([])
            ])
        else:
            sessions = json.loads(sheet.cell(found_row, 9).value or "[]")

            # prevent double IN
            if len(sessions) > 0 and len(sessions[-1]) == 1:
                return jsonify({'success': False, 'message': 'Already IN ❌'})

            sessions.append([time_str])
            sheet.update_cell(found_row, 9, json.dumps(sessions))

        return jsonify({'success': True, 'message': 'IN Success ✅'})

    # ======================
    # ✅ PUNCH OUT
    # ======================
    elif action == 'out':

        if not found_row:
            return jsonify({'success': False, 'message': 'No IN Found ❌'})

        sessions = json.loads(sheet.cell(found_row, 9).value or "[]")

        if len(sessions) == 0 or len(sessions[-1]) == 2:
            return jsonify({'success': False, 'message': 'Already OUT ❌'})

        # ✅ Add OUT to last session
        sessions[-1].append(time_str)
        sheet.update_cell(found_row, 9, json.dumps(sessions))

        # ✅ CALCULATE WORK
        total_minutes = 0

        for i in sessions:
            if len(i) == 2:
                in_dt = datetime.strptime(i[0], '%I:%M %p')
                out_dt = datetime.strptime(i[1], '%I:%M %p')

                if out_dt < in_dt:
                    out_dt += timedelta(days=1)

                diff = out_dt - in_dt
                total_minutes += diff.seconds // 60

        # ✅ TOTAL HOURS
        hrs = total_minutes // 60
        mins = total_minutes % 60
        working_hours = f"{hrs} hrs {mins} mins"

        # ✅ FIRST IN & LAST OUT
        first_in = sessions[0][0]
        last_out = sessions[-1][1]

        sheet.update_cell(found_row, 4, first_in)
        sheet.update_cell(found_row, 5, last_out)
        sheet.update_cell(found_row, 8, working_hours)

        # ✅ OUT STATUS
        current_minutes = now.hour * 60 + now.minute
        office_out = 17 * 60 + 30

        if current_minutes < office_out:
            early = office_out - current_minutes
            out_status = f'{early} mins Early Exit 🚶'
        else:
            out_status = 'On Time Exit ✅'

        sheet.update_cell(found_row, 7, out_status)

        return jsonify({
            'success': True,
            'working_hours': working_hours,
            'message': 'OUT Success ✅'
        })

    return jsonify({'success': False})
    

# =========================================
# RUN
# =========================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)