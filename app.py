from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
from geopy.distance import geodesic
from zoneinfo import ZoneInfo
import json
import gspread
import os

# ✅ ENV loader
from dotenv import load_dotenv
load_dotenv()

# ✅ NEW AUTH
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
ALLOWED_RADIUS = 35

# =========================================
# GOOGLE SHEETS AUTH
# =========================================

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = None

# ✅ TRY ENV
creds_raw = os.environ.get("GOOGLE_CREDENTIALS")

if creds_raw:
    try:
        creds_dict = json.loads(creds_raw)

        # ✅ FIX PRIVATE KEY
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=scope
        )

        print("✅ Using ENV credentials")

    except Exception as e:
        raise Exception(f"❌ ENV credential error: {e}")

else:
    # ✅ LOCAL FALLBACK
    print("⚠ Using local service_account.json")

    creds = Credentials.from_service_account_file(
        "service_account.json",
        scopes=scope
    )

# ✅ CONNECT
client = gspread.authorize(creds)

# =========================================
# SHEET
# =========================================

SHEET_ID = "1Ryj_plY3dJ6v9ZCE_QJXuR7vXdFHqFOHWwJb0ODQ6Js"

sheet = client.open_by_key(SHEET_ID).sheet1

# =========================================
# EMPLOYEES
# =========================================

with open("employees.json", "r") as f:
    employees = json.load(f)

# =========================================
# ROUTES
# =========================================

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/get_employee', methods=['POST'])
def get_employee():
    emp_id = request.json.get('emp_id')

    if emp_id in employees:
        emp = employees[emp_id]
        return jsonify({
            'success': True,
            'name': emp['name'],
            'phone': emp['phone']
        })

    return jsonify({'success': False, 'message': 'Employee Not Found ❌'})


@app.route('/live_count')
def live_count():
    records = sheet.get_all_records()
    today = datetime.now(IST).strftime('%d-%m-%Y')

    count = sum(1 for r in records if r['Date'] == today)

    return jsonify({'count': count})


@app.route('/attendance', methods=['POST'])
def attendance():
    try:
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
            return jsonify({'success': False, 'message': 'Wrong OTP ❌'})

        # ✅ LOCATION CHECK
        distance = geodesic(
            (OFFICE_LAT, OFFICE_LON),
            (lat, lon)
        ).meters

        if distance > ALLOWED_RADIUS:
            return jsonify({
                'success': False,
                'message': f'Outside Office ({int(distance)}m) ❌'
            })

        # ✅ TIME
        now = datetime.now(IST)
        date_str = now.strftime('%d-%m-%Y')
        time_str = now.strftime('%I:%M %p')

        records = sheet.get_all_records()
        found_row = None

        # ✅ FIND RECORD
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
                    'message': 'Device already used ❌'
                })

        # ✅ PUNCH IN
        if action == 'in':

            if found_row:
                return jsonify({'success': False, 'message': 'Already IN ✅'})

            current_minutes = now.hour * 60 + now.minute
            office_in = 9 * 60

            if current_minutes <= office_in + 5:
                in_status = 'On Time ✅'
            else:
                late = current_minutes - office_in
                in_status = f'{late} mins Late ⏰'

            sheet.append_row([
                date_str,
                emp_id,
                employee['name'],
                time_str,
                '',
                in_status,
                '',
                '',
                device_id
            ])

            return jsonify({
                'success': True,
                'name': employee['name'],
                'time': time_str,
                'status': in_status
            })

        # ✅ PUNCH OUT
        elif action == 'out':

            if not found_row:
                return jsonify({'success': False, 'message': 'No IN ❌'})

            if sheet.cell(found_row, 5).value:
                return jsonify({'success': False, 'message': 'Already OUT ✅'})

            in_time = sheet.cell(found_row, 4).value

            in_dt = datetime.strptime(in_time, '%I:%M %p')
            out_dt = datetime.strptime(time_str, '%I:%M %p')

            if out_dt < in_dt:
                out_dt += timedelta(days=1)

            diff = out_dt - in_dt
            hrs = diff.seconds // 3600
            mins = (diff.seconds % 3600) // 60

            working_hours = f"{hrs} hrs {mins} mins"

            current_minutes = now.hour * 60 + now.minute
            office_out = 17 * 60 + 30

            if current_minutes < office_out:
                early = office_out - current_minutes
                out_status = f'{early} mins Early Exit 🚶'
            elif current_minutes <= office_out + 20:
                out_status = 'On Time Exit ✅'
            else:
                extra = current_minutes - office_out
                out_status = f'{extra} mins Extra Stay 🔥'

            sheet.update_cell(found_row, 5, time_str)
            sheet.update_cell(found_row, 7, out_status)
            sheet.update_cell(found_row, 8, working_hours)

            return jsonify({
                'success': True,
                'time': time_str,
                'status': out_status,
                'working_hours': working_hours
            })

        return jsonify({'success': False})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# =========================================
# RUN
# =========================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )