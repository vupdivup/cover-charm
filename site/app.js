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

// Cap how many cards keep an animated GIF loaded at once; older
// hovers revert to their static preview so 500 items can't pin
// hundreds of full-size GIFs in memory at the same time.
const MAX_HOT_CARDS = 12;
const hotCards = [];

let currentAlbum = null;
let currentFormat = "markdown";
let openerCard = null;
let openerDeactivate = null;

wireThemeToggle();
wireIntro();
yearEl.textContent = new Date().getFullYear();
init();

function wireThemeToggle() {
  themeToggle.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    document.documentElement.style.colorScheme = next;
    localStorage.setItem("theme", next);
  });
}

function wireIntro() {
  intro.addEventListener("click", (event) => {
    if (event.target === intro) intro.close();
  });
  intro.addEventListener("close", () => {
    localStorage.setItem("introSeen", "1");
  });

  if (!localStorage.getItem("introSeen")) {
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

  albums.sort((a, b) => {
    return (
      a.artist.localeCompare(b.artist) ||
      (a.year ?? 0) - (b.year ?? 0) ||
      a.title.localeCompare(b.title)
    );
  });

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
  if (img.src !== gifUrl) img.src = gifUrl;

  const idx = hotCards.indexOf(img);
  if (idx !== -1) hotCards.splice(idx, 1);
  hotCards.push(img);

  while (hotCards.length > MAX_HOT_CARDS) {
    const stale = hotCards.shift();
    // Each img's own preview, not the just-activated card's — reverting
    // to the wrong URL here showed a stale card frozen on another
    // album's art after fast navigation evicted it.
    if (stale.src !== stale.dataset.preview) stale.src = stale.dataset.preview;
  }
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
    history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}`);
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

  detailImg.src = gifUrl;
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

    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);

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
