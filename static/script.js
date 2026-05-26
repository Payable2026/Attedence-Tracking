function safeGet(id){
    return document.getElementById(id).value;
}

function show(msg){
    document.getElementById("result").innerHTML = msg;
}

function deviceId(){
    let id = localStorage.getItem("dev");

    if(!id){
        id = Date.now();
        localStorage.setItem("dev", id);
    }
    return id;
}

async function loadEmployee(){
    let emp_id = safeGet("emp_id");

    let res = await fetch("/get_employee", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({emp_id})
    });

    let data = await res.json();

    if(data.success){
        document.getElementById("name").value = data.name;
        document.getElementById("phone").value = data.phone;
    } else {
        alert("Not found ❌");
    }
}

function markAttendance(action){

    let emp_id = safeGet("emp_id");
    let otp = safeGet("otp");

    navigator.geolocation.getCurrentPosition(async pos => {

        let res = await fetch("/attendance", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body: JSON.stringify({
                emp_id,
                otp,
                lat:pos.coords.latitude,
                lon:pos.coords.longitude,
                action,
                device_id:deviceId()
            })
        });

        let data = await res.json();

        if(data.success){
            show(`
            ✅ ${data.name || ""}<br>
            ${data.message}<br>
            📅 ${data.date}<br>
            ⏰ ${data.time}<br>
            ${data.status}<br>
            ${data.working_hours || ""}
            `);
        } else {
            alert(data.message);
        }

    });
}
