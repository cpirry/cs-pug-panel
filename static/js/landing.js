// landing.js
// Purpose: Entry point for the root page - shows the login prompt or the host/join lobby view,
// and wires up hosting, joining, and the invite-link modal.

import {
  steamLogoutBtn,
  landingWrap,
  loginCard,
  lobbyEntryCard,
  landingAvatar,
  landingName,
  hostBtn,
  joinCodeInput,
  joinBtn,
  joinMsg,
  lobbyModalCode,
  lobbyModalCopyBtn,
  lobbyModalContinueBtn,
  lobbyModalMsg,
  statsGrid,
  recentGamesBody,
  myGamesBody,
} from "./dom.js";
import { renderAuth } from "./auth.js";
import { createLobby, joinLobby, showLobbyModal, buildLobbyLink } from "./lobby.js";
import { fetchMatches, fetchPlayerMatches, renderMatchRows, renderPlayerMatchRows } from "./history.js";

const STAT_TILES = [
  ["Total Matches", "matches_played"],
  ["Total Wins", "wins"],
  ["Total Losses", "losses"],
  ["Kills", "kills"],
  ["Deaths", "deaths"],
  ["K/D", "kd_ratio"],
  ["ADR", "adr"],
  ["Headshot %", "headshot_pct"],
];

async function renderStats() {
  const res = await fetch("/api/stats/me");
  if (!res.ok) return;
  const stats = await res.json();
  statsGrid.innerHTML = STAT_TILES.map(
    ([label, key]) => `
      <div class="stat-tile">
        <span class="stat-tile-label">${label}</span>
        <span class="stat-tile-value">${stats[key]}</span>
      </div>
    `
  ).join("");
}

async function renderRecentGames() {
  const matches = await fetchMatches();
  renderMatchRows(recentGamesBody, matches.slice(0, 5));
}

async function renderMyGames() {
  const matches = await fetchPlayerMatches();
  renderPlayerMatchRows(myGamesBody, matches);
}

steamLogoutBtn.addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  await init();
});

hostBtn.addEventListener("click", async () => {
  hostBtn.disabled = true;
  joinMsg.textContent = "";
  const data = await createLobby();
  if (data.ok) {
    showLobbyModal(data.code);
  } else {
    joinMsg.textContent = data.error || "Couldn't create a lobby";
    joinMsg.className = "msg err";
  }
  hostBtn.disabled = false;
});

joinBtn.addEventListener("click", async () => {
  const code = joinCodeInput.value.trim();
  if (!code) return;
  joinBtn.disabled = true;
  joinMsg.textContent = "";
  const data = await joinLobby(code);
  if (data.ok) {
    window.location.href = "/app.html";
    return;
  }
  joinMsg.textContent = data.error || "Couldn't join that lobby";
  joinMsg.className = "msg err";
  joinBtn.disabled = false;
});

lobbyModalCopyBtn.addEventListener("click", async () => {
  const link = buildLobbyLink(lobbyModalCode.textContent);
  try {
    await navigator.clipboard.writeText(link);
    lobbyModalMsg.textContent = "Copied!";
    lobbyModalMsg.className = "msg ok";
  } catch {
    lobbyModalMsg.textContent = "Couldn't copy automatically - link: " + link;
    lobbyModalMsg.className = "msg err";
  }
});

lobbyModalContinueBtn.addEventListener("click", () => {
  window.location.href = "/app.html";
});

async function init() {
  const res = await fetch("/api/state");
  if (res.status === 401) {
    landingWrap.hidden = false;
    loginCard.hidden = false;
    lobbyEntryCard.hidden = true;
    renderAuth({ loggedIn: false });
    return;
  }
  const state = await res.json();
  landingWrap.hidden = true;
  loginCard.hidden = true;
  lobbyEntryCard.hidden = false;
  renderAuth(state.auth);
  if (state.auth.avatarFull) {
    landingAvatar.src = state.auth.avatarFull;
    landingAvatar.hidden = false;
  } else {
    landingAvatar.hidden = true;
  }
  landingName.textContent = state.auth.displayName;

  const invitedCode = new URLSearchParams(window.location.search).get("lobby");
  if (invitedCode) joinCodeInput.value = invitedCode.trim().toUpperCase();

  renderStats();
  renderMyGames();
  renderRecentGames();
}

init();
