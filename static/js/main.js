// main.js
// Purpose: Entry point - wires up all DOM event listeners and kicks off polling.

import {
  mapBtn,
  mapMsg,
  workshopInput,
  workshopAddBtn,
  workshopMsg,
  launchBtn,
  stopBtn,
  rconForm,
  rconInput,
  rconSend,
  consoleEl,
  logsEl,
  maxPlayersInput,
  serverNameInput,
  serverPasswordInput,
  rconPasswordInput,
  rconPasswordToggle,
  serverPasswordToggle,
  ctTeamNameInput,
  tTeamNameInput,
  configFileSelect,
  configEditor,
  configSaveBtn,
  configMsg,
  presetName,
  presetSaveBtn,
  steamLogoutBtn,
} from "./dom.js";
import { selectedMap, selectedMapSource } from "./maps.js";
import {
  wirePasswordToggle,
  selectedMode,
  selectedGameMode,
  teamSizeToMax,
  selectedTeamSize,
  applyGameModeLock,
} from "./settings.js";
import { pushRconHistory, renderConsole } from "./console.js";
import { loadConfig, renderPresets } from "./config.js";
import { loadState, refreshMaps, pollTail } from "./state.js";

steamLogoutBtn.addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  await loadState();
});

wirePasswordToggle(rconPasswordInput, rconPasswordToggle);
wirePasswordToggle(serverPasswordInput, serverPasswordToggle);

mapBtn.addEventListener("click", async () => {
  mapBtn.disabled = true;
  mapMsg.textContent = "";
  const res = await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ map: selectedMap(), mapSource: selectedMapSource() }),
  });
  const data = await res.json();
  if (data.rcon) {
    mapMsg.textContent = data.rcon.ok ? "Map changed live" : "Failed: " + data.rcon.error;
    mapMsg.className = "save-msg " + (data.rcon.ok ? "ok" : "err");
  }
  await loadState();
});

workshopAddBtn.addEventListener("click", async () => {
  const input = workshopInput.value.trim();
  if (!input) return;
  workshopAddBtn.disabled = true;
  workshopMsg.textContent = "Downloading...";
  workshopMsg.className = "msg";
  const res = await fetch("/api/workshop/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });
  const data = await res.json();
  if (data.ok) {
    workshopMsg.textContent = "";
    workshopInput.value = "";
    await refreshMaps();
  } else {
    workshopMsg.textContent = data.error || "Failed to add map";
    workshopMsg.className = "msg err";
  }
  workshopAddBtn.disabled = false;
});

launchBtn.addEventListener("click", async () => {
  launchBtn.disabled = true;
  launchBtn.textContent = "Starting...";
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      serverName: serverNameInput.value,
      password: serverPasswordInput.value,
      rconPassword: rconPasswordInput.value,
      maxPlayers: teamSizeToMax(selectedTeamSize()),
      mode: selectedMode(),
      gameMode: selectedGameMode(),
      map: selectedMap(),
      ctTeamName: ctTeamNameInput.value,
      tTeamName: tTeamNameInput.value,
    }),
  });
  await fetch("/api/launch", { method: "POST" });
  await loadState();
});

stopBtn.addEventListener("click", async () => {
  stopBtn.disabled = true;
  stopBtn.textContent = "Stopping...";
  await fetch("/api/stop", { method: "POST" });
  stopBtn.textContent = "Stop Server";
  await loadState();
});

rconForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const command = rconInput.value.trim();
  if (!command) return;
  rconSend.disabled = true;
  rconInput.disabled = true;
  const res = await fetch("/api/rcon", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  });
  const data = await res.json();
  const line = data.ok
    ? `> ${command}\n${data.output}`
    : `> ${command}\nERROR: ${data.error}`;
  pushRconHistory(line);
  renderConsole();
  consoleEl.scrollTop = consoleEl.scrollHeight;
  rconInput.value = "";
  rconSend.disabled = false;
  rconInput.disabled = false;
  rconInput.focus();
});

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => (p.hidden = true));
    btn.classList.add("active");
    document.querySelector(`.tab-panel[data-panel="${btn.dataset.tab}"]`).hidden = false;
    if (btn.dataset.tab === "settings") {
      consoleEl.scrollTop = consoleEl.scrollHeight;
      logsEl.scrollTop = logsEl.scrollHeight;
    }
  });
});

document.querySelectorAll(".subtab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".subtab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".subtab-panel").forEach((p) => (p.hidden = true));
    btn.classList.add("active");
    document.querySelector(`.subtab-panel[data-mappanel="${btn.dataset.maptab}"]`).hidden = false;
  });
});

document.querySelectorAll('input[name=teamSize]').forEach((input) => {
  input.addEventListener("change", () => {
    maxPlayersInput.value = teamSizeToMax(selectedTeamSize());
  });
});

document.querySelectorAll('input[name=gameMode]').forEach((input) => {
  input.addEventListener("change", applyGameModeLock);
});

applyGameModeLock();

configFileSelect.addEventListener("change", () => {
  loadConfig(configFileSelect.value);
});

configSaveBtn.addEventListener("click", async () => {
  configSaveBtn.disabled = true;
  configMsg.textContent = "";
  const res = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file: configFileSelect.value, content: configEditor.value }),
  });
  const data = await res.json();
  if (data.live === true) {
    configMsg.textContent = "Saved and applied live";
    configMsg.className = "msg ok";
  } else if (data.live === false) {
    configMsg.textContent = "Saved, but live reload failed: " + data.liveError;
    configMsg.className = "msg err";
  } else {
    configMsg.textContent = "Saved - will apply on next launch";
    configMsg.className = "msg ok";
  }
  configSaveBtn.disabled = false;
});

presetSaveBtn.addEventListener("click", async () => {
  const name = presetName.value.trim();
  if (!name) return;
  presetSaveBtn.disabled = true;
  const res = await fetch("/api/config/presets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file: configFileSelect.value, name, content: configEditor.value }),
  });
  const data = await res.json();
  if (data.presets) {
    renderPresets(data.presets);
    presetName.value = "";
  }
  presetSaveBtn.disabled = false;
});

loadState();
loadConfig();
setInterval(pollTail, 3000);
