// lobby.js
// Purpose: Renders lobby-level UI (code, ready/start/reset controls) and drives lobby actions.

import {
  deleteLobbyBtn,
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
  const ready = lobby.members.filter((m) => m.ready).length;
  const unready = total - ready;

  lobbyStartBtn.hidden = lobby.state !== "waiting";
  lobbyStartBtn.disabled = unready > 0 || !isHost;
  lobbyStartBtn.textContent =
    unready > 0
      ? `Waiting on ready players (${ready}/${total})`
      : isHost
      ? "Start match"
      : "Match ready to start";
  lobbyResetBtn.hidden = !(isHost && lobby.state === "in_match");
  deleteLobbyBtn.hidden = !isHost;

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

export function kickMember(steamId) {
  return postLobbyAction("/api/lobby/kick", { steamId });
}

export function deleteLobby() {
  return postLobbyAction("/api/lobby/delete");
}
