const CDN = "https://cdn.jsdelivr.net/gh/vupdivup/wubwub";
// Two published channels: reviewed prod (`assets`, one PR per release)
// and the force-pushed dev branch. Picked at runtime so the same static
// page serves both — `wubwub studio serve --dev` opens `?channel=dev`.
const CHANNELS = { prod: "assets", dev: "assets-dev" };
const channel = new URLSearchParams(location.search).get("channel") === "dev" ? "dev" : "prod";
const MANIFEST_URL = `${CDN}@${CHANNELS[channel]}/manifest.json`;

// Media base comes from the manifest, not from the channel: a prod
// manifest names the immutable `assets-vN` tag it was released as, so
// copied embed snippets keep working forever and only manifest.json
// ever needs a CDN purge. Dev has no tags and stays on its branch.
let BASE = `${CDN}@${CHANNELS[channel]}`;

import Fuse from "https://cdn.jsdelivr.net/npm/fuse.js@7.1.0/+esm";

const grid = document.getElementById("grid");
const empty = document.getElementById("empty");
const countEl = document.getElementById("count");
const searchInput = document.getElementById("search");
const searchClear = document.getElementById("search-clear");

const detail = document.getElementById("detail");
const detailImg = document.getElementById("detail-img");
const detailTitle = document.getElementById("detail-title");
const detailSub = document.getElementById("detail-sub");
const detailDownload = document.getElementById("detail-download");
const snippetCode = document.getElementById("snippet-code");
const snippetCopy = document.getElementById("snippet-copy");
const snippetTabs = document.querySelectorAll(".snippet__tabs button");
const themeToggle = document.getElementById("theme-toggle");
const yearEl = document.getElementById("year");
const intro = document.getElementById("intro");
const introOpen = document.getElementById("intro-open");

// Cap how many cards keep an animated GIF loaded at once; older
// hovers revert to their static preview so 500 items can't pin
// hundreds of full-size GIFs in memory at the same time.
const MAX_HOT_CARDS = 12;
const hotCards = [];

let currentAlbum = null;
let currentFormat = "markdown";
let openerCard = null;
let openerDeactivate = null;

// Safari throws SecurityError on any localStorage access when the user
// blocks all cookies -- not just on write, and not a null return. Every
// use here is a preference (theme, intro-seen), so losing storage should
// cost the preference and nothing else; unguarded, the throw in
// wireIntro() propagated out of the startup sequence below and init()
// never ran, leaving a permanently empty grid. Declared above the calls
// because wireIntro() reads it synchronously.
const store = {
  get(key) {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Preference just doesn't persist.
    }
  },
};

wirePressState();
wireThemeToggle();
wireIntro();
yearEl.textContent = new Date().getFullYear();
init();

// Controls whose press feedback is a colour flash. :active is supposed
// to carry it, but a mobile engine defers :active while it decides
// whether the touch is a scroll, so a quick tap ends before the state
// ever paints -- and with the page's colour states snapping (no
// transition, by design) there is nothing left to trail behind it.
// `.pressed` mirrors each control's :active declarations in style.css.
const PRESS_SELECTOR = ".icon-btn, .intro__dismiss, .detail__close, .search__clear";
const PRESS_MS = 120;

// contextmenu carries no pointer type, so remember what opened it.
let lastPointerType = "mouse";

function wirePressState() {
  // `-webkit-touch-callout` is Safari's alone: Chrome still opens its
  // image context menu on a long press, which ends the hold that is
  // playing the card's GIF. Cancelling the event is the only way to
  // refuse it. Gated on a touch press so a desktop right-click keeps
  // its menu (and its "save image as").
  document.addEventListener("contextmenu", (event) => {
    if (lastPointerType === "mouse") return;
    if (event.target.closest(".card")) event.preventDefault();
  });

  document.addEventListener("pointerdown", (event) => {
    lastPointerType = event.pointerType;

    // Mouse :active works as advertised; leave the desktop untouched.
    if (event.pointerType === "mouse") return;

    const control = event.target.closest(PRESS_SELECTOR);
    if (!control) return;

    control.classList.add("pressed");
    const start = performance.now();

    // Released on the window, not the control: a finger that drifts off
    // the button before lifting never fires pointerup on it, which
    // would leave the state stuck on. Held to a minimum beat so the
    // flash is visible even on a tap shorter than PRESS_MS.
    const release = () => {
      done();
      const held = performance.now() - start;
      setTimeout(() => control.classList.remove("pressed"), Math.max(0, PRESS_MS - held));
    };

    // A scroll that starts on a control fires pointercancel instead of
    // pointerup, and it isn't a press: drop the state immediately
    // rather than holding it for the minimum beat. Matters most for the
    // cards, since every drag down the grid starts on one.
    const cancel = () => {
      done();
      control.classList.remove("pressed");
    };

    // Only one of the two ever fires, so `once` would leave the other
    // registered for the life of the page -- one more per tap.
    const done = () => {
      removeEventListener("pointerup", release);
      removeEventListener("pointercancel", cancel);
    };

    addEventListener("pointerup", release);
    addEventListener("pointercancel", cancel);
  });
}

