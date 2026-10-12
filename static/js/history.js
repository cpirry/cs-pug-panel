// history.js
// Purpose: Renders match lists (the full Match History table, and the landing page's
// "Latest Games" list) from the real /api/matches backend.

import { historyTableBody } from "./dom.js";

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function formatDate(isoString) {
  const d = new Date(isoString);
  const day = DAY_NAMES[d.getDay()];
  const month = MONTH_NAMES[d.getMonth()];
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${day} ${d.getDate()} ${month} ${hh}:${mm}`;
}

function formatScore(match) {
  return `${Math.max(match.score_ct, match.score_t)}:${Math.min(match.score_ct, match.score_t)}`;
}

export function renderMatchRows(tbody, matches) {
  tbody.innerHTML = "";
  for (const match of matches) {
    const tr = document.createElement("tr");
    tr.className = "history-row";
    tr.addEventListener("click", () => {
      window.location.href = `match.html?id=${encodeURIComponent(match.id)}`;
    });
    tr.innerHTML = `
      <td>${formatDate(match.started_at)}</td>
      <td>${formatScore(match)}</td>
      <td>${match.map}</td>
    `;
    tbody.appendChild(tr);
  }
}

export function renderPlayerMatchRows(tbody, matches) {
  tbody.innerHTML = "";
  for (const match of matches) {
    const tr = document.createElement("tr");
    tr.className = "history-row";
    tr.addEventListener("click", () => {
      window.location.href = `match.html?id=${encodeURIComponent(match.id)}`;
    });
    tr.innerHTML = `
      <td>${formatDate(match.started_at)}</td>
      <td>${formatScore(match)}</td>
      <td>${match.kills}/${match.deaths}/${match.assists}</td>
      <td>${match.adr}</td>
      <td>${match.map}</td>
    `;
    tbody.appendChild(tr);
  }
}

export async function fetchMatches() {
  const res = await fetch("/api/matches");
  if (!res.ok) return [];
  const data = await res.json();
  return data.matches;
}

export async function fetchPlayerMatches() {
  const res = await fetch("/api/matches/mine");
  if (!res.ok) return [];
  const data = await res.json();
  return data.matches;
}

export async function renderHistoryTable() {
  const matches = await fetchMatches();
  renderMatchRows(historyTableBody, matches);
}
