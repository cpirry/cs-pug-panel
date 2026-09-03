// console.js
// Purpose: Renders the console/log/player views and tracks console history.

import { consoleEl, playersEl } from "./dom.js";
import { classifyLine } from "./format.js";

let latestTail = "";
const rconHistory = [];
let lastRunning = false;

export function pushRconHistory(line) {
  rconHistory.push(line);
  if (rconHistory.length > 20) rconHistory.shift();
}

export function setLatestTail(text) {
  latestTail = text;
}

export function setConsoleRunning(running) {
  if (!running && lastRunning) {
    latestTail = "";
    rconHistory.length = 0;
  }
  lastRunning = running;
}

export function renderLines(el, text) {
  const stick = el.scrollTop + el.clientHeight >= el.scrollHeight - 10;
  el.innerHTML = "";
  for (const line of text.split("\n")) {
    const div = document.createElement("div");
    const cls = classifyLine(line);
    div.className = "log-line" + (cls ? " " + cls : "");
    div.textContent = line || " ";
    el.appendChild(div);
  }
  if (stick) el.scrollTop = el.scrollHeight;
}

export function renderConsole() {
  if (!lastRunning) {
    consoleEl.innerHTML = "";
    const div = document.createElement("div");
    div.className = "log-line log-offline";
    div.textContent = "Server is offline";
    consoleEl.appendChild(div);
    return;
  }
  let text = latestTail;
  if (rconHistory.length) {
    text += (text ? "\n" : "") + "\n--- commands ---\n" + rconHistory.join("\n\n");
  }
  renderLines(consoleEl, text);
}

export function renderPlayers(running, players) {
  playersEl.innerHTML = "";
  if (!running) {
    const empty = document.createElement("div");
    empty.className = "player-empty";
    empty.textContent = "Server not running";
    playersEl.appendChild(empty);
    return;
  }
  if (!players.length) {
    const empty = document.createElement("div");
    empty.className = "player-empty";
    empty.textContent = "No players connected";
    playersEl.appendChild(empty);
    return;
  }
  for (const player of players) {
    const row = document.createElement("div");
    row.className = "player-row";
    const dot = document.createElement("span");
    dot.className = "dot";
    const name = document.createElement("span");
    name.textContent = player.name;
    const ping = document.createElement("span");
    ping.className = "player-ping";
    ping.textContent = `${player.ping}ms`;
    row.appendChild(dot);
    row.appendChild(name);
    row.appendChild(ping);
    playersEl.appendChild(row);
  }
}
