// maps.js
// Purpose: Renders map tiles and reads the currently selected map.
//
// Rendered with Preact + htm (same approach as roster.js) so the host's map pick can be synced
// to everyone else on every poll without reloading/flickering thumbnails on each re-render - the
// same flicker class that maps.js used to suffer from when it rebuilt via innerHTML = "".

import { h, render } from "https://esm.sh/preact@10.19.3";
import htm from "https://esm.sh/htm@3.1.1";
import { mapsCoreEl, mapsWingmanEl, mapsExtraEl, mapsWorkshopEl } from "./dom.js";
import { activateSubtab } from "./subtabs.js";

const html = htm.bind(h);

// selectedMap()/selectedMapSource() prefer whatever's actually checked in the DOM (the freshest
// pick, possibly not yet confirmed by the server) and fall back to the last server-confirmed
// value otherwise - needed for a random pick, which deliberately never checks a real radio (see
// RandomMapTile below), so nothing would be :checked for them to read.
let lastSelectedMap = "";
let lastSelectedMapSource = "local";

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

// Not a real map - a trigger tile that picks one of this tab's maps at random and reports it via
// a "randommap" event (handled in main.js), rather than ever checking a real radio: that would
// reveal which map got picked, both visually (the tile would light up via :has(input:checked))
// and structurally (once Preact has rendered a radio as unchecked, it won't write `checked = true`
// back to the DOM on a later render if a native click set it outside Preact's knowledge - same
// class of bug as the roster's disabled-checkbox issue). No thumbnail - just a shuffle glyph.
function RandomMapTile({ maps, disabled, active }) {
  const pickRandom = (e) => {
    if (disabled || !maps.length) return;
    const pick = maps[Math.floor(Math.random() * maps.length)];
    e.currentTarget.dispatchEvent(new CustomEvent("randommap", { bubbles: true, detail: { map: pick } }));
  };
  return html`
    <button
      type="button"
      class="map-tile map-tile-random${active ? " is-active" : ""}"
      disabled=${disabled}
      onClick=${pickRandom}
    >
      <span class="map-tile-thumb map-tile-random-thumb">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="16 3 21 3 21 8"></polyline>
          <line x1="4" y1="20" x2="21" y2="3"></line>
          <polyline points="21 16 21 21 16 21"></polyline>
          <line x1="15" y1="15" x2="21" y2="21"></line>
          <line x1="4" y1="4" x2="9" y2="9"></line>
        </svg>
      </span>
      <span class="map-tile-caption">Random</span>
    </button>
  `;
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

export function renderMapList(container, maps, selected, disabled, randomActive = false) {
  if (!maps.length) {
    render(html`<div class="player-empty">No maps in this category</div>`, container);
    return;
  }
  render(
    [
      ...maps.map(
        (map) =>
          html`<${MapTile} key=${map} map=${map} selected=${randomActive ? null : selected} disabled=${disabled} />`
      ),
      html`<${RandomMapTile} key="__random__" maps=${maps} disabled=${disabled} active=${randomActive} />`,
    ],
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

export function renderMaps(maps, selected, selectedSource, disabled = false, isRandomPick = false) {
  lastSelectedMap = selected;
  lastSelectedMapSource = selectedSource;
  renderMapList(mapsCoreEl, maps.core, selected, disabled, isRandomPick && maps.core.includes(selected));
  renderMapList(mapsWingmanEl, maps.wingman, selected, disabled, isRandomPick && maps.wingman.includes(selected));
  renderMapList(mapsExtraEl, maps.extra, selected, disabled, isRandomPick && maps.extra.includes(selected));
  renderWorkshopMaps(mapsWorkshopEl, maps.workshop, selected, disabled);
}

export function activateMapTabFor(selected, maps) {
  let target = "core";
  if (maps.wingman.includes(selected)) target = "wingman";
  else if (maps.extra.includes(selected)) target = "extra";
  else if (maps.workshop.some((m) => m.id === selected)) target = "workshop";
  activateSubtab(mapsCoreEl.closest(".subtab-group"), target);
}

export function selectedMap() {
  const checked = document.querySelector("input[name=map]:checked");
  return checked ? checked.value : lastSelectedMap;
}

export function selectedMapSource() {
  const checked = document.querySelector("input[name=map]:checked");
  if (checked) return mapsWorkshopEl.contains(checked) ? "workshop" : "local";
  return lastSelectedMapSource;
}
