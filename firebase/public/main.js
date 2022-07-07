"use strict";

// Currently unused.
document.getElementById(`btn-getPermission`).addEventListener('click', function(){
  navigator.serviceWorker.controller.postMessage("stop");
});

// Check if the browser supports service workers, and if the current context is secure.
console.log("serviceWorker in main?:", 'serviceWorker' in navigator)
console.log("is main securecontext?:", self.isSecureContext)

// Request notification permissions.
self.Notification.requestPermission(function (status) {
  console.log('Notification permission status:', status);
});

// On page load, register our service worker and print the registration result 
// to the console.
if ('serviceWorker' in navigator) {
    window.addEventListener('load', async function () {
      navigator.serviceWorker

        // Register the service worker and update it.
        .register('/service-worker.js')
        .then((registration) => {
          console.log(`ServiceWorker registration successful with scope: ${registration.scope}`);
          return registration.update();
        })
        .then((registration) => {
          console.log(`ServiceWorker updated`);
          return registration;
        })

        // Subscribe to the push service.
        .then(registration => subscribeUserToPush(registration))

        // Post the subscription details to the save subscription Cloud Function.
        .then((pushSubscription) => {
          return fetch(top.subscriptionURL, 
                {
                  method :'POST',
                  mode   :'cors',
                  headers:{'Content-Type': 'application/json'},
                  body   :JSON.stringify(pushSubscription)
                });
        })

        // Print the response from the save subscrption Cloud Function.
        .then(saveResponse => saveResponse.text()).then(text=>console.log(text))
        .catch((err) => console.log('ServiceWorker registration failed: ', err));
    });
  }

// Function to convert a Base64 string to a uint8 array.
function urlB64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/\-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

// Function to subscribe to push notifications from a push service, and return
// the user's pushSubscription object.
function subscribeUserToPush(registration) {
  const subscribeOptions = 
  {
    userVisibleOnly: true,
    applicationServerKey: urlB64ToUint8Array(
        top.applicationServerKey,),
  };

  // Print the pushSubscription to the console, and return it from the 
  // subscribeUserToPush() function.
  return registration.pushManager.subscribe(subscribeOptions)
.then(function (pushSubscription) {
    console.log('Received PushSubscription',pushSubscription.endpoint.slice(-5));
    return pushSubscription;
  });
}