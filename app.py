from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
from geopy.distance import geodesic
from zoneinfo import ZoneInfo
import json
import gspread
import os
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

# =========================================
# INIT
# =========================================
load_dotenv()
app = Flask(__name__)

IST = ZoneInfo("Asia/Kolkata")

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

    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
else:
    creds = Credentials.from_service_account_file("service_account.json", scopes=scope)

client = gspread.authorize(creds)

# =========================================
# SHEET
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
        return jsonify({
            'success': True,
            'name': employees[emp_id]['name'],
            'phone': employees[emp_id]['phone']
        })

    return jsonify({'success': False, 'message': 'Employee Not Found ❌'})

# =========================================
# ATTENDANCE MAIN LOGIC
# =========================================
@app.route('/attendance', methods=['POST'])
def attendance():
    data = request.json

    emp_id = data.get('emp_id')
    otp = data.get('otp')
    lat = float(data.get('lat'))
    lon = float(data.get('lon'))
    device_id = data.get('device_id')

    # ✅ Employee validation
    if emp_id not in employees:
        return jsonify({'success': False, 'message': 'Invalid Employee ❌'})

    employee = employees[emp_id]

    # ✅ OTP validation
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

    now = datetime.now(IST)
    date_str = now.strftime('%d-%m-%Y')
    time_str = now.strftime('%I:%M %p')

    records = sheet.get_all_records()

    # ✅ Device restriction (same day)
    for rec in records:
        if (
            rec.get('Device ID') == device_id and
            str(rec['Employee ID']) != emp_id and
            rec['Date'] == date_str
        ):
            return jsonify({'success': False, 'message': 'Device already used ❌'})

    # =====================================
    # FIND TODAY ROW
    # =====================================
    row_index = None
    rec_data = None

    for i, rec in enumerate(records, start=2):
        if str(rec['Employee ID']) == emp_id and rec['Date'] == date_str:
            row_index = i
            rec_data = rec
            break

    # =====================================
    # ✅ FIRST PUNCH → IN
    # =====================================
    if not row_index:

        current_minutes = now.hour * 60 + now.minute
        office_in = 9 * 60

        if current_minutes <= office_in + 5:
            in_status = "On Time ✅"
        else:
            late = current_minutes - office_in
            in_status = f"{late} mins Late ⏰"

        sheet.append_row([
            date_str, emp_id, employee['name'],
            time_str, '', in_status, '', '0 hrs 0 mins', device_id
        ])

        return jsonify({
            'success': True,
            'message': 'Punch IN ✅',
            'time': time_str
        })

    # =====================================
    # ✅ NEXT PUNCH → UPDATE OUT ONLY
    # =====================================
    in_time = rec_data['In Time']

    if not in_time:
        return jsonify({'success': False, 'message': 'Invalid IN ❌'})

    # ✅ Update OUT TIME (overwrite)
    sheet.update_cell(row_index, 5, time_str)

    # ✅ Time calc
    in_dt = datetime.strptime(in_time.strip(), '%I:%M %p')
    out_dt = datetime.strptime(time_str.strip(), '%I:%M %p')

    if out_dt < in_dt:
        out_dt += timedelta(days=1)

    diff = out_dt - in_dt
    hrs = diff.seconds // 3600
    mins = (diff.seconds % 3600) // 60
    working_hours = f"{hrs} hrs {mins} mins"

    # ✅ IN STATUS (fixed)
    first_minutes = in_dt.hour * 60 + in_dt.minute
    office_in = 9 * 60

    if first_minutes <= office_in + 5:
        in_status = "On Time ✅"
    else:
        late = first_minutes - office_in
        in_status = f"{late} mins Late ⏰"

    # ✅ OUT STATUS (based on latest punch)
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

    # ✅ Update row
    sheet.update_cell(row_index, 6, in_status)
    sheet.update_cell(row_index, 7, out_status)
    sheet.update_cell(row_index, 8, working_hours)

    return jsonify({
        'success': True,
        'message': 'OUT Updated ✅',
        'out_time': time_str,
        'working_hours': working_hours,
        'status': out_status
    })

# =========================================
# RUN
# =========================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)