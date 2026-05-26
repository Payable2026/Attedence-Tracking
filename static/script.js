console.log("✅ Script Loaded");

/* =========================================
   SAFE GET
========================================= */
function safeGet(id) {
    return document.getElementById(id)?.value || "";
}

/* =========================================
   SHOW MESSAGE
========================================= */
function show(msg) {
    document.getElementById("result").innerHTML = msg;
}

/* =========================================
   DEVICE ID (IMPROVED)
========================================= */
function deviceId() {

    let id = localStorage.getItem("dev");

    if (!id) {
        id = "DEV-" + Math.random().toString(36).substring(2) + Date.now();
        localStorage.setItem("dev", id);
    }

    return id;
}

/* =========================================
   LOAD EMPLOYEE
========================================= */
async function loadEmployee() {

    const emp_id = safeGet("emp_id");

    if (!emp_id) {
        alert("Employee ID required ❌");
        return;
    }

    try {
        let res = await fetch("/get_employee", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ emp_id })
        });

        let data = await res.json();

        if (data.success) {
            document.getElementById("name").value = data.name;
            document.getElementById("phone").value = data.phone;
        } else {
            alert("Employee not found ❌");
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

        async (pos) => {

            try {

                let res = await fetch("/attendance", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        emp_id,
                        otp,
                        lat: pos.coords.latitude,
                        lon: pos.coords.longitude,
                        action,
                        device_id: deviceId()
                    })
                });

                let data = await res.json();

                if (data.success) {
                    show(`
                        ✅ ${data.name || ""} <br>
                        ${data.message} <br>
                        📅 ${data.date} <br>
                        ⏰ ${data.time} <br>
                        📌 ${data.status}
                        ${data.working_hours ? `<br><br>🕒 ${data.working_hours}` : ""}
                    `);
                } else {
                    alert(data.message);
                }

            } catch (err) {
                console.error(err);
                alert("Server error ❌");
            }

        },

        (error) => {
            alert("Location permission required ❌");
        }

    );
}