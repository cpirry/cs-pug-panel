// history.js
// Purpose: Renders the Match History table from the real /api/matches backend.

import { historyTableBody } from "./dom.js";

function formatDate(isoString) {
  return isoString.replace("T", " ").slice(0, 16);
}

export async function renderHistoryTable() {
  const res = await fetch("/api/matches");
  if (!res.ok) return;
  const data = await res.json();
  historyTableBody.innerHTML = "";
  for (const match of data.matches) {
    const tr = document.createElement("tr");
    tr.className = "history-row";
    tr.addEventListener("click", () => {
      window.location.href = `match.html?id=${encodeURIComponent(match.id)}`;
    });
    tr.innerHTML = `
      <td>${formatDate(match.started_at)}</td>
      <td>${match.map}</td>
      <td>CT ${match.score_ct} - T ${match.score_t}</td>
      <td>${match.player_count}</td>
    `;
    historyTableBody.appendChild(tr);
  }
}
