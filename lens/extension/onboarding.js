export function setupSummary(status) {
  const count = (status?.likes || 0) + (status?.dislikes || 0);
  if (status?.need_ratings === 0 && status?.tabpfn_configured)
    return `Your ${count} saved ratings are ready for personalized match scores.`;
  if (status?.need_ratings === 0)
    return `Your ${count} saved ratings are ready. Add TabPFN access for match scores, or continue with similarity ranking.`;
  const target = status?.match_after || 30;
  return `${count} of ${target} ratings saved. Match scores unlock after ${target} ratings, including at least 3 Interested and 3 Not for me.`;
}

export function createOnboarding({
  request,
  pair,
  remember,
  onDone,
  onStatus,
}) {
  const $ = (selector) => document.querySelector(selector);
  let state = null,
    step = 0,
    active = false,
    working = false,
    transition = null;
  const frames = [...document.querySelectorAll("[data-setup-step]")];
  function feedback(text = "") {
    $("#setup-error").textContent = text;
    $("#setup-error").hidden = !text;
  }
  function updateStatus(next) {
    state = next;
    onStatus(next);
    $("#setup-connected").hidden = !state;
    $("#setup-pair-fields").hidden = Boolean(state);
    $("#setup-connect-submit").textContent = state
      ? "Continue"
      : "Connect Lens";
    $("#setup-access-ready").hidden = !state?.tabpfn_configured;
    $("#setup-access-fields").hidden = Boolean(state?.tabpfn_configured);
    $("#setup-access-submit").textContent = state?.tabpfn_configured
      ? "Continue"
      : "Save access token";
    $("#setup-ready-summary").textContent = setupSummary(state);
    $("#setup-ready-model").textContent = state?.tabpfn_configured
      ? "TabPFN access is configured on this computer."
      : "Similarity ranking is ready. You can add TabPFN access later in setup.";
  }
  function move(next, { focus = true, entrance = false } = {}) {
    transition?.cancel();
    step = next;
    feedback();
    for (const frame of frames)
      frame.hidden = Number(frame.dataset.setupStep) !== step;
    for (const marker of document.querySelectorAll(".setup-progress li")) {
      const index = Number(marker.dataset.step);
      marker.classList.toggle("complete", index < step);
      marker.classList.toggle("active", index === step);
      if (index === step) marker.setAttribute("aria-current", "step");
      else marker.removeAttribute("aria-current");
    }
    $("#setup-back").hidden = step === 0;
    const frame = frames[step];
    window.scrollTo({ top: 0, behavior: "instant" });
    if (step === 1 && !$("#setup-topics").dataset.edited)
      $("#setup-topics").value = state?.interests || "";
    if (focus) frame.querySelector("h1").focus({ preventScroll: true });
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches)
      transition = frame.animate?.(
        entrance
          ? [
              { opacity: 0, transform: "translateY(10px)" },
              { opacity: 1, transform: "translateY(0)" },
            ]
          : [
              { opacity: 0, transform: "translateX(12px)" },
              { opacity: 1, transform: "translateX(0)" },
            ],
        { duration: entrance ? 420 : 260, easing: "cubic-bezier(.16,1,.3,1)" },
      );
  }
  async function perform(action) {
    if (working) return;
    working = true;
    feedback();
    $("#onboarding").setAttribute("aria-busy", "true");
    const buttons = [...$("#onboarding").querySelectorAll("button")];
    buttons.forEach((button) => (button.disabled = true));
    $("#setup-working").hidden = false;
    let failed = false;
    try {
      await action();
    } catch (error) {
      failed = true;
      feedback(error.message);
    } finally {
      working = false;
      $("#onboarding").setAttribute("aria-busy", "false");
      buttons.forEach((button) => (button.disabled = false));
      $("#setup-working").hidden = true;
      if (failed) frames[step].querySelector("input,textarea,button")?.focus();
    }
  }
  $("#setup-connect-form").addEventListener("submit", (event) => {
    event.preventDefault();
    perform(async () => {
      updateStatus(state || (await pair($("#setup-pair-key").value.trim())));
      $("#setup-pair-key").value = "";
      move(1);
    });
  });
  $("#setup-topics").addEventListener("input", () => {
    $("#setup-topics").dataset.edited = "true";
  });
  $("#setup-topics-form").addEventListener("submit", (event) => {
    event.preventDefault();
    perform(async () => {
      const interests = $("#setup-topics").value.trim();
      if (interests !== (state?.interests || "").trim())
        updateStatus(await request("/api/interests", { interests }));
      move(2);
    });
  });
  $("#setup-skip-topics").addEventListener("click", () => move(2));
  $("#setup-access-form").addEventListener("submit", (event) => {
    event.preventDefault();
    perform(async () => {
      try {
        if (!state?.tabpfn_configured)
          updateStatus(
            await request("/api/tabpfn-access", {
              token: $("#setup-tabpfn-token").value.trim(),
            }),
          );
        move(3);
      } finally {
        $("#setup-tabpfn-token").value = "";
      }
    });
  });
  $("#setup-skip-access").addEventListener("click", () => move(3));
  $("#setup-back").addEventListener("click", () => move(Math.max(0, step - 1)));
  $("#setup-finish").addEventListener("click", () =>
    perform(async () => {
      await remember();
      active = false;
      transition?.cancel();
      $("#onboarding").hidden = true;
      $(".connection-line").hidden = false;
      $("#settings-button").hidden = false;
      await onDone();
      $("#shortlist-tab").focus();
    }),
  );
  return {
    get active() {
      return active;
    },
    start(next) {
      active = true;
      state = next;
      updateStatus(next);
      delete $("#setup-topics").dataset.edited;
      $("#setup-topics").value = next?.interests || "";
      $("#setup-pair-key").value = "";
      $("#setup-tabpfn-token").value = "";
      $("#onboarding").hidden = false;
      $("#workspace").hidden = true;
      $("#settings").hidden = true;
      $("#connect").hidden = true;
      $(".connection-line").hidden = true;
      $("#settings-button").hidden = true;
      move(0, { focus: false, entrance: true });
    },
    async refresh() {
      try {
        updateStatus(await request("/api/status"));
      } catch {
        /* Keep a user's entered setup details on a temporary outage. */
      }
    },
  };
}
