// roster.js
// Purpose: Renders player-roster slots sized to the selected team size, seeding lobby members into slots.
//
// PROTOTYPE: rendered with Preact + htm instead of manual DOM manipulation (innerHTML = "" +
// rebuild), to see whether a diffing approach is worth adopting project-wide. No build step -
// both libraries are loaded as ES modules straight from a CDN. renderRoster() keeps the exact
// same signature as the vanilla version, so main.js/state.js need no changes to use this.
//
// Compare against roster.vanilla.js.bak (the version this replaced) - same behavior, same CSS
// classes/data attributes (main.js's drag/ready/kick event delegation doesn't care who created
// the DOM nodes), but every render now diffs against the previous tree instead of tearing it
// down, which is what was causing the flicker/reset bugs in maps.js before that got fixed
// separately by just not re-rendering on every poll.

import { h, render } from "https://esm.sh/preact@10.19.3";
import htm from "https://esm.sh/htm@3.1.1";
import { rosterCtEl, rosterTEl } from "./dom.js";

const html = htm.bind(h);

let currentLobby = null;
let currentAuth = null;

function RosterSlot({ member, hostId, selfId, isHost, canMove }) {
  if (!member) {
    return html`
      <div class="roster-slot" data-steam-id="">
        <div class="roster-slot-avatar"></div>
        <div class="roster-slot-name">Empty Slot</div>
      </div>
    `;
  }

  const draggable = canMove(member.steamId);
  const isSelf = member.steamId === selfId;

  return html`
    <div
      class="roster-slot${draggable ? " roster-slot-draggable" : ""}"
      data-steam-id=${member.steamId}
      draggable=${draggable}
    >
      <img class="roster-slot-avatar" alt="" src=${member.avatar || undefined} />
      <div class="roster-slot-name${member.ready ? " is-ready" : ""}">
        ${member.displayName}${member.steamId === hostId ? " (host)" : ""}
      </div>
      <label class="roster-slot-ready">
        <input type="checkbox" class="roster-ready-checkbox" checked=${!!member.ready} disabled=${!isSelf} />
        Ready
      </label>
      ${isHost && !isSelf
        ? html`<button type="button" class="roster-slot-kick" data-steam-id=${member.steamId} aria-label="Kick player">×</button>`
        : null}
    </div>
  `;
}

function renderRosterSide(container, count, members, canMove, hostId, selfId, isHost) {
  const slots = Array.from(
    { length: count },
    (_, i) =>
      html`<${RosterSlot}
        key=${i}
        member=${members[i] || null}
        hostId=${hostId}
        selfId=${selfId}
        isHost=${isHost}
        canMove=${canMove}
      />`
  );
  render(slots, container);
}

export function renderRoster(teamSize, lobby = currentLobby, auth = currentAuth) {
  currentLobby = lobby;
  currentAuth = auth;
  const members = lobby && lobby.members ? lobby.members : [];
  const hostId = lobby ? lobby.host : null;
  const isHost = !!(lobby && auth && lobby.host === auth.steamId);
  const selfId = auth ? auth.steamId : null;
  // A readied-up player can't be dragged (or dragged onto) - see move_member()'s docstring for why.
  const readyMap = new Map(members.map((m) => [m.steamId, !!m.ready]));
  const canMove = (steamId) =>
    !!lobby && lobby.state === "waiting" && !readyMap.get(steamId) && (isHost || steamId === selfId);
  const tMembers = members.filter((m) => (m.team || "t") === "t");
  const ctMembers = members.filter((m) => (m.team || "t") === "ct");
  renderRosterSide(rosterTEl, teamSize, tMembers, canMove, hostId, selfId, isHost);
  renderRosterSide(rosterCtEl, teamSize, ctMembers, canMove, hostId, selfId, isHost);
}
