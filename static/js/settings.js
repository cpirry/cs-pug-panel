// settings.js
// Purpose: Selectors and helpers for match format, game mode, and team size fields.

export function selectedMode() {
  const checked = document.querySelector("input[name=mode]:checked");
  return checked ? checked.value : "bo1";
}

export function selectedGameMode() {
  return "versus";
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

export function selectedSmallTeamMode() {
  const checked = document.querySelector("input[name=smallTeamMode]:checked");
  return checked ? checked.value : "defusal";
}
