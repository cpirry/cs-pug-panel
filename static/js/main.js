// main.js
// Purpose: Entry point - wires up all DOM event listeners and kicks off polling.

import {
  mapBtn,
  mapMsg,
  workshopInput,
  workshopAddBtn,
  workshopMsg,
  rconForm,
  rconInput,
  rconSend,
  consoleEl,
  logsEl,
  ctTeamNameInput,
  tTeamNameInput,
  configFileSelect,
  configEditor,
  configSaveBtn,
  configMsg,
  presetName,
  presetSaveBtn,
  steamLogoutBtn,
  lobbyMsg,
  lobbyStartBtn,
  lobbyResetBtn,
  rosterTEl,
  rosterCtEl,
  lobbyCode,
  lobbyCodeCopyBtn,
  invitePlayerBtn,
  invitePlayerModal,
  invitePlayerLink,
  invitePlayerCopyBtn,
  invitePlayerCloseBtn,
  invitePlayerMsg,
} from "./dom.js";
import { selectedMap, selectedMapSource } from "./maps.js";
import { selectedMode, selectedGameMode, teamSizeToMax, selectedTeamSize } from "./settings.js";
import { renderRoster } from "./roster.js";
import { wireSubtabs } from "./subtabs.js";
import { pushRconHistory, renderConsole } from "./console.js";
import { loadConfig, renderPresets } from "./config.js";
import { toggleReady, startMatch, resetLobby, moveMember, buildLobbyLink } from "./lobby.js";
import { loadState, refreshMaps, pollTail } from "./state.js";

steamLogoutBtn.addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  await loadState();
});

function pushSettings(extra = {}) {
  return fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      maxPlayers: teamSizeToMax(selectedTeamSize()),
      mode: selectedMode(),
      gameMode: selectedGameMode(),
      ctTeamName: ctTeamNameInput.value,
      tTeamName: tTeamNameInput.value,
      ...extra,
    }),
  });
}

lobbyStartBtn.addEventListener("click", async () => {
  lobbyStartBtn.disabled = true;
  lobbyStartBtn.textContent = "Starting...";
  await pushSettings({ map: selectedMap() });
  const data = await startMatch();
  lobbyMsg.textContent = data.ok ? "" : data.error || "Something went wrong";
  await loadState();
});

lobbyResetBtn.addEventListener("click", async () => {
  lobbyResetBtn.disabled = true;
  const data = await resetLobby();
  lobbyMsg.textContent = data.ok ? "" : data.error || "Something went wrong";
  await loadState();
  lobbyResetBtn.disabled = false;
});

[rosterTEl, rosterCtEl].forEach((container) => {
  container.addEventListener("change", async (e) => {
    if (!e.target.classList.contains("roster-ready-checkbox")) return;
    e.target.disabled = true;
    const data = await toggleReady();
    lobbyMsg.textContent = data.ok ? "" : data.error || "Something went wrong";
    await loadState();
  });

  container.addEventListener("dragstart", (e) => {
    const slot = e.target.closest(".roster-slot-draggable");
    if (!slot) {
      e.preventDefault();
      return;
    }
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", slot.dataset.steamId);
  });

  container.addEventListener("dragover", (e) => {
    if (!e.dataTransfer.types.includes("text/plain")) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    const slot = e.target.closest(".roster-slot");
    if (slot) slot.classList.add("drag-over");
  });

  container.addEventListener("dragleave", (e) => {
    const slot = e.target.closest(".roster-slot");
    if (slot) slot.classList.remove("drag-over");
  });

  container.addEventListener("drop", async (e) => {
    e.preventDefault();
    const slot = e.target.closest(".roster-slot");
    if (slot) slot.classList.remove("drag-over");
    const draggedId = e.dataTransfer.getData("text/plain");
    if (!draggedId || !slot) return;
    const targetId = slot.dataset.steamId;
    if (targetId === draggedId) return;
    const data = await moveMember(draggedId, container.dataset.team, targetId || undefined);
    lobbyMsg.textContent = data.ok ? "" : data.error || "Couldn't move that player";
    await loadState();
  });
});

lobbyCodeCopyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(lobbyCode.textContent);
    lobbyCodeCopyBtn.classList.add("is-copied");
    setTimeout(() => lobbyCodeCopyBtn.classList.remove("is-copied"), 1200);
  } catch {
    // clipboard unavailable - nothing else to surface for an icon-only button
  }
});

function closeInvitePlayerModal() {
  invitePlayerModal.hidden = true;
}

invitePlayerBtn.addEventListener("click", () => {
  invitePlayerLink.value = buildLobbyLink(lobbyCode.textContent);
  invitePlayerMsg.textContent = "";
  invitePlayerModal.hidden = false;
});

invitePlayerCloseBtn.addEventListener("click", closeInvitePlayerModal);

invitePlayerModal.addEventListener("click", (e) => {
  if (e.target === invitePlayerModal) closeInvitePlayerModal();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !invitePlayerModal.hidden) closeInvitePlayerModal();
});

invitePlayerCopyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(invitePlayerLink.value);
    invitePlayerMsg.textContent = "Copied!";
    invitePlayerMsg.className = "msg ok";
  } catch {
    invitePlayerMsg.textContent = "Couldn't copy automatically";
    invitePlayerMsg.className = "msg err";
  }
});

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

document.querySelectorAll(".side-nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".side-nav-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => (p.hidden = true));
    btn.classList.add("active");
    document.querySelector(`.tab-panel[data-panel="${btn.dataset.tab}"]`).hidden = false;
    if (btn.dataset.tab === "logs") {
      consoleEl.scrollTop = consoleEl.scrollHeight;
      logsEl.scrollTop = logsEl.scrollHeight;
    }
  });
});

wireSubtabs();

document.querySelectorAll('input[name=teamSize]').forEach((input) => {
  input.addEventListener("change", () => {
    renderRoster(selectedTeamSize());
    pushSettings();
  });
});

document.querySelectorAll('input[name=mode]').forEach((input) => {
  input.addEventListener("change", () => {
    pushSettings();
  });
});

[ctTeamNameInput, tTeamNameInput].forEach((input) => {
  input.addEventListener("change", () => {
    pushSettings();
  });
});

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
