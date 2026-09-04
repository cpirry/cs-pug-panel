// format.js
// Purpose: Small formatting helpers (console line classification).

export function classifyLine(line) {
  const lower = line.toLowerCase();
  if (line.startsWith("> ")) return "log-cmd";
  if (lower.includes("error") || lower.includes("fail")) return "log-error";
  if (lower.includes("warn")) return "log-warn";
  return "";
}