function wireThemeToggle() {
  themeToggle.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    document.documentElement.style.colorScheme = next;
    store.set("theme", next);
  });
}

function wireIntro() {
  intro.addEventListener("click", (event) => {
    if (event.target === intro) intro.close();
  });
  intro.addEventListener("close", () => {
    store.set("introSeen", "1");
  });

  // The intro auto-opens once, but it's also the only place the page
  // explains itself -- the header button lets a returning visitor get
  // it back instead of clearing storage.
  introOpen.addEventListener("click", () => intro.showModal());

  if (!store.get("introSeen")) {
    intro.showModal();
  }
}

async function init() {
  let albums = [];
  try {
    // `no-cache` = revalidate, not bypass: jsDelivr hands the manifest
    // out with max-age=604800, and that week-long *browser* copy is
    // beyond the reach of the CDN purge a release does, so a returning
    // visitor would sit on a stale album list long after the release
    // merged. Revalidating costs a conditional request that is a 304
    // whenever nothing changed. Media below stay hard-cached, which is
    // safe: their URLs carry the immutable release tag.
    const res = await fetch(MANIFEST_URL, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const manifest = await res.json();
    albums = manifest.albums ?? [];
    if (manifest.version) BASE = `${CDN}@${manifest.version}`;
  } catch (err) {
    countEl.hidden = false;
    countEl.textContent = "Failed to load manifest.";
    console.error("manifest load failed", err);
    return;
  }

  // Randomized so the grid isn't always fronted by the same handful of
  // albums; fresh on every load rather than pinned to a session, since
  // the page has no reload path a user hits often enough for that
  // stability to matter (search filters in place, the detail dialog
  // never navigates).
  shuffle(albums);

  const fuse = new Fuse(albums, {
    keys: [
      { name: "title", weight: 0.6 },
      { name: "artist", weight: 0.4 },
    ],
    threshold: 0.35,
    ignoreLocation: true,
  });

  const cards = renderGrid(albums);

  wireSearch(albums, fuse, cards);
  wireDialog();

  // Deep-linkable search: `?q=...` pre-filters on load.
  const initialQuery = new URLSearchParams(location.search).get("q") ?? "";
  if (initialQuery) {
    searchInput.value = initialQuery;
    applyFilter(initialQuery, albums, fuse, cards);
  }
}

// Fisher-Yates, in place.
function shuffle(items) {
  for (let i = items.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
}

function renderGrid(albums) {
  const fragment = document.createDocumentFragment();
  const cards = new Map();

  for (const album of albums) {
    const card = buildCard(album);
    fragment.appendChild(card);
    cards.set(album, card);
  }

  grid.appendChild(fragment);
  return cards;
}

function buildCard(album) {
  const previewUrl = `${BASE}/${album.preview}`;
  const gifUrl = `${BASE}/${album.gif}`;

  const card = document.createElement("button");
  card.type = "button";
  card.className = "card";
  card.setAttribute("aria-haspopup", "dialog");

  const media = document.createElement("div");
  media.className = "card__media";

  const img = document.createElement("img");
  // Belt to the CSS's braces: `-webkit-user-drag` is WebKit/Blink only,
  // and a drag started on the artwork cancels the hold that is playing
  // the GIF. The attribute covers the engines that ignore the property.
  img.draggable = false;
  img.loading = "lazy";
  img.decoding = "async";
  img.src = previewUrl;
  img.dataset.preview = previewUrl;
  img.alt = `${album.artist} — ${album.title}`;
  media.appendChild(img);

  const body = document.createElement("div");
  body.className = "card__body";
  body.innerHTML = `
    <div class="card__title"></div>
    <div class="card__artist muted"></div>
  `;
  body.querySelector(".card__title").textContent = album.title;
  body.querySelector(".card__artist").textContent = album.year
    ? `${album.artist} · ${album.year}`
    : album.artist;

  card.append(media, body);

  const activate = () => setHot(img, gifUrl);
  const deactivate = () => {
    // Clearing `want` first is what cancels a GIF still in flight: the
    // preload below only writes to an img that still asks for it.
    delete img.dataset.want;
    if (img.src === gifUrl) img.src = previewUrl;
  };

  card.addEventListener("pointerenter", activate);
  card.addEventListener("pointerleave", deactivate);
  // Only keyboard focus animates: closing the dialog restores focus to
  // the card that opened it, which otherwise left that card playing
  // with the pointer somewhere else entirely.
  card.addEventListener("focus", () => {
    if (card.matches(":focus-visible")) activate();
  });
  card.addEventListener("blur", deactivate);
  card.addEventListener("click", () => openDetail(album, gifUrl, card, deactivate));

  return card;
}

function setHot(img, gifUrl) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  // `dataset.want` records what this img should end up showing, and is
  // the only thing that authorizes the swap below. Assigning the GIF to
  // the live img directly would drop the decoded preview the same
  // frame, leaving the card a hole for the whole download -- GIFs are
  // the heavy asset, so that gap is seconds on a slow connection.
  // Loading it detached instead lets the preview hold the box until
  // there is a decoded frame to put in its place.
  img.dataset.want = gifUrl;

  const idx = hotCards.indexOf(img);
  if (idx !== -1) hotCards.splice(idx, 1);
  hotCards.push(img);

  while (hotCards.length > MAX_HOT_CARDS) {
    const stale = hotCards.shift();
    // Each img's own preview, not the just-activated card's — reverting
    // to the wrong URL here showed a stale card frozen on another
    // album's art after fast navigation evicted it.
    delete stale.dataset.want;
    if (stale.src !== stale.dataset.preview) stale.src = stale.dataset.preview;
  }

  if (img.src === gifUrl) return;
  loadThen(gifUrl, () => {
    if (img.dataset.want === gifUrl) img.src = gifUrl;
  });
}

// Pull a URL into the image cache without touching anything on screen,
// then hand control back. The callback is skipped on failure: leaving
// whatever is already displayed beats blanking to a broken image.
function loadThen(url, onReady) {
  const loader = new Image();
  loader.onload = onReady;
  loader.src = url;
}

function wireSearch(albums, fuse, cards) {
  let debounceHandle;

  function commit() {
    clearTimeout(debounceHandle);
    const value = searchInput.value;
    applyFilter(value, albums, fuse, cards);
    const params = new URLSearchParams(location.search);
    if (value) params.set("q", value);
    else params.delete("q");
    // `params.toString()`, not `params.size`: the latter only landed in
    // Safari 17, where it reads `undefined` and silently drops the query
    // string on every keystroke, so a search stopped being linkable.
    const query = params.toString();
    history.replaceState(null, "", `${location.pathname}${query ? `?${query}` : ""}`);
  }

  searchInput.addEventListener("input", () => {
    clearTimeout(debounceHandle);
    debounceHandle = setTimeout(commit, 120);
  });

  // Enter has nothing to submit (filtering is live), so on touch it means
  // "done typing": blur to drop the virtual keyboard off the grid. On a
  // mouse/desktop pointer blurring only costs the caret, so keep focus.
  searchInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    commit();
    if (matchMedia("(pointer: coarse)").matches) searchInput.blur();
  });

  // Replaces the UA's unstylable search-cancel button (see style.css), so
  // it clears immediately rather than through the input debounce. Focus
  // goes back to the field: the button hides itself once empty, and
  // clearing usually means retyping.
  searchClear.addEventListener("click", () => {
    searchInput.value = "";
    commit();
    searchInput.focus();
  });
}

