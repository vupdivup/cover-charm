// Single constant tying the site to a published asset channel. Swap to
// an `assets` (tagged/reviewed) branch here once one exists — see
// packages/album-store/src/album_store/README.md.
const BASE = "https://cdn.jsdelivr.net/gh/vupdivup/cover-charm@assets-dev";

import Fuse from "https://cdn.jsdelivr.net/npm/fuse.js@7.1.0/+esm";

const grid = document.getElementById("grid");
const empty = document.getElementById("empty");
const countEl = document.getElementById("count");
const searchInput = document.getElementById("search");

const detail = document.getElementById("detail");
const detailImg = document.getElementById("detail-img");
const detailTitle = document.getElementById("detail-title");
const detailSub = document.getElementById("detail-sub");
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
    const res = await fetch("./data/manifest.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const manifest = await res.json();
    albums = manifest.albums ?? [];
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
  card.addEventListener("focus", activate);
  card.addEventListener("blur", deactivate);
  card.addEventListener("click", () => openDetail(album, gifUrl));

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
  searchInput.addEventListener("input", () => {
    clearTimeout(debounceHandle);
    const value = searchInput.value;
    debounceHandle = setTimeout(() => {
      applyFilter(value, albums, fuse, cards);
      const params = new URLSearchParams(location.search);
      if (value) params.set("q", value);
      else params.delete("q");
      history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}`);
    }, 120);
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

  // Native <dialog> only closes on backdrop click if the click target
  // is the dialog element itself (i.e. outside its content box).
  detail.addEventListener("click", (event) => {
    if (event.target === detail) detail.close();
  });
}

function openDetail(album, gifUrl) {
  currentAlbum = { ...album, gifUrl };

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

  snippetCopy.setAttribute("aria-label", "Copied");
  snippetCopy.classList.add("copied");
  setTimeout(() => {
    snippetCopy.setAttribute("aria-label", "Copy snippet");
    snippetCopy.classList.remove("copied");
  }, 1200);
}
