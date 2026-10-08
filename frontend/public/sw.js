/* Ingress Job Web Push service worker (engagement Phase 5). */

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    try {
      data = { body: event.data ? event.data.text() : "" };
    } catch {
      data = {};
    }
  }
  const title = (data && data.title) || "Ingress Job";
  const options = {
    body: (data && data.body) || "",
    data: { url: (data && data.url) || "/" },
    tag: (data && data.tag) || "ingress-job",
    renotify: true,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target =
    (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if (client.url && client.url.startsWith(self.location.origin) && "focus" in client) {
          return client.focus().then(() => {
            if ("navigate" in client) {
              return client.navigate(target);
            }
            return undefined;
          });
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(target);
      }
      return undefined;
    }),
  );
});
