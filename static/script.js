console.log("✅ Script Loaded Successfully");

function safeGet(id) {
    return document.getElementById(id)?.value || "";
}

function showStatus(data, action) {

    const messageText = data.message || 
        (action === "in" ? "Punch IN ✅" : "Punch OUT ✅");

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

function getDeviceId() {
    let deviceId = localStorage.getItem("device_id");

    if (!deviceId) {
        deviceId = "DEV-" + Math.random().toString(36).substring(2) + Date.now();
        localStorage.setItem("device_id", deviceId);
    }

    return deviceId;
}

async function loadEmployee() {

    const empId = safeGet("emp_id");

    if (!empId) {
        alert("Employee ID required ❌");
        return;
    }

    const response = await fetch("/get_employee", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ emp_id: empId })
    });

    const data = await response.json();

    if (data.success) {
        document.getElementById("name").value = data.name || "";
        document.getElementById("phone").value = data.phone || "";
    } else {
        alert(data.message || "Not found ❌");
    }
}

function markAttendance(action) {

    const emp_id = safeGet("emp_id");
    const otp = safeGet("otp");

    if (!emp_id || !otp) {
        alert("Fill required fields ❌");
        return;
    }

    navigator.geolocation.getCurrentPosition(async function(pos) {

        const response = await fetch('/attendance', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                emp_id,
                otp,
                lat: pos.coords.latitude,
                lon: pos.coords.longitude,
                action,
                device_id: getDeviceId()
            })
        });

        const data = await response.json();

        if (data.success) {
            showStatus(data, action);
        } else {
            alert(data.message);
        }

    }, function() {
        alert("Allow location ❌");
    });
}