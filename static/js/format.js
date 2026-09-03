// format.js
// Purpose: Small formatting helpers (duration text, console line classification).

export function formatDuration(totalSeconds) {
  if (totalSeconds == null) return "--:--";
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = Math.floor(totalSeconds % 60);
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function classifyLine(line) {
  const lower = line.toLowerCase();
  if (line.startsWith("> ")) return "log-cmd";
  if (lower.includes("error") || lower.includes("fail")) return "log-error";
  if (lower.includes("warn")) return "log-warn";
  return "";
}
