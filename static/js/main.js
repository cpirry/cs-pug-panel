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
  forceStopBtn,
  rosterTEl,
  rosterCtEl,
  lobbyCode,
  lobbyCodeCopyBtn,
  lobbyConnectCopyBtn,
  invitePlayerBtn,
  invitePlayerModal,
  invitePlayerLink,
  invitePlayerCopyBtn,
  invitePlayerCloseBtn,
  invitePlayerMsg,
  deleteLobbyBtn,
  mapsCoreEl,
  mapsWingmanEl,
  mapsExtraEl,
  mapsWorkshopEl,
} from "./dom.js";
import { selectedMap, selectedMapSource } from "./maps.js";
import {
  selectedMode,
  selectedGameMode,
  teamSizeToMax,
  selectedTeamSize,
  selectedSmallTeamMode,
} from "./settings.js";
import { renderRoster } from "./roster.js";
import { wireSubtabs } from "./subtabs.js";
import { pushRconHistory, renderConsole } from "./console.js";
import { loadConfig, renderPresets } from "./config.js";
import {
  toggleReady,
  startMatch,
  forceStopServer,
  moveMember,
  kickMember,
  deleteLobby,
  buildLobbyLink,
} from "./lobby.js";
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
      smallTeamMode: selectedSmallTeamMode(),
      ctTeamName: ctTeamNameInput.value,
      tTeamName: tTeamNameInput.value,
      ...extra,
    }),
  });
}

lobbyStartBtn.addEventListener("click", async () => {
  lobbyStartBtn.disabled = true;
  lobbyStartBtn.textContent = "Starting...";
  try {
    await pushSettings({ map: selectedMap(), mapSource: selectedMapSource() });
    const data = await startMatch();
    lobbyMsg.textContent = data.ok ? "" : data.error || "Something went wrong";
  } catch {
    // The request can still have succeeded server-side even if the response never made it
    // back (e.g. starting the container is slow enough that the connection drops before the
    // reply is sent) - loadState() below re-derives the real button state from the server
    // either way, instead of leaving the button stuck on "Starting..." forever.
    lobbyMsg.textContent = "Lost connection while starting - checking current status...";
  } finally {
    await loadState();
  }
});

forceStopBtn.addEventListener("click", async () => {
  if (!window.confirm("Force stop the server? This stops the container, closes the firewall ports, and resets the lobby back to waiting.")) return;
  forceStopBtn.disabled = true;
  forceStopBtn.textContent = "Stopping...";
  try {
    const data = await forceStopServer();
    lobbyMsg.textContent = data.ok ? "" : data.error || "Something went wrong";
  } catch {
    // As with Start Match, the stop can still have succeeded server-side even if the
    // response was lost - loadState() re-derives the real state either way.
    lobbyMsg.textContent = "Lost connection while stopping - checking current status...";
  } finally {
    forceStopBtn.textContent = "Force Stop Server";
    forceStopBtn.disabled = false;
    await loadState();
  }
});

deleteLobbyBtn.addEventListener("click", async () => {
  if (!window.confirm("Delete this lobby? This removes everyone from it.")) return;
  deleteLobbyBtn.disabled = true;
  const data = await deleteLobby();
  if (data.ok) {
    window.location.href = "/";
    return;
  }
  lobbyMsg.textContent = data.error || "Couldn't delete this lobby";
  deleteLobbyBtn.disabled = false;
});

[rosterTEl, rosterCtEl].forEach((container) => {
  container.addEventListener("change", async (e) => {
    if (!e.target.classList.contains("roster-ready-checkbox")) return;
    // Don't imperatively disable e.target here: Preact tracks this checkbox's "disabled" prop
    // independently of the real DOM (it's always `false` for your own checkbox, every render),
    // so if the actual value is ever changed outside a Preact-driven write, Preact's diff sees
    // no change next render and never writes `false` back - the checkbox stays stuck disabled
    // forever. That's exactly what was blocking unreadying here.
    const data = await toggleReady();
    lobbyMsg.textContent = data.ok ? "" : data.error || "Something went wrong";
    await loadState();
  });

  container.addEventListener("click", async (e) => {
    const kickBtn = e.target.closest(".roster-slot-kick");
    if (!kickBtn) return;
    if (!window.confirm("Kick this player from the lobby?")) return;
    kickBtn.disabled = true;
    const data = await kickMember(kickBtn.dataset.steamId);
    lobbyMsg.textContent = data.ok ? "" : data.error || "Couldn't kick that player";
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

lobbyConnectCopyBtn.addEventListener("click", async () => {
  const command = lobbyConnectCopyBtn.dataset.connectCommand;
  if (!command) return;
  try {
    await navigator.clipboard.writeText(command);
    const original = lobbyConnectCopyBtn.textContent;
    lobbyConnectCopyBtn.textContent = "Copied!";
    setTimeout(() => (lobbyConnectCopyBtn.textContent = original), 1200);
  } catch {
    // clipboard unavailable - nothing else to surface here
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

[mapsCoreEl, mapsWingmanEl, mapsExtraEl, mapsWorkshopEl].forEach((container) => {
  container.addEventListener("change", async (e) => {
    if (e.target.name !== "map") return;
    // Just persists which tile is picked (for everyone else to see live) - doesn't touch the
    // running server. Only "Change Map" below actually applies it.
    const res = await fetch("/api/lobby/map", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ map: selectedMap(), mapSource: selectedMapSource() }),
    });
    const data = await res.json();
    if (!data.ok) mapMsg.textContent = data.error || "Couldn't select that map";
    // The clicked radio already highlights itself natively, but if a Random pick was active,
    // its tile's "is-active" class is plain Preact-rendered state - nothing clears it on its own.
    // Force a sync so it turns off now that a specific map was picked instead.
    await loadState({ syncMaps: true });
  });

  container.addEventListener("randommap", async (e) => {
    const res = await fetch("/api/lobby/map", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ map: e.detail.map, mapSource: "local", isRandom: true }),
    });
    const data = await res.json();
    if (!data.ok) mapMsg.textContent = data.error || "Couldn't select that map";
    // Unlike a normal tile pick, nothing in the DOM changes on its own here (no radio gets
    // checked, on purpose) - force a map re-render so the Random tile shows as the active pick
    // and the previously-selected tile (if any) clears. Plain loadState() defaults syncMaps to
    // false and skips re-rendering maps at all for the host, to avoid disrupting their local
    // browsing - but this IS an authoritative selection change, so it must sync regardless.
    await loadState({ syncMaps: true });
  });
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
  await loadState({ syncMaps: true });
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
  });
});

document.querySelectorAll(".admin-subnav .subtab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.subtab === "monitoring") {
      consoleEl.scrollTop = consoleEl.scrollHeight;
      logsEl.scrollTop = logsEl.scrollHeight;
    }
  });
});

wireSubtabs();

document.querySelectorAll('input[name=teamSize]').forEach((input) => {
  input.addEventListener("change", () => {
    renderRoster(selectedTeamSize());
    const size = selectedTeamSize();
    document.querySelectorAll('input[name=smallTeamMode]').forEach((modeInput) => {
      modeInput.disabled = !(size >= 2 && size <= 4);
    });
    pushSettings();
  });
});

document.querySelectorAll('input[name=mode]').forEach((input) => {
  input.addEventListener("change", () => {
    pushSettings();
  });
});

document.querySelectorAll('input[name=smallTeamMode]').forEach((input) => {
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

loadState({ syncMaps: true });
loadConfig();
setInterval(pollTail, 3000);
setInterval(loadState, 3000);
