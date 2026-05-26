console.log("✅ Script Loaded");

/* SAFE GET */
function safeGet(id) {
    return document.getElementById(id)?.value || "";
}

/* SHOW STATUS */
function showStatus(data, action) {

    const msg = data.message
        ? data.message
        : (action === "in"
            ? "Punch IN Success ✅"
            : "Punch OUT Success ✅");

    document.getElementById("result").innerHTML = `
        ✅ <b>${data.name || "-"}</b><br><br>
        📢 ${msg}<br><br>
        📅 ${data.date || "-"}<br>
        ⏰ ${data.time || "-"}<br><br>
        📌 ${data.status || "-"}
        ${data.working_hours 
            ? `<br><br>🕒 ${data.working_hours}` 
            : ""
        }
    `;
}

/* DEVICE */
function getDeviceId() {

    let id = localStorage.getItem("device_id");

    if (!id) {
        id = "DEV-" + Math.random().toString(36).substring(2) + Date.now();
        localStorage.setItem("device_id", id);
    }

    return id;
}

/* LOAD EMPLOYEE */
async function loadEmployee() {

    const emp_id = safeGet("emp_id");

    if (!emp_id) return alert("Enter ID ❌");

    const res = await fetch("/get_employee", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ emp_id })
    });

    const data = await res.json();

    if (data.success) {
        document.getElementById("name").value = data.name;
        document.getElementById("phone").value = data.phone;
    } else {
        alert(data.message);
    }
}

/* MARK ATTENDANCE */
function markAttendance(action) {

    const emp_id = safeGet("emp_id");
    const otp = safeGet("otp");

    if (!emp_id || !otp) {
        alert("Fill all fields ❌");
        return;
    }

    navigator.geolocation.getCurrentPosition(async pos => {

        const res = await fetch("/attendance", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                emp_id,
                otp,
                lat: pos.coords.latitude,
                lon: pos.coords.longitude,
                action,
                device_id: getDeviceId()
            })
        });

        const data = await res.json();

        if (data.success) {
            showStatus(data, action);
        } else {
            alert(data.message);
        }

    }, () => alert("Location needed ❌"));
}
