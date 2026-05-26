console.log("✅ Script Loaded Successfully");

/* =========================================
   SAFE GET
========================================= */
function safeGet(id) {
    return document.getElementById(id)?.value || "";
}

/* =========================================
   SHOW STATUS
========================================= */
function showStatus(message) {
    document.getElementById("result").innerHTML = message;
}

/* =========================================
   DEVICE ID
========================================= */
function getDeviceId() {

    let deviceId = localStorage.getItem("device_id");

    if (!deviceId) {
        deviceId =
            "DEV-" +
            Math.random().toString(36).substring(2) +
            Date.now();

        localStorage.setItem("device_id", deviceId);
    }

    return deviceId;
}

/* =========================================
   LOAD EMPLOYEE
========================================= */
async function loadEmployee() {

    const empId = safeGet("emp_id");

    if (!empId) {
        alert("Employee ID required ❌");
        return;
    }

    try {
        const response = await fetch("/get_employee", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ emp_id: empId })
        });

        const data = await response.json();

        if (data.success) {
            document.getElementById("name").value = data.name || "";
            document.getElementById("phone").value = data.phone || "";
        } else {
            alert(data.message || "Employee not found ❌");
        }

    } catch (err) {
        console.error(err);
        alert("Server error ❌");
    }
}

/* =========================================
   MARK ATTENDANCE
========================================= */
function markAttendance(action) {

    const emp_id = safeGet("emp_id");
    const otp = safeGet("otp");

    if (!emp_id) {
        alert("Employee ID required ❌");
        return;
    }

    if (!otp) {
        alert("OTP required ❌");
        return;
    }

    if (!navigator.geolocation) {
        alert("Geolocation not supported ❌");
        return;
    }

    navigator.geolocation.getCurrentPosition(

        async function (position) {

            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            const device_id = getDeviceId();

            try {
                const response = await fetch('/attendance', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        emp_id,
                        otp,
                        lat,
                        lon,
                        action,
                        device_id
                    })
                });

                const data = await response.json();

                if (data.success) {

                    showStatus(`
                        ✅ ${data.name || "-"} <br><br>
                        📢 ${data.message || "-"} <br><br>
                        📅 ${data.date || new Date().toLocaleDateString()} <br>
                        ⏰ ${data.time || "-"} <br>
                        📌 ${data.status || "-"}
                        ${data.working_hours 
                            ? `<br><br>🕒 Working Hours: ${data.working_hours}` 
                            : ""
                        }
                    `);

                } else {
                    alert(data.message || "Error ❌");
                }

            } catch (err) {
                console.error(err);
                alert("Server error ❌");
            }

        },

        function () {
            alert("Location permission required ❌");
        }

    );
}