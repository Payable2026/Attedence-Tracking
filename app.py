from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
from geopy.distance import geodesic
from zoneinfo import ZoneInfo
import json
import gspread
import os

# ✅ NEW: Load .env
from dotenv import load_dotenv
load_dotenv()

from google.oauth2.service_account import Credentials

app = Flask(__name__)

# ✅ Timezone
IST = ZoneInfo("Asia/Kolkata")

# ✅ Office Location
OFFICE_LAT = 13.0566
OFFICE_LON = 80.2541
ALLOWED_RADIUS = 25  # meters

# ✅ Google Scope
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


# ✅ ✅ CREDENTIAL LOADING (UPDATED FULL FIX)

creds = None

# 🔁 Try ENV first
creds_raw = os.environ.get("GOOGLE_CREDENTIALS")

if creds_raw:
    try:
        creds_dict = json.loads(creds_raw)

        # ✅ Fix newline issue
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=scope
        )

        print("✅ Using ENV credentials")

    except Exception as e:
        raise Exception(f"❌ ENV credentials error: {e}")

else:
    # ✅ Fallback (LOCAL only)
    print("⚠ Using local service_account.json (DEV MODE)")

    creds = Credentials.from_service_account_file(
        "service_account.json",
        scopes=scope
    )


# ✅ Connect Google Sheets
client = gspread.authorize(creds)

SHEET_ID = "1KteRJa0GenikpFQpFCBGvh6HS_jSDl-HHItrORwWRcE"

try:
    sheet = client.open_by_key(SHEET_ID).sheet1
except Exception as e:
    raise Exception(f"❌ Sheet error: {e}")


# ✅ Load employees
with open("employees.json", "r") as f:
    employees = json.load(f)


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

    return jsonify({'success': False})


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

        if emp_id not in employees:
            return jsonify({'success': False, 'message': 'Invalid ID ❌'})

        if otp != employees[emp_id]['otp']:
            return jsonify({'success': False, 'message': 'Wrong OTP ❌'})

        # ✅ Distance check
        distance = geodesic((OFFICE_LAT, OFFICE_LON), (lat, lon)).meters
        if distance > ALLOWED_RADIUS:
            return jsonify({'success': False, 'message': 'Outside Office ❌'})

        now = datetime.now(IST)
        date_str = now.strftime('%d-%m-%Y')
        time_str = now.strftime('%I:%M %p')

        records = sheet.get_all_records()
        found_row = None

        # ✅ Check existing record
        for i, rec in enumerate(records, start=2):
            if str(rec['Employee ID']) == emp_id and rec['Date'] == date_str:
                found_row = i
                break

        # ✅ Punch IN
        if action == 'in':
            if found_row:
                return jsonify({'success': False, 'message': 'Already IN ✅'})

            sheet.append_row([
                date_str,
                emp_id,
                employees[emp_id]['name'],
                time_str,
                '',
                'IN ✅',
                '',
                '',
                device_id
            ])

            return jsonify({
                'success': True,
                'name': employees[emp_id]['name'],
                'date': date_str,
                'time': time_str,
                'status': 'IN ✅',
                'message': 'Punch IN Success'
            })

        # ✅ Punch OUT
        elif action == 'out':
            if not found_row:
                return jsonify({'success': False, 'message': 'No IN ❌'})

            if sheet.cell(found_row, 5).value:
                return jsonify({'success': False, 'message': 'Already OUT ✅'})

            in_time = sheet.cell(found_row, 4).value

            in_dt = datetime.strptime(in_time, '%I:%M %p')
            out_dt = datetime.strptime(time_str, '%I:%M %p')

            # ✅ Midnight fix
            if out_dt < in_dt:
                out_dt += timedelta(days=1)

            diff = out_dt - in_dt

            hrs = diff.seconds // 3600
            mins = (diff.seconds % 3600) // 60

            work = f"{hrs} hrs {mins} mins"

            sheet.update_cell(found_row, 5, time_str)
            sheet.update_cell(found_row, 8, work)

            return jsonify({
                'success': True,
                'date': date_str,
                'time': time_str,
                'status': 'OUT ✅',
                'working_hours': work,
                'message': 'Punch OUT Success'
            })

        return jsonify({'success': False})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ✅ Run
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)