function applyFilter(query, albums, fuse, cards) {
  const trimmed = query.trim();
  const matches = trimmed ? new Set(fuse.search(trimmed).map((r) => r.item)) : null;

  let visible = 0;
  for (const album of albums) {
    const show = !matches || matches.has(album);
    cards.get(album).classList.toggle("hidden", !show);
    if (show) visible += 1;
  }

  empty.hidden = visible !== 0;
  grid.hidden = visible === 0;
}

function wireDialog() {
  for (const tab of snippetTabs) {
    tab.addEventListener("click", () => {
      currentFormat = tab.dataset.format;
      for (const t of snippetTabs) t.setAttribute("aria-selected", String(t === tab));
      renderSnippet();
    });
  }

  snippetCopy.addEventListener("click", copySnippet);
  detailDownload.addEventListener("click", downloadGif);

  // The card that opened the dialog never sees `pointerleave` while the
  // modal covers it, so stop its GIF on close unless the pointer really
  // did come to rest on it.
  detail.addEventListener("close", () => {
    if (openerCard && !openerCard.matches(":hover")) openerDeactivate();
    openerCard = null;
    openerDeactivate = null;
  });

  // Native <dialog> only closes on backdrop click if the click target
  // is the dialog element itself (i.e. outside its content box).
  detail.addEventListener("click", (event) => {
    if (event.target === detail) detail.close();
  });
}

