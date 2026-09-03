// maps.js
// Purpose: Renders map tiles and reads the currently selected map.

import { mapsCoreEl, mapsExtraEl, mapsWorkshopEl } from "./dom.js";

export function renderMapList(container, maps, selected) {
  container.innerHTML = "";
  if (!maps.length) {
    const empty = document.createElement("div");
    empty.className = "player-empty";
    empty.textContent = "No maps in this category";
    container.appendChild(empty);
    return;
  }
  for (const map of maps) {
    const label = document.createElement("label");
    label.className = "map-tile";

    const input = document.createElement("input");
    input.type = "radio";
    input.name = "map";
    input.value = map;
    input.checked = map === selected;
    label.appendChild(input);

    const thumb = document.createElement("span");
    thumb.className = "map-tile-thumb";
    const img = document.createElement("img");
    img.alt = "";
    img.loading = "lazy";
    const extensions = ["jpg", "png", "webp"];
    let i = 0;
    img.addEventListener("error", () => {
      if (i < extensions.length) {
        img.src = `/map-images/${map}.${extensions[i]}`;
        i++;
      } else {
        img.remove();
        thumb.classList.add("map-tile-fallback");
      }
    });
    img.src = `/map-images/${map}.${extensions[i]}`;
    i++;
    thumb.appendChild(img);
    label.appendChild(thumb);

    const caption = document.createElement("span");
    caption.className = "map-tile-caption";
    caption.textContent = map;
    label.appendChild(caption);

    container.appendChild(label);
  }
}

export function renderWorkshopMaps(container, maps, selected) {
  container.innerHTML = "";
  if (!maps.length) {
    const empty = document.createElement("div");
    empty.className = "player-empty";
    empty.textContent = "No workshop maps added yet";
    container.appendChild(empty);
    return;
  }
  for (const map of maps) {
    const label = document.createElement("label");
    label.className = "map-tile";

    const input = document.createElement("input");
    input.type = "radio";
    input.name = "map";
    input.value = map.id;
    input.checked = map.id === selected;
    label.appendChild(input);

    const thumb = document.createElement("span");
    thumb.className = "map-tile-thumb";
    if (map.thumbnail) {
      const img = document.createElement("img");
      img.alt = "";
      img.loading = "lazy";
      img.src = map.thumbnail;
      img.addEventListener("error", () => {
        img.remove();
        thumb.classList.add("map-tile-fallback");
      });
      thumb.appendChild(img);
    } else {
      thumb.classList.add("map-tile-fallback");
    }
    label.appendChild(thumb);

    const caption = document.createElement("span");
    caption.className = "map-tile-caption";
    caption.textContent = map.title;
    label.appendChild(caption);

    container.appendChild(label);
  }
}

export function renderMaps(maps, selected) {
  renderMapList(mapsCoreEl, maps.core, selected);
  renderMapList(mapsExtraEl, maps.extra, selected);
  renderWorkshopMaps(mapsWorkshopEl, maps.workshop, selected);
}

export function activateMapTabFor(selected, maps) {
  let target = "core";
  if (maps.extra.includes(selected)) target = "extra";
  else if (maps.workshop.some((m) => m.id === selected)) target = "workshop";
  document.querySelectorAll(".subtab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.maptab === target);
  });
  document.querySelectorAll(".subtab-panel").forEach((p) => {
    p.hidden = p.dataset.mappanel !== target;
  });
}

export function selectedMap() {
  const checked = document.querySelector("input[name=map]:checked");
  return checked ? checked.value : "";
}

export function selectedMapSource() {
  const checked = document.querySelector("input[name=map]:checked");
  return checked && mapsWorkshopEl.contains(checked) ? "workshop" : "local";
}
