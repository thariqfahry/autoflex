"use strict";
console.log("is sw securecontext?:", self.isSecureContext);

self.addEventListener('install', function(event) {
    event.waitUntil(self.skipWaiting()); // Activate worker immediately
});

self.addEventListener('activate', function(event) {
    event.waitUntil(self.clients.claim()); // Become available to all pages
    //self.registration.showNotification("Service worker registered.");
});

self.addEventListener("push", function(data){
    console.log("Push recieved: ", data.data.text());
    let msg = data.data.json()

    if(msg.ok){
        let body = ""
        for (let [id, shift] of Object.entries(msg.shifts)){
            body += `£${shift.total_pay.toFixed(0)} ${shift.duration}h (${shift.total_commute_time.toFixed(1)}) ${shift.outbound_departure_time}>${shift.starttime}-${shift.endtime}>${shift.return_arrival_time} ${shift.date} ${shift.role}\n`
        }
        const promiseChain = self.registration.showNotification(
            msg.title,
            {
                "body"  :body +'\n' +msg.time,
                "icon"  :"/favicon.ico",
                "badge" :"/favicon.ico"
            })

    } else {
        const promiseChain = self.registration.showNotification(
            msg.title,
            {
                "body"  :msg.error +'\n' +msg.time,
                "icon"  :"/favicon.ico",
                "badge" :"/favicon.ico"
            })
    }

    //data.waitUntil(promiseChain);
});

self.addEventListener("message", function(event){
    if (event.data == "stop"){
        console.log("Interval cleared.")
        clearInterval(I);
    }
});


