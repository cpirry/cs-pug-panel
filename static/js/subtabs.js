// subtabs.js
// Purpose: Generic scoped tab-switching for `.subtab-group` blocks (Maps, Lobby mode).

export function activateSubtab(group, key) {
  group.querySelectorAll(".subtab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.subtab === key);
  });
  group.querySelectorAll(".subtab-panel").forEach((p) => {
    p.hidden = p.dataset.subpanel !== key;
  });
}

export function wireSubtabs() {
  document.querySelectorAll(".subtab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      activateSubtab(btn.closest(".subtab-group"), btn.dataset.subtab);
    });
  });
}
