// config.js
// Purpose: Loads/saves the gamemode config editor and its saved presets.

import { configFileSelect, configEditor, configMsg, presetList } from "./dom.js";

export function renderPresets(presets) {
  presetList.innerHTML = "";
  if (!presets.length) {
    const empty = document.createElement("div");
    empty.className = "player-empty";
    empty.textContent = "No saved alternatives yet";
    presetList.appendChild(empty);
    return;
  }
  for (const name of presets) {
    const row = document.createElement("div");
    row.className = "preset-row-item";

    const label = document.createElement("span");
    label.className = "preset-name";
    label.textContent = name;

    const loadBtn = document.createElement("button");
    loadBtn.className = "btn btn-primary";
    loadBtn.type = "button";
    loadBtn.textContent = "Load";
    loadBtn.addEventListener("click", async () => {
      const file = configFileSelect.value;
      const res = await fetch(`/api/config/presets/${encodeURIComponent(file)}/${encodeURIComponent(name)}`);
      if (res.ok) {
        const data = await res.json();
        configEditor.value = data.content;
        configMsg.textContent = `Loaded "${name}" into the editor - click Save Config to apply`;
        configMsg.className = "msg ok";
      }
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "btn btn-danger";
    deleteBtn.type = "button";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", async () => {
      const res = await fetch("/api/config/presets/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file: configFileSelect.value, name }),
      });
      const data = await res.json();
      renderPresets(data.presets);
    });

    row.appendChild(label);
    row.appendChild(loadBtn);
    row.appendChild(deleteBtn);
    presetList.appendChild(row);
  }
}

export async function loadConfig(file) {
  const url = file ? `/api/config?file=${encodeURIComponent(file)}` : "/api/config";
  const res = await fetch(url);
  const data = await res.json();
  configFileSelect.innerHTML = "";
  for (const f of data.files) {
    const option = document.createElement("option");
    option.value = f;
    option.textContent = f;
    option.selected = f === data.file;
    configFileSelect.appendChild(option);
  }
  configEditor.value = data.content;
  renderPresets(data.presets);
}