function openDetail(album, gifUrl, card, deactivate) {
  currentAlbum = { ...album, gifUrl };
  openerCard = card;
  openerDeactivate = deactivate;

  // Seed with the static frame the grid has almost certainly cached
  // already, then swap once the GIF has decoded. Assigning the GIF cold
  // left the dialog's 16:9 box empty for the length of the download,
  // with the artwork sitting in cache one URL away. Same `want` guard
  // as the cards: opening another album mid-download must win.
  detailImg.dataset.want = gifUrl;
  detailImg.src = `${BASE}/${album.preview}`;
  loadThen(gifUrl, () => {
    if (detailImg.dataset.want === gifUrl) detailImg.src = gifUrl;
  });
  detailImg.alt = `${album.artist} — ${album.title}`;
  detailTitle.textContent = album.title;
  detailSub.textContent = album.year ? `${album.artist} · ${album.year}` : album.artist;

  renderSnippet();
  detail.showModal();
}

function renderSnippet() {
  if (!currentAlbum) return;
  const { artist, title, gifUrl } = currentAlbum;
  const alt = `${artist} — ${title}`;

  const snippets = {
    markdown: `![${alt}](${gifUrl})`,
    html: `<img src="${gifUrl}" alt="${alt}" width="300">`,
    url: gifUrl,
  };

  snippetCode.textContent = snippets[currentFormat];
}

async function copySnippet() {
  const text = snippetCode.textContent;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Clipboard API needs a secure context; fall back for plain-HTTP
    // local dev servers.
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }

  flashDone(snippetCopy, "Copied", "Copy snippet");
}

// Swap a control to its check icon for a beat, then back.
function flashDone(button, doneLabel, idleLabel) {
  button.setAttribute("aria-label", doneLabel);
  button.classList.add("copied");
  setTimeout(() => {
    button.setAttribute("aria-label", idleLabel);
    button.classList.remove("copied");
  }, 1200);
}

async function downloadGif() {
  if (!currentAlbum) return;
  const { artist, title, gifUrl } = currentAlbum;
  const filename = `${slug(artist)}-${slug(title)}.gif`;

  try {
    // The media is cross-origin (jsDelivr), and `download` on a
    // cross-origin <a> is ignored -- the browser navigates to the GIF
    // instead of saving it. Fetching to a same-origin blob URL first
    // is what makes the attribute stick, and jsDelivr sends CORS
    // headers, so the fetch itself is allowed.
    const response = await fetch(gifUrl);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const url = URL.createObjectURL(await response.blob());

    // In the document and revoked a turn later, both for WebKit: it
    // honours `download` only on a connected anchor, and revoking the
    // blob URL in the same task as the click cancels the save before it
    // starts. Chromium tolerates the detached, immediately-revoked
    // version, which is why it worked there.
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {
      link.remove();
      URL.revokeObjectURL(url);
    }, 0);

    flashDone(detailDownload, "Downloaded", "Download GIF");
  } catch {
    // Blocked fetch or offline: hand the file to the browser directly.
    // Loses the filename, but still gets the user the GIF.
    window.open(gifUrl, "_blank", "noopener");
  }
}

function slug(text) {
  return text
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "cover";
}
