// mods.js
// Purpose: Renders the Mods toggle list.

import { modsEl } from "./dom.js";

export function renderMods(mods) {
  modsEl.innerHTML = "";
  for (const mod of mods) {
    const row = document.createElement("div");
    row.className = "toggle-row";

    const name = document.createElement("span");
    name.textContent = mod.name;

    const switchLabel = document.createElement("label");
    switchLabel.className = "switch";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = mod.enabled;
    input.addEventListener("change", async () => {
      input.disabled = true;
      await fetch("/api/mods/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: mod.name }),
      });
      input.disabled = false;
    });
    const slider = document.createElement("span");
    slider.className = "slider";
    switchLabel.appendChild(input);
    switchLabel.appendChild(slider);

    row.appendChild(name);
    row.appendChild(switchLabel);
    modsEl.appendChild(row);
  }
}
