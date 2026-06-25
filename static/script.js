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
function showStatus(data, action) {

    const messageText = data.message
        ? data.message
        : (action === "in"
            ? "Punch IN Success ✅"
            : "Punch OUT Success ✅");

    document.getElementById("result").innerHTML = `
        <div style="text-align:center; padding:20px;">

            ✅ <b>${data.name || "-"}</b><br><br>

            📢 ${messageText}<br><br>

            📅 ${data.date || new Date().toLocaleDateString()}<br>
            ⏰ ${data.time || "-"}<br><br>

            📌 ${data.status || "-"}

            ${data.working_hours 
                ? `<br><br>🕒 Working Hours : ${data.working_hours}` 
                : ""
            }

        </div>
    `;
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
   ✅ LOAD EMPLOYEE (FIXED)
========================================= */
async function loadEmployee() {

    const empId = safeGet("emp_id").trim();  // ✅ IMPORTANT

    console.log("EMP ID:", empId);

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

        // ✅ Handle server error response
        if (!response.ok) {
            throw new Error("Server response not OK");
        }

        const data = await response.json();

        console.log("Response:", data);

        if (data.success) {
            document.getElementById("name").value = data.name || "";
            document.getElementById("phone").value = data.phone || "";
        } else {
            alert(data.message || "Employee not found ❌");
        }

    } catch (err) {
        console.error("LOAD ERROR:", err);
        alert("Server error ❌");
    }
}

/* =========================================
   ✅ MARK ATTENDANCE
========================================= */
function markAttendance(action) {

    const emp_id = safeGet("emp_id").trim();
    const otp = safeGet("otp").trim();

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

                // ✅ Check response
                if (!response.ok) {
                    throw new Error("Attendance API error");
                }

                const data = await response.json();

                console.log("Attendance Response:", data);

                if (data.success) {
                    showStatus(data, action);
                } else {
                    alert(data.message || "Error ❌");
                }

            } catch (err) {
                console.error("ATTENDANCE ERROR:", err);
                alert("Server error ❌");
            }

        },

        function () {
            alert("Location permission required ❌");
        }
    );
}