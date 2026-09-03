// auth.js
// Purpose: Renders the Steam login/account area in the top bar.

import { steamAccount, steamAvatar, steamLoginLink, steamName } from "./dom.js";

export function renderAuth(auth) {
  if (auth && auth.loggedIn) {
    steamLoginLink.hidden = true;
    steamAccount.hidden = false;
    steamName.textContent = auth.displayName || auth.steamId;
    if (auth.avatar) {
      steamAvatar.src = auth.avatar;
      steamAvatar.hidden = false;
    } else {
      steamAvatar.hidden = true;
    }
  } else {
    steamLoginLink.hidden = false;
    steamAccount.hidden = true;
  }
}
