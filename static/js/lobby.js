// lobby.js
// Purpose: Renders the lobby create/join/members bar and its create/join/leave actions.

import {
  lobbyActive,
  lobbyBar,
  lobbyCode,
  lobbyConnect,
  lobbyConnectLink,
  lobbyConnectText,
  lobbyEmpty,
  lobbyMembers,
  lobbyMsg,
  lobbyResetBtn,
  lobbyStartBtn,
} from "./dom.js";

export function renderLobby(auth, lobby) {
  const loggedIn = !!(auth && auth.loggedIn);
  lobbyBar.hidden = !loggedIn;
  if (!loggedIn) return;

  const inLobby = !!lobby;
  lobbyEmpty.hidden = inLobby;
  lobbyActive.hidden = !inLobby;
  if (!inLobby) return;

  lobbyCode.textContent = lobby.code;
  lobbyMembers.innerHTML = "";
  for (const member of lobby.members) {
    const row = document.createElement("div");
    row.className = "lobby-member";
    if (member.avatar) {
      const img = document.createElement("img");
      img.className = "lobby-member-avatar";
      img.alt = "";
      img.src = member.avatar;
      row.appendChild(img);
    }
    const name = document.createElement("span");
    name.textContent = member.displayName + (member.steamId === lobby.host ? " (host)" : "");
    row.appendChild(name);
    lobbyMembers.appendChild(row);
  }

  const isHost = lobby.host === auth.steamId;
  lobbyStartBtn.hidden = !(isHost && lobby.state === "waiting");
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

async function postLobbyAction(path, body) {
  lobbyMsg.textContent = "";
  const res = await fetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!data.ok) lobbyMsg.textContent = data.error || "Something went wrong";
  return data.ok;
}

export function createLobby() {
  return postLobbyAction("/api/lobby/create");
}

export function joinLobby(code) {
  return postLobbyAction("/api/lobby/join", { code });
}

export function leaveLobby() {
  return postLobbyAction("/api/lobby/leave");
}

export function startMatch() {
  return postLobbyAction("/api/lobby/start");
}

export function resetLobby() {
  return postLobbyAction("/api/lobby/reset");
}
