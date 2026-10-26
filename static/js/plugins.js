// plugins.js
// Purpose: Renders the Admin > Plugins tiles (installed vs latest version, per-plugin update
// button) from /api/plugins, polling while the tab is open so update progress shows live.
//
// Rendered with Preact + htm like maps.js, so the 5s refresh doesn't rebuild (and flicker) the
// whole grid. That refresh only reads the panel's cached release info; GitHub is only asked
// again via the Check for updates button.

import { h, render } from "https://esm.sh/preact@10.19.3";
import htm from "https://esm.sh/htm@3.1.1";
import { pluginGridEl, pluginsHintEl, pluginsRefreshBtn } from "./dom.js";
import { isHost } from "./state.js";

const html = htm.bind(h);
const POLL_MS = 5000;

let pollTimer = null;
let lastData = null;
let pendingNotice = "";

function buttonFor(plugin, host) {
  const job = plugin.job;
  if (job && job.state === "updating") return { label: "Updating...", disabled: true };
  if (!plugin.canUpdate) return { label: "No update source", disabled: true };
  if (!plugin.isInstalled) {
    return { label: plugin.latest ? `Install ${plugin.latest}` : "Install", disabled: !host || !plugin.latest };
  }
  if (!host) return { label: plugin.updateAvailable ? "Update available" : "Up to date", disabled: true };
  if (plugin.updateAvailable) {
    return { label: plugin.latest ? `Update to ${plugin.latest}` : "Update", disabled: false };
  }
  // Already current - still allow a reinstall (e.g. to repair a broken install).
  return { label: "Reinstall", disabled: !plugin.latest, secondary: true };
}

function statusLine(plugin) {
  const job = plugin.job;
  if (job) {
    const cls = job.state === "error" ? "err" : job.state === "done" ? "ok" : "";
    return html`<span class="plugin-status msg ${cls}">${job.message}</span>`;
  }
  if (plugin.error) return html`<span class="plugin-status msg err">${plugin.error}</span>`;
  if (plugin.note && plugin.updateAvailable) return html`<span class="plugin-status">${plugin.note}</span>`;
  return null;
}

function PluginTile({ plugin, host, onUpdate, onUninstall }) {
  const btn = buttonFor(plugin, host);
  const busy = plugin.job && plugin.job.state === "updating";
  const tileClass = [
    "plugin-tile",
    plugin.updateAvailable && plugin.canUpdate ? "has-update" : "",
    plugin.disabled || !plugin.isInstalled ? "is-disabled" : "",
  ].join(" ");
  return html`
    <div class=${tileClass}>
      <div class="plugin-tile-head">
        <span class="plugin-kind">${plugin.kind}</span>
        ${plugin.disabled ? html`<span class="plugin-badge">Disabled</span>` : null}
      </div>
      <div class="plugin-name">${plugin.name}</div>
      <dl class="plugin-versions">
        <dt>Installed</dt>
        <dd>${plugin.isInstalled ? plugin.installed || "Unknown" : "Not installed"}</dd>
        <dt>Latest</dt>
        <dd>${plugin.canUpdate ? plugin.latest || "-" : "-"}</dd>
      </dl>
      ${plugin.source ? html`<span class="plugin-source">${plugin.source}</span>` : null}
      ${statusLine(plugin)}
      <button
        type="button"
        class="btn ${btn.secondary ? "plugin-btn-secondary" : "btn-primary"} plugin-update-btn"
        disabled=${btn.disabled}
        onClick=${() => onUpdate(plugin)}
      >
        ${btn.label}
      </button>
      ${plugin.canUninstall && host
        ? html`<button
            type="button"
            class="btn plugin-uninstall-btn"
            disabled=${busy}
            onClick=${() => onUninstall(plugin)}
          >
            Uninstall
          </button>`
        : null}
    </div>
  `;
}

function renderPlugins(data) {
  lastData = data;
  const host = isHost();
  const updating = data.plugins.some((p) => p.job && p.job.state === "updating");
  const outdated = data.plugins.filter((p) => p.canUpdate && p.updateAvailable).length;
  // A one-off result (e.g. an uninstall) shown until the next manual action replaces it.
  const notice = pendingNotice;
  pluginsHintEl.textContent = [
    notice,
    formatCheckedAt(data.checkedAt),
    outdated ? `${outdated} update${outdated === 1 ? "" : "s"} available.` : "Everything is up to date.",
    data.serverRunning ? "The server is running - updates take effect the next time it starts." : "",
    host ? "" : "Only the lobby host can update plugins.",
  ]
    .filter(Boolean)
    .join(" ");
  pluginsRefreshBtn.disabled = updating;
  render(
    data.plugins.map(
      (p) =>
        html`<${PluginTile}
          key=${p.id}
          plugin=${p}
          host=${host}
          onUpdate=${startUpdate}
          onUninstall=${uninstallPlugin}
        />`
    ),
    pluginGridEl
  );
}

// Polling only re-reads the panel's cached release info - it never triggers a new check.
export async function loadPlugins() {
  const res = await fetch("/api/plugins");
  if (!res.ok) return;
  renderPlugins(await res.json());
}

function formatCheckedAt(epochSeconds) {
  if (!epochSeconds) return "Not checked yet.";
  const d = new Date(epochSeconds * 1000);
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const sameDay = d.toDateString() === new Date().toDateString();
  return `Last checked ${sameDay ? "today" : d.toLocaleDateString()} at ${time}.`;
}

async function uninstallPlugin(plugin) {
  const ok = window.confirm(
    `Uninstall ${plugin.name}? Its files are backed up first; its config files are left in place.`
  );
  if (!ok) return;
  const res = await fetch("/api/plugins/uninstall", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: plugin.id }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    window.alert(data.error || "Couldn't uninstall that plugin");
    return;
  }
  pendingNotice = data.message || `Uninstalled ${plugin.name}.`;
  await loadPlugins();
}

async function startUpdate(plugin) {
  pendingNotice = "";
  const label = !plugin.isInstalled
    ? `Install ${plugin.name} ${plugin.latest}?`
    : plugin.updateAvailable
    ? `Update ${plugin.name} to ${plugin.latest}?`
    : `Reinstall ${plugin.name} ${plugin.latest}?`;
  if (!window.confirm(`${label} Current files are backed up first; existing configs are kept.`)) return;
  const res = await fetch("/api/plugins/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: plugin.id }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    window.alert(data.error || "Couldn't start the update");
  }
  await loadPlugins();
}

export function startPluginPolling() {
  if (pollTimer) return;
  if (lastData) renderPlugins(lastData);
  loadPlugins();
  pollTimer = setInterval(loadPlugins, POLL_MS);
}

export function stopPluginPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
}

pluginsRefreshBtn.addEventListener("click", async () => {
  pluginsRefreshBtn.disabled = true;
  pendingNotice = "";
  pluginsHintEl.textContent = "Checking for updates...";
  const res = await fetch("/api/plugins/check", { method: "POST" });
  const data = await res.json().catch(() => ({}));
  if (res.ok) {
    renderPlugins(data);
  } else {
    pendingNotice = data.error || "Couldn't check for updates.";
    await loadPlugins();
  }
  pluginsRefreshBtn.disabled = false;
});
