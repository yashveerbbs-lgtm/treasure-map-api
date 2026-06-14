self.addEventListener('push', function(event) {
    const data = event.data ? event.data.json() : {};
    const title = data.title || "Geocatcher Update";
    
    const options = {
        body: data.body || "There is new activity near you!",
        icon: "https://cdn-icons-png.flaticon.com/512/2857/2857355.png",
        badge: "https://cdn-icons-png.flaticon.com/512/2857/2857355.png",
        vibrate: [200, 100, 200]
    };
    
    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(clients.openWindow('/'));
});
