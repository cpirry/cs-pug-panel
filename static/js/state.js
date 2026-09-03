// state.js
// Purpose: Fetches server state and drives status/launch-button/map/mod rendering.

import {
  statusEl,
  launchBtn,
  launchBtnIdleLabel,
  stopBtn,
  mapBtn,
  rconInput,
  rconSend,
  logsEl,
  serverNameInput,
  serverPasswordInput,
  rconPasswordInput,
  maxPlayersInput,
  ctTeamNameInput,
  tTeamNameInput,
  metaMapEl,
  metaUptimeEl,
} from "./dom.js";
import { renderAuth } from "./auth.js";
import { renderMaps, activateMapTabFor } from "./maps.js";
import { renderMods } from "./mods.js";
import { maxToTeamSize, applyGameModeLock } from "./settings.js";
import { setConsoleRunning, renderConsole, renderLines, renderPlayers, setLatestTail } from "./console.js";
import { formatDuration } from "./format.js";

export function setStatus(running, status) {
  statusEl.textContent = status;
  statusEl.className = "status-pill " + (running ? "running" : "stopped");
  launchBtn.disabled = running;
  stopBtn.disabled = !running;
  mapBtn.disabled = !running;
  mapBtn.title = running ? "" : "Can only change the map when the server is running.";
  rconInput.disabled = !running;
  rconSend.disabled = !running;
  setConsoleRunning(running);
}

export function updateLaunchButtonLabel(running, matchTime) {
  launchBtn.textContent = running ? `Live for: ${formatDuration(matchTime)}` : launchBtnIdleLabel;
}

export async function loadState() {
  const res = await fetch("/api/state");
  const state = await res.json();
  setStatus(state.running, state.status);
  renderAuth(state.auth);
  renderConsole();
  updateLaunchButtonLabel(state.running, null);
  renderMaps(state.maps, state.selectedMap);
  activateMapTabFor(state.selectedMap, state.maps);
  renderMods(state.mods);
  serverNameInput.value = state.settings.serverName;
  serverPasswordInput.value = state.settings.password;
  rconPasswordInput.value = state.settings.rconPassword;
  maxPlayersInput.value = state.settings.maxPlayers;
  ctTeamNameInput.value = state.settings.ctTeamName;
  tTeamNameInput.value = state.settings.tTeamName;
  const modeInput = document.querySelector(`input[name=mode][value="${state.mode}"]`);
  if (modeInput) modeInput.checked = true;
  const gameModeInput = document.querySelector(`input[name=gameMode][value="${state.gameMode}"]`);
  if (gameModeInput) gameModeInput.checked = true;
  applyGameModeLock();
  const teamSizeInput = document.querySelector(
    `input[name=teamSize][value="${maxToTeamSize(state.settings.maxPlayers)}"]`
  );
  if (teamSizeInput) teamSizeInput.checked = true;
  metaMapEl.textContent = state.selectedMap || "no start map set";
}

export async function refreshMaps() {
  const res = await fetch("/api/state");
  const state = await res.json();
  renderMaps(state.maps, state.selectedMap);
}

export async function pollTail() {
  const res = await fetch("/api/tail?n=200");
  const data = await res.json();
  setStatus(data.running, data.status);
  setLatestTail(data.console);
  renderConsole();
  renderLines(logsEl, data.logs);
  renderPlayers(data.running, data.players);
  metaUptimeEl.textContent = formatDuration(data.serverUptime);
  updateLaunchButtonLabel(data.running, data.matchTime);
}
