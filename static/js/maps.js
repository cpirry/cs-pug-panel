// maps.js
// Purpose: Renders map tiles and reads the currently selected map.
//
// Rendered with Preact + htm (same approach as roster.js) so the host's map pick can be synced
// to everyone else on every poll without reloading/flickering thumbnails on each re-render - the
// same flicker class that maps.js used to suffer from when it rebuilt via innerHTML = "".

import { h, render } from "https://esm.sh/preact@10.19.3";
import htm from "https://esm.sh/htm@3.1.1";
import { mapsCoreEl, mapsExtraEl, mapsWorkshopEl } from "./dom.js";
import { activateSubtab } from "./subtabs.js";

const html = htm.bind(h);

// Thumbnail loading is imperative (cycling through file extensions until one loads), so it's
// wired once per <img> DOM node via a ref rather than expressed declaratively - re-renders that
// reuse the same node (same key, nothing else changed) never re-trigger a fresh image load.
function wireLocalThumb(map) {
  return (el) => {
    if (!el || el.dataset.wired) return;
    el.dataset.wired = "1";
    const extensions = ["jpg", "png", "webp"];
    let i = 0;
    el.addEventListener("error", () => {
      if (i < extensions.length) {
        el.src = `/map-images/${map}.${extensions[i]}`;
        i++;
      } else {
        el.closest(".map-tile-thumb").classList.add("map-tile-fallback");
        el.remove();
      }
    });
    el.src = `/map-images/${map}.${extensions[i]}`;
    i++;
  };
}

function wireWorkshopThumb(thumbnail) {
  return (el) => {
    if (!el || el.dataset.wired) return;
    el.dataset.wired = "1";
    el.addEventListener("error", () => {
      el.closest(".map-tile-thumb").classList.add("map-tile-fallback");
      el.remove();
    });
    el.src = thumbnail;
  };
}

function MapTile({ map, selected, disabled }) {
  return html`
    <label class="map-tile">
      <input type="radio" name="map" value=${map} checked=${map === selected} disabled=${disabled} />
      <span class="map-tile-thumb"><img alt="" loading="lazy" ref=${wireLocalThumb(map)} /></span>
      <span class="map-tile-caption">${map}</span>
    </label>
  `;
}

function WorkshopMapTile({ map, selected, disabled }) {
  return html`
    <label class="map-tile">
      <input type="radio" name="map" value=${map.id} checked=${map.id === selected} disabled=${disabled} />
      <span class="map-tile-thumb${map.thumbnail ? "" : " map-tile-fallback"}">
        ${map.thumbnail ? html`<img alt="" loading="lazy" ref=${wireWorkshopThumb(map.thumbnail)} />` : null}
      </span>
      <span class="map-tile-caption">${map.title}</span>
    </label>
  `;
}

export function renderMapList(container, maps, selected, disabled) {
  if (!maps.length) {
    render(html`<div class="player-empty">No maps in this category</div>`, container);
    return;
  }
  render(
    maps.map((map) => html`<${MapTile} key=${map} map=${map} selected=${selected} disabled=${disabled} />`),
    container
  );
}

export function renderWorkshopMaps(container, maps, selected, disabled) {
  if (!maps.length) {
    render(html`<div class="player-empty">No workshop maps added yet</div>`, container);
    return;
  }
  render(
    maps.map((map) => html`<${WorkshopMapTile} key=${map.id} map=${map} selected=${selected} disabled=${disabled} />`),
    container
  );
}

export function renderMaps(maps, selected, disabled = false) {
  renderMapList(mapsCoreEl, maps.core, selected, disabled);
  renderMapList(mapsExtraEl, maps.extra, selected, disabled);
  renderWorkshopMaps(mapsWorkshopEl, maps.workshop, selected, disabled);
}

export function activateMapTabFor(selected, maps) {
  let target = "core";
  if (maps.extra.includes(selected)) target = "extra";
  else if (maps.workshop.some((m) => m.id === selected)) target = "workshop";
  activateSubtab(mapsCoreEl.closest(".subtab-group"), target);
}

export function selectedMap() {
  const checked = document.querySelector("input[name=map]:checked");
  return checked ? checked.value : "";
}

export function selectedMapSource() {
  const checked = document.querySelector("input[name=map]:checked");
  return checked && mapsWorkshopEl.contains(checked) ? "workshop" : "local";
}
