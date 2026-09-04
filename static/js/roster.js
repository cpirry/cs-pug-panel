// roster.js
// Purpose: Renders player-roster slots sized to the selected team size, seeding lobby members into slots.

import { rosterCtEl, rosterTEl } from "./dom.js";

let currentLobby = null;
let currentAuth = null;

function renderRosterSide(container, count, members, canMove, hostId, selfId) {
  container.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const member = members[i] || null;
    const slot = document.createElement("div");
    slot.className = "roster-slot";
    slot.dataset.steamId = member ? member.steamId : "";
    if (member && canMove(member.steamId)) {
      slot.setAttribute("draggable", "true");
      slot.classList.add("roster-slot-draggable");
    }

    const avatar = document.createElement(member ? "img" : "div");
    avatar.className = "roster-slot-avatar";
    if (member) {
      avatar.alt = "";
      if (member.avatar) avatar.src = member.avatar;
    }
    slot.appendChild(avatar);

    const name = document.createElement("div");
    name.className = "roster-slot-name" + (member && member.ready ? " is-ready" : "");
    name.textContent = member
      ? member.displayName + (member.steamId === hostId ? " (host)" : "")
      : "Empty Slot";
    slot.appendChild(name);

    if (member) {
      const readyLabel = document.createElement("label");
      readyLabel.className = "roster-slot-ready";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "roster-ready-checkbox";
      checkbox.checked = !!member.ready;
      checkbox.disabled = member.steamId !== selfId;
      readyLabel.appendChild(checkbox);
      readyLabel.appendChild(document.createTextNode("Ready"));
      slot.appendChild(readyLabel);
    }

    container.appendChild(slot);
  }
}

export function renderRoster(teamSize, lobby = currentLobby, auth = currentAuth) {
  currentLobby = lobby;
  currentAuth = auth;
  const members = lobby && lobby.members ? lobby.members : [];
  const hostId = lobby ? lobby.host : null;
  const isHost = !!(lobby && auth && lobby.host === auth.steamId);
  const selfId = auth ? auth.steamId : null;
  const canMove = (steamId) =>
    !!lobby && lobby.state === "waiting" && (isHost || steamId === selfId);
  const tMembers = members.filter((m) => (m.team || "t") === "t");
  const ctMembers = members.filter((m) => (m.team || "t") === "ct");
  renderRosterSide(rosterTEl, teamSize, tMembers, canMove, hostId, selfId);
  renderRosterSide(rosterCtEl, teamSize, ctMembers, canMove, hostId, selfId);
}
