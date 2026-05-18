self.addEventListener("push", event => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (error) {
    data = { title: "GigaParts filament in stock", body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "GigaParts filament in stock";
  const options = {
    body: data.body || "",
    data: { url: data.url || "./" },
    icon: data.icon || undefined,
    badge: data.badge || undefined,
    tag: data.tag || undefined,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", event => {
  event.notification.close();
  const targetUrl = event.notification.data && event.notification.data.url ? event.notification.data.url : "./";
  event.waitUntil(clients.openWindow(targetUrl));
});
