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
} from "./dom.js";
import { renderAuth } from "./auth.js";
import { renderLobby } from "./lobby.js";
import { renderMaps, activateMapTabFor } from "./maps.js";
import { renderMods } from "./mods.js";
import { maxToTeamSize } from "./settings.js";
import { renderRoster } from "./roster.js";
import { setConsoleRunning, renderConsole, renderLines, renderPlayers, setLatestTail } from "./console.js";

export function setStatus(running) {
  mapBtn.disabled = !running;
  mapBtn.title = running ? "" : "Can only change the map when the server is running.";
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

export async function loadState() {
  const res = await fetch("/api/state");
  if (redirectIfUnauthorized(res)) return null;
  const state = await res.json();
  setStatus(state.running);
  renderAuth(state.auth);
  renderLobby(state.auth, state.lobby);
  renderConsole();
  renderMaps(state.maps, state.selectedMap);
  activateMapTabFor(state.selectedMap, state.maps);
  renderMods(state.mods);
  ctTeamNameInput.value = state.settings.ctTeamName;
  tTeamNameInput.value = state.settings.tTeamName;
  const modeInput = document.querySelector(`input[name=mode][value="${state.mode}"]`);
  if (modeInput) modeInput.checked = true;
  const teamSize = maxToTeamSize(state.settings.maxPlayers);
  const teamSizeInput = document.querySelector(`input[name=teamSize][value="${teamSize}"]`);
  if (teamSizeInput) teamSizeInput.checked = true;
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
  renderMaps(state.maps, state.selectedMap);
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
