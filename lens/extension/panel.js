import { icon } from "./icons.js";
import { replacePaperList } from "./list-motion.js";
import { createOnboarding } from "./onboarding.js";
const $ = (s) => document.querySelector(s);
const browserExtension = Boolean(globalThis.chrome?.runtime?.id);
const LOCAL = browserExtension ? "http://127.0.0.1:8765" : location.origin;
const previewCitationId = !browserExtension
  ? new URLSearchParams(location.search).get("citation")
  : null;
const previewCitation =
  /^(?:\d{4}\.\d{4,5}|[a-zA-Z-]+(?:\.[A-Z]{2})?\/\d{7})$/.test(
    previewCitationId || "",
  )
    ? {
        id: previewCitationId,
        label: "Preview citation",
        reference: `Example cited paper · arXiv:${previewCitationId}`,
      }
    : null;
let previewToken = "";
let tab = "shortlist";
let category = "";
let status = null;
let current = null;
let citation = null;
let citationTicket = 0;
const citedPaperCache = new Map();
let busy = false;
let noticeTimer;
let renderTicket = 0;
let previousView = null;
let setup = null;
function unavailable(message) {
  const error = new Error(message);
  error.offline = true;
  return error;
}
function icons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon);
  });
}
function show(id, yes = true) {
  $(id).hidden = !yes;
}
function message(text) {
  const el = $("#message");
  el.textContent = text;
  show("#message");
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => show("#message", false), 3300);
}
function error(text) {
  $("#error-text").textContent = text;
  show("#error");
}
function clearError() {
  show("#error", false);
}
function validPaperUrl(paper) {
  return `https://arxiv.org/abs/${paper.id.split("/").map(encodeURIComponent).join("/")}`;
}
async function request(path, body) {
  if (browserExtension) {
    let reply;
    try {
      reply = await chrome.runtime.sendMessage({
        type: "api",
        path,
        ...(body === undefined ? {} : { body }),
      });
    } catch {
      throw unavailable("Lens extension could not reach its local companion.");
    }
    if (!reply?.ok) {
      const error = new Error(reply?.error || "Lens is unavailable.");
      error.offline = Boolean(reply?.offline);
      throw error;
    }
    return reply.data;
  }
  let response;
  try {
    response = await fetch(LOCAL + path, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        Authorization: `Bearer ${previewToken}`,
        "Content-Type": "application/json",
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw unavailable(
      "Local companion is unavailable. Start it, then try again.",
    );
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Lens is unavailable.");
  return data;
}
async function getCurrent() {
  if (!browserExtension) return null;
  const reply = await chrome.runtime.sendMessage({ type: "current" });
  return reply?.ok ? reply.data : null;
}
function ratingsFor(id) {
  const state = status?.ratings?.[id] || 0;
  const group = document.createElement("div");
  group.className = "rating-actions";
  for (const [value, label, iconName] of [
    [1, "Interested", "check"],
    [-1, "Not for me", "minus"],
  ]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "rate-button" + (state === value ? " selected" : "");
    button.setAttribute("aria-pressed", String(state === value));
    button.setAttribute("aria-label", `${label}: ${id}`);
    button.innerHTML = icon(iconName) + `<span>${label}</span>`;
    button.addEventListener("click", async () => {
      if (busy) return;
      busy = true;
      group.classList.add("busy");
      clearError();
      const hadFocus = document.activeElement === button;
      const row = button.closest(".paper");
      const rowIndex = row
        ? Array.from(row.parentElement.children).indexOf(row)
        : -1;
      try {
        status = await request("/api/rate", {
          id,
          rating: state === value ? 0 : value,
        });
        message(state === value ? "Rating removed." : "Saved to your library.");
        await render({
          quiet: true,
          restoreFocus: hadFocus
            ? {
                label: button.getAttribute("aria-label"),
                rowIndex,
                paperId: id,
              }
            : null,
        });
      } catch (e) {
        error(e.message);
      } finally {
        busy = false;
        group.classList.remove("busy");
      }
    });
    group.append(button);
  }
  return group;
}
function renderCurrent() {
  show("#current-paper", Boolean(current));
  if (!current) return;
  $("#current-title").textContent = current.title;
  $("#current-actions").replaceChildren(ratingsFor(current.id));
}
async function renderCitation() {
  const ticket = ++citationTicket;
  let reply = { ok: true, data: previewCitation };
  if (browserExtension) {
    try {
      reply = await chrome.runtime.sendMessage({ type: "citationCurrent" });
    } catch {
      reply = null;
    }
  }
  if (ticket !== citationTicket) return;
  citation = reply?.ok ? reply.data : null;
  show("#cited-paper", Boolean(citation));
  if (!citation) return;
  $("#cited-marker").textContent = citation.label || "Citation";
  $("#cited-title").textContent =
    citation.details?.title ||
    (citation.id ? `arXiv:${citation.id}` : "Cited reference");
  $("#cited-reference").textContent = citation.reference;
  show("#cited-match", false);
  show("#cited-authors", false);
  show("#cited-abstract", false);
  show("#cited-save", false);
  show("#cited-link", Boolean(citation.id));
  show("#cited-help", true);
  if (!citation.id) {
    $("#cited-authors").textContent =
      citation.details?.authors ||
      citation.details?.publication ||
      citation.details?.year ||
      "";
    show("#cited-authors", Boolean($("#cited-authors").textContent));
    try {
      const url = new URL(citation.details?.url);
      if (["https:", "http:"].includes(url.protocol)) {
        $("#cited-link").href = url.href;
        $("#cited-link").textContent = "Open reference";
        show("#cited-link");
      }
    } catch {}
    $("#cited-help").textContent =
      "From this paper’s bibliography. Match and library ratings need an arXiv paper ID.";
    return;
  }
  $("#cited-link").textContent = "Open on arXiv";
  $("#cited-link").href = validPaperUrl(citation);
  $("#cited-help").textContent = "Looking up the cited paper…";
  try {
    let paper = citedPaperCache.get(citation.id);
    if (!paper) {
      paper = await request(`/api/paper?id=${encodeURIComponent(citation.id)}`);
      citedPaperCache.set(citation.id, paper);
    }
    if (ticket !== citationTicket) return;
    $("#cited-title").textContent = paper.title;
    $("#cited-authors").textContent =
      (paper.authors || []).slice(0, 3).join(", ") +
      (paper.authors?.length > 3 ? " et al." : "");
    show("#cited-authors", Boolean(paper.authors?.length));
    $("#cited-abstract-text").textContent = paper.abstract || "";
    show("#cited-abstract", Boolean(paper.abstract));
    const saved = status?.ratings?.[citation.id] === 1;
    $("#cited-save").textContent = saved
      ? "Remove from library"
      : "Save as Interested";
    $("#cited-save").setAttribute("aria-pressed", String(saved));
    show("#cited-save");
    show("#cited-help", false);
    const estimate = await request(
      `/api/paper-match?id=${encodeURIComponent(citation.id)}`,
    ).catch(() => null);
    if (ticket !== citationTicket) return;
    show("#cited-match", typeof estimate?.match === "number");
    $("#cited-match").textContent =
      typeof estimate?.match === "number"
        ? `${estimate.match >= 0.995 ? ">99" : Math.round(estimate.match * 100)}% match`
        : "";
  } catch (e) {
    if (ticket !== citationTicket) return;
    $("#cited-help").textContent =
      "Lens could not verify this cited paper. You can still open it on arXiv.";
  }
}
function renderStatus() {
  $("#connection-dot").classList.add("online");
  $("#connection-label").textContent = "Local companion connected";
  $("#library-count").textContent = String(status.likes + status.dislikes);
  $("#interests").value = status.interests || "";
  const existing = $("#category").value;
  const cats = status.categories || [];
  $("#category").replaceChildren(
    new Option("All subjects", ""),
    ...cats.map((c) => new Option(c, c)),
  );
  category = cats.includes(category) ? category : "";
  $("#category").value =
    category || (existing && cats.includes(existing))
      ? category || existing
      : "";
  category = $("#category").value;
  const count = status.likes + status.dislikes;
  const target = status.match_after;
  const progress = Math.max(0, target - status.need_ratings);
  const complete = status.need_ratings === 0;
  show("#learning", !complete && ["shortlist", "learn"].includes(tab));
  $("#learning-count").textContent =
    `${count} ${count === 1 ? "rating" : "ratings"}`;
  const missing = [];
  if (status.need_likes) missing.push(`${status.need_likes} Interested`);
  if (status.need_dislikes) missing.push(`${status.need_dislikes} Not for me`);
  $("#learning-description").textContent =
    `${status.need_ratings} more ${status.need_ratings === 1 ? "rating" : "ratings"}${missing.length ? `, including ${missing.join(" and ")}` : ""}, before Lens can show match estimates.`;
  $("#learning-fill").style.transform =
    `scaleX(${Math.min(1, progress / target)})`;
  $(".learning-track").setAttribute("aria-valuemax", String(target));
  $(".learning-track").setAttribute(
    "aria-valuenow",
    String(Math.min(progress, target)),
  );
  if (tab === "shortlist") {
    $("#feed-title").textContent =
      count || status.interests
        ? "Papers for your next read."
        : "A place to start.";
    $("#feed-description").textContent =
      count || status.interests
        ? "Selected from the latest arXiv batch using your interests and ratings."
        : "Recent arXiv papers, ready for your first impressions.";
  } else if (tab === "digest") {
    $("#feed-title").textContent = "A quieter way to discover.";
    $("#feed-description").textContent =
      "Only papers with a match estimate above 80%. No new matches means no alert.";
  } else if (tab === "learn") {
    $("#feed-title").textContent = "Sharpen your reading profile.";
    $("#feed-description").textContent =
      "A few useful judgments, one paper at a time. Read the abstract, then give your honest first impression.";
  } else {
    $("#feed-title").textContent = "Your paper library.";
    $("#feed-description").textContent =
      "Papers you marked while browsing arXiv.";
  }
  $("#feed-meta").textContent = status.pool_count
    ? `${status.pool_count.toLocaleString()} papers in latest local batch · ${status.pool_name.replace("pool-", "")}`
    : "Fetch a batch to start your shortlist";
  if (status.refresh?.state === "running") {
    $("#refresh").disabled = true;
    $("#refresh").title = `Fetching ${status.refresh.count || 0} papers…`;
  } else {
    $("#refresh").disabled = false;
    $("#refresh").title = "Fetch the last 3 days from arXiv";
  }
}
function reliability(next = status?.reliability) {
  if (!next) return;
  $("#reliability-summary").textContent = next.count
    ? `80%+ check · you liked ${next.liked} of ${next.count}`
    : "Your 80%+ reality check · awaiting feedback";
  $("#reliability-detail").textContent = next.count
    ? `Of papers Lens estimated at 80% or higher before your rating, you liked ${next.liked} of ${next.count} (${Math.round((100 * next.liked) / next.count)}%). Their average forecast was ${Math.round(100 * next.mean_prediction)}%.${next.count < 10 ? " This is a small sample so far." : ""}`
    : "No prospective high-match ratings yet. Rate papers after Lens scores them to start this check; your past library is never counted retroactively.";
}
function paperRow(p) {
  const row = document.createElement("article");
  row.className = "paper";
  row.dataset.paperId = p.id;
  const meta = document.createElement("div");
  meta.className = "paper-meta";
  const primary = document.createElement("span");
  primary.textContent = p.primary || "arXiv";
  meta.append(primary);
  if (p.created) {
    const age = document.createElement("span");
    age.textContent = "· " + p.created;
    meta.append(age);
  }
  if (typeof p.match === "number") {
    const score = document.createElement("span");
    score.className = "match";
    score.textContent = `${p.match >= 0.995 ? ">99" : Math.round(p.match * 100)}% match`;
    meta.append(score);
  }
  const h = document.createElement("h2");
  const a = document.createElement("a");
  a.textContent = p.title;
  a.href = validPaperUrl(p);
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  h.append(a);
  const authors = document.createElement("p");
  authors.className = "authors";
  authors.textContent =
    (p.authors || []).slice(0, 3).join(", ") +
    (p.authors?.length > 3 ? " et al." : "");
  row.append(meta, h, authors);
  if (p.reason) {
    const why = document.createElement("p");
    why.className = "reason";
    why.textContent = p.reason;
    row.append(why);
  }
  if (p.abstract) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Read abstract";
    const text = document.createElement("p");
    text.textContent = p.abstract;
    details.append(summary, text);
    row.append(details);
  }
  row.append(ratingsFor(p.id));
  return row;
}
async function render(options = {}) {
  if (setup?.active) {
    await setup.refresh();
    return;
  }
  const ticket = ++renderTicket;
  clearError();
  const changingView = previousView !== tab;
  if (changingView) {
    $("#paper-list").replaceChildren();
    show("#empty", false);
  }
  const updates = {
    shortlist: "Updating your shortlist…",
    digest: "Checking high matches…",
    learn: "Choosing papers to sharpen your profile…",
  };
  $("#list-update").textContent =
    options.quiet && !changingView ? updates[tab] || "" : "";
  $("#paper-list").setAttribute("aria-busy", "true");
  if (!options.quiet || changingView) show("#loading");
  try {
    const nextStatus = await request("/api/status");
    if (ticket !== renderTicket) return;
    status = nextStatus;
    current = await getCurrent();
    if (ticket !== renderTicket) return;
    show("#connect", false);
    show("#workspace");
    renderStatus();
    renderCurrent();
    show("#feed-tools", tab !== "library");
    show("#digest-controls", tab === "digest");
    $("#digest-enabled").checked = Boolean(status.digest_enabled);
    reliability();
    for (const view of ["shortlist", "digest", "learn", "library"]) {
      $(`#${view}-tab`).classList.toggle("active", tab === view);
      $(`#${view}-tab`).setAttribute(
        "aria-current",
        tab === view ? "page" : "false",
      );
    }
    const routes = {
      shortlist: "/api/shortlist",
      digest: "/api/digest",
      learn: "/api/learning",
      library: "/api/library",
    };
    const data = await request(
      routes[tab] +
        (tab === "library" ? "" : `?category=${encodeURIComponent(category)}`),
    );
    if (ticket !== renderTicket) return;
    const papers = data.papers || [];
    const expanded = new Set(
      Array.from($("#paper-list").querySelectorAll(".paper"))
        .filter((row) => row.querySelector("details[open]"))
        .map((row) => row.dataset.paperId),
    );
    const rows = papers.map(paperRow);
    for (const row of rows)
      if (expanded.has(row.dataset.paperId))
        row.querySelector("details")?.setAttribute("open", "");
    replacePaperList($("#paper-list"), rows, {
      animate: tab !== "library" && previousView === tab,
    });
    previousView = tab;
    if (tab === "digest") {
      reliability(data.reliability);
      $("#feed-description").textContent = data.scored
        ? `${papers.length} above 80% among ${data.scored} scored candidates. More candidates may still be unscored.`
        : "High-match estimates need a ready profile and configured TabPFN access.";
    }
    if (tab === "learn")
      $("#feed-description").textContent =
        data.strategy === "uncertainty"
          ? "Rate these papers to sharpen your profile. Lens chose uncertain predictions with variety, rather than more of the same."
          : "Start with a few different papers. After six ratings, including two of each kind, TabPFN can guide this queue by uncertainty.";
    if (options.restoreFocus) {
      const rows = Array.from($("#paper-list").children);
      const source = options.restoreFocus;
      const originalRow = rows.find(
        (row) => row.dataset.paperId === source.paperId,
      );
      const root = source.rowIndex >= 0 ? originalRow : $("#current-actions");
      const target = Array.from(
        root?.querySelectorAll(".rate-button") || [],
      ).find((button) => button.getAttribute("aria-label") === source.label);
      (
        target ||
        rows[
          Math.min(Math.max(source.rowIndex, 0), rows.length - 1)
        ]?.querySelector("h2 a") ||
        $("#shortlist-tab")
      ).focus();
    }
    show("#empty", papers.length === 0);
    if (!papers.length) {
      $("#empty-title").textContent =
        tab === "digest"
          ? "Nothing above 80% yet."
          : tab === "library"
            ? "Your library is still open."
            : "No papers in this view.";
      $("#empty-description").textContent =
        tab === "digest"
          ? "You’ll only hear from Lens when a paper clears your threshold. Keep rating, or fetch a new batch."
          : tab === "library"
            ? "Mark a paper as Interested or Not for me on arXiv, or here in your shortlist."
            : "Choose another subject or fetch a new batch from arXiv.";
    }
    show("#model-warning", Boolean(data.warning));
    $("#model-warning").textContent = data.warning || "";
    if (tab === "shortlist" && data.engine === "recent" && papers.length)
      $("#feed-description").textContent =
        "Recently announced papers. Rate or describe your interests to personalize this list.";
    renderCitation();
  } catch (e) {
    if (ticket !== renderTicket) return;
    if (e.offline) {
      $("#connection-dot").classList.remove("online");
      $("#connection-label").textContent = "Local companion unavailable";
    }
    if (!status) {
      show("#workspace", false);
      show("#connect");
    }
    error(e.message);
  } finally {
    if (ticket === renderTicket) {
      show("#loading", false);
      $("#list-update").textContent = "";
      $("#paper-list").setAttribute("aria-busy", "false");
    }
  }
}
async function init() {
  icons();
  setup = createOnboarding({
    request,
    onStatus: (next) => {
      status = next;
    },
    pair: async (token) => {
      if (!browserExtension) return request("/api/status");
      const reply = await chrome.runtime.sendMessage({ type: "pair", token });
      if (!reply?.ok) throw new Error(reply?.error || "Could not connect.");
      return reply.data;
    },
    remember: async () => {
      if (browserExtension)
        await chrome.storage.local.set({ onboardingComplete: true });
      else localStorage.setItem("lens-onboarding-complete", "true");
    },
    onDone: () => render(),
  });
  if (browserExtension) {
    const savedView = (await chrome.storage.session.get("lensView")).lensView;
    if (savedView === "digest") {
      tab = "digest";
      await chrome.storage.session.remove("lensView");
    }
    chrome.runtime.onMessage.addListener((m) => {
      if (m.type === "showDigest" && !setup.active) {
        tab = "digest";
        chrome.storage.session.remove("lensView");
        render();
      }
      if (m.type === "changed" && !busy) render({ quiet: true });
      if (m.type === "citationChanged" && !setup.active) renderCitation();
    });
  } else {
    show("#preview-note");
    show("#pairing-controls");
    try {
      previewToken = (await (await fetch("/api/session")).json()).token || "";
    } catch {}
  }
  $("#settings-button").addEventListener("click", () =>
    show("#settings", $("#settings").hidden),
  );
  $("#restart-setup").addEventListener("click", () => {
    clearError();
    setup.start(status);
  });
  $("#close-settings").addEventListener("click", () =>
    show("#settings", false),
  );
  for (const view of ["shortlist", "digest", "learn", "library"])
    $(`#${view}-tab`).addEventListener("click", () => {
      tab = view;
      render();
    });
  $("#digest-enabled").addEventListener("change", async () => {
    const control = $("#digest-enabled");
    control.disabled = true;
    try {
      status = await request("/api/digest-preferences", {
        enabled: control.checked,
      });
      message(
        control.checked ? "Quiet digest enabled." : "Digest alerts paused.",
      );
    } catch (e) {
      control.checked = Boolean(status?.digest_enabled);
      error(e.message);
    } finally {
      control.disabled = false;
    }
  });
  $("#digest-check").addEventListener("click", async () => {
    const button = $("#digest-check");
    button.disabled = true;
    button.textContent = "Checking matches…";
    $("#digest-feedback").textContent = "";
    try {
      if (browserExtension) {
        const reply = await chrome.runtime.sendMessage({ type: "checkDigest" });
        if (!reply?.ok)
          throw new Error(reply?.error || "Could not check the digest.");
        $("#digest-feedback").textContent = !reply.data.enabled
          ? `Alerts are paused. ${reply.data.papers.length} high-match papers in your digest.`
          : reply.data.notification_warning ||
            (reply.data.notified
              ? `${reply.data.notified} new high-match papers notified.`
              : "No new alerts. Your digest is up to date.");
      } else
        $("#digest-feedback").textContent =
          "Digest refreshed. Desktop alerts run through the installed Chrome extension.";
      await render({ quiet: true });
    } catch (e) {
      error(e.message);
    } finally {
      button.disabled = false;
      button.textContent = "Check for new matches";
    }
  });
  $("#category").addEventListener("change", (e) => {
    category = e.target.value;
    render();
  });
  $("#refresh").addEventListener("click", async () => {
    try {
      await request("/api/refresh", { archive: "cs", days: 3 });
      message("Fetching the latest computer science papers.");
      await render({ quiet: true });
    } catch (e) {
      error(e.message);
    }
  });
  $("#cited-save").addEventListener("click", async () => {
    if (busy || !citation?.id) return;
    busy = true;
    clearError();
    const id = citation.id;
    try {
      const saved = status?.ratings?.[id] === 1;
      status = await request("/api/rate", { id, rating: saved ? 0 : 1 });
      message(
        saved
          ? "Removed from your library."
          : "Cited paper saved to your library.",
      );
      await render({ quiet: true });
      $("#cited-save").focus();
    } catch (e) {
      error(e.message);
    } finally {
      busy = false;
    }
  });
  $("#interests-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await request("/api/interests", { interests: $("#interests").value });
      show("#settings", false);
      message("Your interests are saved.");
      await render();
    } catch (err) {
      error(err.message);
    }
  });
  $("#connect-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!browserExtension) return;
    try {
      const reply = await chrome.runtime.sendMessage({
        type: "pair",
        token: $("#pair-key").value.trim(),
      });
      if (!reply?.ok) throw new Error(reply?.error || "Could not connect.");
      $("#pair-key").value = "";
      await render();
    } catch (err) {
      error(err.message);
    }
  });
  $("#copy-key").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(previewToken);
      message("Pairing key copied.");
    } catch {
      error(
        "Clipboard access failed. Select and copy the key from the local token file instead.",
      );
    }
  });
  $("#retry").addEventListener("click", () => render());
  let completed = false;
  try {
    completed = browserExtension
      ? Boolean(
          (await chrome.storage.local.get("onboardingComplete"))
            .onboardingComplete,
        )
      : true;
  } catch {}
  const forceSetup = new URLSearchParams(location.search).has("setup");
  if (!completed || forceSetup) {
    setup.start(null);
    await setup.refresh();
  } else await render();
  setInterval(() => {
    if (status?.refresh?.state === "running") render({ quiet: true });
  }, 7000);
}
init();
