// settings.js
// Purpose: Selectors and helpers for match format, game mode, and team size fields.

export function wirePasswordToggle(input, toggle) {
  toggle.addEventListener("click", () => {
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    toggle.textContent = showing ? "View" : "Hide";
  });
}

export function selectedMode() {
  const checked = document.querySelector("input[name=mode]:checked");
  return checked ? checked.value : "bo1";
}

export function selectedGameMode() {
  const checked = document.querySelector("input[name=gameMode]:checked");
  return checked ? checked.value : "versus";
}

export function teamSizeToMax(size) {
  return size * 2;
}

export function maxToTeamSize(max) {
  const size = Math.round((Number(max) || 10) / 2);
  return Math.min(5, Math.max(1, size));
}

export function selectedTeamSize() {
  const checked = document.querySelector("input[name=teamSize]:checked");
  return checked ? Number(checked.value) : 5;
}

export function applyGameModeLock() {
  const checked = document.querySelector("input[name=gameMode]:checked");
  const isVersus = !checked || checked.value === "versus";
  document.querySelectorAll("input[name=mode], input[name=teamSize]").forEach((input) => {
    input.disabled = !isVersus;
  });
}
