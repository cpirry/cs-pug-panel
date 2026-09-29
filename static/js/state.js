// state.js
// Purpose: Fetches server state and drives status/map/mod/lobby rendering.

import {
  mapBtn,
  rconInput,
  rconSend,
  logsEl,
  ctTeamNameInput,
  tTeamNameInput,
  serverHeadingNameEl,
  contentEl,
  sideNavEl,
  workshopInput,
  workshopAddBtn,
} from "./dom.js";
import { renderAuth } from "./auth.js";
import { renderLobby } from "./lobby.js";
import { renderMaps, activateMapTabFor } from "./maps.js";
import { renderMods } from "./mods.js";
import { maxToTeamSize } from "./settings.js";
import { renderRoster } from "./roster.js";
import { setConsoleRunning, renderConsole, renderLines, renderPlayers, setLatestTail } from "./console.js";

// setStatus() is also called from pollTail(), which has no lobby/auth data of its own - cache
// the host flag here (set from loadState(), which does have it) so both call sites agree on
// whether the map-change button should be host-gated instead of fighting over its disabled state.
let cachedIsHost = false;

export function setStatus(running) {
  mapBtn.disabled = !running || !cachedIsHost;
  mapBtn.title = !cachedIsHost
    ? "Only the host can change the map."
    : running
    ? ""
    : "Can only change the map when the server is running.";
  rconInput.disabled = !running;
  rconSend.disabled = !running;
  setConsoleRunning(running);
}

function redirectIfUnauthorized(res) {
  if (res.status === 401) {
    window.location.href = "/";
    return true;
  }
  return false;
}

export async function loadState({ syncMaps = false } = {}) {
  const res = await fetch("/api/state");
  if (redirectIfUnauthorized(res)) return null;
  const state = await res.json();
  if (!state.lobby) {
    window.location.href = "/";
    return null;
  }
  const isHost = !!(state.auth && state.auth.loggedIn && state.lobby.host === state.auth.steamId);
  cachedIsHost = isHost;
  setStatus(state.running);
  renderAuth(state.auth);
  renderLobby(state.auth, state.lobby);
  renderConsole();

  sideNavEl.hidden = !isHost;
  contentEl.classList.toggle("hide-nav", !isHost);

  // The host's own map pick is local browsing until they click a tile (which persists it
  // immediately) - re-rendering from server state on every poll would otherwise revert whatever
  // they're currently browsing and jump the tab back to Active Duty. Everyone else can't
  // interact with map selection at all (host-only), so there's no local browsing state of theirs
  // to protect - always sync for them, so the host's pick shows up live.
  if (syncMaps || !isHost) {
    renderMaps(
      state.maps,
      state.lobby.selectedMap,
      state.lobby.selectedMapSource,
      !isHost,
      state.lobby.selectedMapIsRandom
    );
    activateMapTabFor(state.lobby.selectedMap, state.maps);
  }
  workshopInput.disabled = !isHost;
  workshopAddBtn.disabled = !isHost;

  renderMods(state.mods, isHost);
  if (document.activeElement !== ctTeamNameInput) ctTeamNameInput.value = state.settings.ctTeamName;
  if (document.activeElement !== tTeamNameInput) tTeamNameInput.value = state.settings.tTeamName;
  const modeInput = document.querySelector(`input[name=mode][value="${state.mode}"]`);
  if (modeInput) modeInput.checked = true;
  const teamSize = maxToTeamSize(state.settings.maxPlayers);
  const teamSizeInput = document.querySelector(`input[name=teamSize][value="${teamSize}"]`);
  if (teamSizeInput) teamSizeInput.checked = true;
  document.querySelectorAll('input[name=teamSize]').forEach((input) => {
    input.disabled = !isHost;
  });

  const smallTeamModeInput = document.querySelector(
    `input[name=smallTeamMode][value="${state.settings.smallTeamMode}"]`
  );
  if (smallTeamModeInput) smallTeamModeInput.checked = true;
  const smallTeamModeApplicable = teamSize >= 2 && teamSize <= 4;
  document.querySelectorAll('input[name=smallTeamMode]').forEach((input) => {
    input.disabled = !isHost || !smallTeamModeApplicable;
  });
  renderRoster(teamSize, state.lobby, state.auth);
  if (state.auth && state.auth.loggedIn) {
    serverHeadingNameEl.textContent = `${state.auth.displayName}'s Lobby`;
  }
  return state;
}

export async function refreshMaps() {
  const res = await fetch("/api/state");
  if (redirectIfUnauthorized(res)) return;
  const state = await res.json();
  const isHost = !!(state.auth && state.lobby && state.lobby.host === state.auth.steamId);
  renderMaps(
    state.maps,
    state.lobby ? state.lobby.selectedMap : "",
    state.lobby ? state.lobby.selectedMapSource : "local",
    !isHost,
    state.lobby ? state.lobby.selectedMapIsRandom : false
  );
}

export async function pollTail() {
  const res = await fetch("/api/tail?n=200");
  if (redirectIfUnauthorized(res)) return;
  const data = await res.json();
  setStatus(data.running);
  setLatestTail(data.console);
  renderConsole();
  renderLines(logsEl, data.logs);
  renderPlayers(data.running, data.players);
}
