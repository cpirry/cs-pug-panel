// lobby.js
// Purpose: Renders lobby-level UI (code, ready/start/reset controls) and drives lobby actions.

import {
  lobbyCode,
  lobbyCodeCopyBtn,
  lobbyConnect,
  lobbyConnectLink,
  lobbyConnectText,
  lobbyModal,
  lobbyModalCode,
  lobbyResetBtn,
  lobbyStartBtn,
} from "./dom.js";

export function renderLobby(auth, lobby) {
  const loggedIn = !!(auth && auth.loggedIn);
  const show = loggedIn && !!lobby;
  lobbyCode.hidden = !show;
  lobbyCodeCopyBtn.hidden = !show;
  if (!show) return;

  lobbyCode.textContent = lobby.code;

  const isHost = lobby.host === auth.steamId;
  const total = lobby.members.length;
  const unready = lobby.members.filter((m) => !m.ready).length;

  lobbyStartBtn.hidden = !(isHost && lobby.state === "waiting");
  lobbyStartBtn.disabled = unready > 0;
  lobbyStartBtn.textContent =
    unready > 0 ? `Waiting on ready players (${unready}/${total})` : "Start match";
  lobbyResetBtn.hidden = !(isHost && lobby.state === "in_match");

  const connect = lobby.connect;
  lobbyConnect.hidden = !connect;
  if (connect) {
    lobbyConnectLink.hidden = !connect.steamUrl;
    if (connect.steamUrl) lobbyConnectLink.href = connect.steamUrl;
    const host = connect.host || "(connect host not configured)";
    lobbyConnectText.textContent = `${host}:${connect.port} • password: ${connect.password}`;
  }
}

export function showLobbyModal(code) {
  lobbyModalCode.textContent = code;
  lobbyModal.hidden = false;
}

export function buildLobbyLink(code) {
  return `${window.location.origin}/?lobby=${code}`;
}

async function postLobbyAction(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

export function createLobby() {
  return postLobbyAction("/api/lobby/create");
}

export function joinLobby(code) {
  return postLobbyAction("/api/lobby/join", { code });
}

export function toggleReady() {
  return postLobbyAction("/api/lobby/ready");
}

export function startMatch() {
  return postLobbyAction("/api/lobby/start");
}

export function resetLobby() {
  return postLobbyAction("/api/lobby/reset");
}

export function moveMember(steamId, team, swapWith) {
  return postLobbyAction("/api/lobby/move", { steamId, team, swapWith });
}
