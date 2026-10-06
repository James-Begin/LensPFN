import { createDigestCheck } from "./digest.js";
const BASE = "http://127.0.0.1:8765";
const allowedPaths = new Set([
  "/api/digest",
  "/api/digest-preferences",
  "/api/digest-delivered",
  "/api/learning",
  "/api/status",
  "/api/shortlist",
  "/api/library",
  "/api/paper",
  "/api/paper-match",
  "/api/rate",
  "/api/interests",
  "/api/refresh",
  "/api/tabpfn-access",
  "/api/resolve-reference",
]);
const writes = new Set([
  "/api/digest-preferences",
  "/api/digest-delivered",
  "/api/rate",
  "/api/interests",
  "/api/refresh",
  "/api/tabpfn-access",
]);
const arxiv = (url) =>
  /^https:\/\/(www\.)?arxiv\.org\/(abs|html)\//.test(url || "");
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.setAccessLevel({ accessLevel: "TRUSTED_CONTEXTS" });
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  syncDigestAlarm().catch(() => {});
});
chrome.runtime.onStartup.addListener(() => {
  chrome.storage.local.setAccessLevel({ accessLevel: "TRUSTED_CONTEXTS" });
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  syncDigestAlarm().catch(() => {});
});
async function api(path, body) {
  const route = path.split("?")[0];
  if (!allowedPaths.has(route) || path.includes("#") || path.includes("://"))
    throw new Error("Unknown Lens request.");
  if (
    (body !== undefined) !==
    (writes.has(route) || route === "/api/resolve-reference")
  )
    throw new Error("Invalid request method.");
  const { token } = await chrome.storage.local.get("token");
  if (!token)
    throw new Error("Open Lens and connect your local companion first.");
  let response;
  try {
    response = await fetch(BASE + path, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: AbortSignal.timeout(180000),
    });
  } catch {
    const error = new Error(
      "Local companion is unavailable. Start it, then try again.",
    );
    error.offline = true;
    throw error;
  }
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.error || "Lens could not finish this request.");
  return data;
}
const checkDigest = createDigestCheck({
  request: api,
  deliver: async (papers) => {
    if ((await chrome.notifications.getPermissionLevel()) !== "granted")
      return false;
    const count = papers.length;
    await chrome.notifications.create("lens-quiet-digest", {
      type: "basic",
      iconUrl: "icons/icon-128.png",
      title: `${count} new ${count === 1 ? "paper" : "papers"} above 80% match`,
      message:
        count === 1
          ? papers[0].title.slice(0, 180)
          : `${papers[0].title.slice(0, 115)} and ${count - 1} more. Open your Lens digest.`,
    });
    return true;
  },
});
async function syncDigestAlarm() {
  let enabled = Boolean(
    (await chrome.storage.local.get("digestEnabled")).digestEnabled,
  );
  try {
    const status = await api("/api/status");
    enabled = Boolean(status.digest_enabled);
    await chrome.storage.local.set({ digestEnabled: enabled });
  } catch {}
  if (enabled)
    await chrome.alarms.create("lens-digest", { periodInMinutes: 30 });
  else await chrome.alarms.clear("lens-digest");
}
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "lens-digest")
    checkDigest()
      .then(() => notify())
      .catch(() => {});
});
chrome.notifications.onClicked.addListener(async (id) => {
  if (id !== "lens-quiet-digest") return;
  await chrome.storage.session.set({ lensView: "digest" });
  chrome.runtime.sendMessage({ type: "showDigest" }).catch(() => {});
  const [tab] = await chrome.tabs.query({
    active: true,
    lastFocusedWindow: true,
  });
  if (tab) await chrome.sidePanel.open({ tabId: tab.id });
});
async function notify() {
  chrome.runtime.sendMessage({ type: "changed" }).catch(() => {});
  const tabs = await chrome.tabs.query({});
  for (const tab of tabs)
    chrome.tabs.sendMessage(tab.id, { type: "changed" }).catch(() => {});
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== chrome.runtime.id) return false;
  const fromPage = Boolean(sender.tab);
  if (fromPage && !arxiv(sender.url)) return false;
  if (message.type === "open") {
    if (sender.tab)
      chrome.sidePanel
        .open({ tabId: sender.tab.id })
        .then(() => reply({ ok: true }))
        .catch(() => reply({ ok: false }));
    return true;
  }
  (async () => {
    if (message.type === "page" && fromPage) {
      const paper = message.paper;
      if (
        !paper ||
        typeof paper.id !== "string" ||
        typeof paper.title !== "string"
      )
        throw new Error("No paper found.");
      await chrome.storage.session.set({
        ["paper-" + sender.tab.id]: {
          id: paper.id.slice(0, 100),
          title: paper.title.slice(0, 1000),
        },
      });
      chrome.runtime.sendMessage({ type: "changed" }).catch(() => {});
      return null;
    }
    if (message.type === "current" && !fromPage) {
      const [tab] = await chrome.tabs.query({
        active: true,
        lastFocusedWindow: true,
      });
      const key = "paper-" + tab?.id;
      return (await chrome.storage.session.get(key))[key] || null;
    }
    if (
      message.type === "citation" &&
      fromPage &&
      /\/html\//.test(sender.url)
    ) {
      const citation = message.citation;
      if (
        !citation ||
        typeof citation.reference !== "string" ||
        typeof citation.label !== "string" ||
        (citation.id !== null && typeof citation.id !== "string")
      )
        throw new Error("Invalid citation.");
      const id = citation.id?.replace(/v\d+$/, "") || null;
      if (
        id &&
        !/^(?:\d{4}\.\d{4,5}|[a-zA-Z-]+(?:\.[A-Z]{2})?\/\d{7})$/.test(id)
      )
        throw new Error("Invalid arXiv paper ID.");
      await chrome.storage.session.set({
        ["citation-" + sender.tab.id]: {
          id,
          label: citation.label.slice(0, 40),
          reference: citation.reference.slice(0, 3000),
          details: Object.fromEntries(
            ["title", "authors", "publication", "year", "url", "doi"].map(
              (key) => [
                key,
                typeof citation.details?.[key] === "string"
                  ? citation.details[key].slice(0, key === "year" ? 4 : 1500)
                  : "",
              ],
            ),
          ),
        },
      });
      chrome.runtime.sendMessage({ type: "citationChanged" }).catch(() => {});
      return null;
    }
    if (message.type === "citationCurrent" && !fromPage) {
      const [tab] = await chrome.tabs.query({
        active: true,
        lastFocusedWindow: true,
      });
      const key = "citation-" + tab?.id;
      return (await chrome.storage.session.get(key))[key] || null;
    }
    if (message.type === "checkDigest" && !fromPage) return checkDigest();
    if (message.type === "pair" && !fromPage) {
      if (
        typeof message.token !== "string" ||
        !/^[A-Za-z0-9_-]{32,100}$/.test(message.token)
      )
        throw new Error("Paste the complete pairing key.");
      // Check the supplied key before replacing a working connection.
      const response = await fetch(BASE + "/api/status", {
        headers: { Authorization: "Bearer " + message.token },
      });
      if (!response.ok) throw new Error("That pairing key was not accepted.");
      await chrome.storage.local.set({ token: message.token });
      await syncDigestAlarm();
      return response.json();
    }
    if (message.type === "api") {
      if (
        fromPage &&
        ![
          "/api/rate",
          "/api/status",
          "/api/paper",
          "/api/paper-match",
          "/api/resolve-reference",
        ].includes(message.path?.split("?")[0])
      )
        throw new Error("This request is only available in the Lens panel.");
      const result = await api(message.path, message.body);
      if (message.path.split("?")[0] === "/api/digest-preferences")
        await syncDigestAlarm();
      if (
        writes.has(message.path.split("?")[0]) &&
        message.path.split("?")[0] !== "/api/digest-delivered"
      )
        await notify();
      return result;
    }
    if (
      message.type === "changed" ||
      message.type === "citationChanged" ||
      message.type === "showDigest"
    )
      return null;
    throw new Error("Unknown Lens action.");
  })()
    .then((data) => reply({ ok: true, data }))
    .catch((error) =>
      reply({
        ok: false,
        error: error.message,
        offline: Boolean(error.offline),
      }),
    );
  return true;
});
chrome.tabs.onActivated.addListener(() =>
  chrome.runtime.sendMessage({ type: "changed" }).catch(() => {}),
);
chrome.tabs.onUpdated.addListener((id, change) => {
  if (change.url) {
    chrome.storage.session
      .remove(["paper-" + id, "citation-" + id])
      .then(() =>
        chrome.runtime.sendMessage({ type: "changed" }).catch(() => {}),
      );
  }
});
chrome.tabs.onRemoved.addListener((id) =>
  chrome.storage.session.remove(["paper-" + id, "citation-" + id]),
);
