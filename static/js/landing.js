// landing.js
// Purpose: Entry point for the root page - shows the login prompt or the host/join lobby view,
// and wires up hosting, joining, and the invite-link modal.

import {
  steamLogoutBtn,
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
} from "./dom.js";
import { renderAuth } from "./auth.js";
import { createLobby, joinLobby, showLobbyModal, buildLobbyLink } from "./lobby.js";

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
    loginCard.hidden = false;
    lobbyEntryCard.hidden = true;
    renderAuth({ loggedIn: false });
    return;
  }
  const state = await res.json();
  loginCard.hidden = true;
  lobbyEntryCard.hidden = false;
  renderAuth(state.auth);
  if (state.auth.avatar) {
    landingAvatar.src = state.auth.avatar;
    landingAvatar.hidden = false;
  } else {
    landingAvatar.hidden = true;
  }
  landingName.textContent = state.auth.displayName;

  const invitedCode = new URLSearchParams(window.location.search).get("lobby");
  if (invitedCode) joinCodeInput.value = invitedCode.trim().toUpperCase();
}

init();
