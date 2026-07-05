const DATA_PATHS = {
    tiles: "data/tiles.json",
    news: "data/news.json",
};

// Centrale instelling voor tekst en compacte dashboardaantallen.
const DASHBOARD_CONFIG = {
    greeting: "Goedemorgen Bob",
    headlineNewsLimit: 3,
    matchesToday: 2,
};

document.addEventListener("DOMContentLoaded", () => {
    const page = document.body.dataset.page;

    if (page === "dashboard") {
        initDashboard();
    }

    if (page === "news") {
        initNewsPage();
    }

    replaceIcons();
});

async function initDashboard() {
    const overview = document.getElementById("dashboard-overview");
    const newsList = document.getElementById("dashboard-news-list");
    const tilesGrid = document.getElementById("tiles-grid");
    const greeting = document.getElementById("dashboard-greeting");

    if (!overview || !newsList || !tilesGrid || !greeting) {
        return;
    }

    greeting.textContent = DASHBOARD_CONFIG.greeting;

    try {
        // Nieuws en apps worden tegelijk geladen om de homepage snel op te bouwen.
        const [newsItems, tiles] = await Promise.all([
            fetchJson(DATA_PATHS.news),
            fetchJson(DATA_PATHS.tiles),
        ]);

        const headlineItems = normalizeArray(newsItems).slice(0, DASHBOARD_CONFIG.headlineNewsLimit);

        renderOverview(overview, headlineItems.length, DASHBOARD_CONFIG.matchesToday);
        renderHeadlineNews(newsList, headlineItems);
        renderTiles(tilesGrid, tiles);
        replaceIcons();
    } catch (error) {
        console.error(error);
        renderStatus(overview, getLoadErrorMessage("Het dagoverzicht"));
        renderStatus(newsList, getLoadErrorMessage("De nieuwskaart"));
        renderStatus(tilesGrid, getLoadErrorMessage("De apps"));
    }
}

async function initNewsPage() {
    const newsList = document.getElementById("news-list");

    if (!newsList) {
        return;
    }

    try {
        const items = await fetchJson(DATA_PATHS.news);
        renderNews(newsList, items);
        replaceIcons();
    } catch (error) {
        console.error(error);
        renderStatus(newsList, getLoadErrorMessage("De nieuwsberichten"));
    }
}

async function fetchJson(path) {
    const response = await fetch(path, { cache: "no-store" });

    if (!response.ok) {
        throw new Error(`Kon ${path} niet laden (${response.status}).`);
    }

    return response.json();
}

function normalizeArray(value) {
    return Array.isArray(value) ? value : [];
}

function renderOverview(container, newsCount, matchesToday) {
    const overviewItems = [
        `<strong>${newsCount}</strong> ${pluralize(newsCount, "interessant nieuwsbericht", "interessante nieuwsberichten")}`,
        `<strong>${matchesToday}</strong> ${pluralize(matchesToday, "wedstrijd vandaag", "wedstrijden vandaag")}`,
    ];

    container.innerHTML = overviewItems
        .map((item) => `<div class="overview-pill">${item}</div>`)
        .join("");
}

function renderHeadlineNews(container, items) {
    container.innerHTML = "";

    if (!Array.isArray(items) || items.length === 0) {
        renderStatus(container, "Er zijn nog geen nieuwsberichten beschikbaar.");
        return;
    }

    const fragment = document.createDocumentFragment();

    items.forEach((item) => {
        fragment.appendChild(createHeadlineItem(item));
    });

    container.appendChild(fragment);
}

function renderTiles(container, tiles) {
    container.innerHTML = "";

    if (!Array.isArray(tiles) || tiles.length === 0) {
        renderStatus(container, "Er zijn nog geen apps beschikbaar.");
        return;
    }

    const fragment = document.createDocumentFragment();

    tiles.forEach((tile) => {
        fragment.appendChild(createAppCard(tile));
    });

    container.appendChild(fragment);
}

function renderNews(container, items) {
    container.innerHTML = "";

    if (!Array.isArray(items) || items.length === 0) {
        renderStatus(container, "Er zijn nog geen nieuwsberichten beschikbaar.");
        return;
    }

    const fragment = document.createDocumentFragment();

    items.forEach((item) => {
        fragment.appendChild(createNewsCard(item));
    });

    container.appendChild(fragment);
}

function renderStatus(container, message) {
    container.innerHTML = "";

    const card = document.createElement("div");
    card.className = "status-card";
    card.textContent = message;

    container.appendChild(card);
}

function createHeadlineItem(item) {
    const article = document.createElement("article");
    article.className = "headline-item";

    const link = document.createElement("a");
    link.className = "headline-link";
    link.href = item.url || item.link || "#";
    link.target = "_blank";
    link.rel = "noopener noreferrer";

    const title = document.createElement("h3");
    title.className = "headline-title";
    title.textContent = item.title || "Naamloos bericht";

    const meta = document.createElement("div");
    meta.className = "headline-meta";
    meta.append(
        createMetaText(item.source || "Onbekende bron"),
        createMetaSeparator(),
        createMetaText(formatDate(item.published || item.publishedAt, true)),
    );

    link.append(title, meta);
    article.appendChild(link);

    return article;
}

function createAppCard(tile) {
    const link = document.createElement("a");
    const isPlaceholder = Boolean(tile.comingSoon);

    link.className = "app-card";
    link.href = isPlaceholder ? "#" : tile.url || "#";
    link.setAttribute("aria-label", `${tile.title || "App"} - ${tile.description || ""}`);

    if (isPlaceholder) {
        link.classList.add("is-placeholder");
        link.addEventListener("click", (event) => event.preventDefault());
    }

    const iconBadge = document.createElement("span");
    iconBadge.className = "icon-badge app-icon";
    iconBadge.setAttribute("aria-hidden", "true");

    const icon = document.createElement("i");
    icon.dataset.lucide = tile.icon || "grid-2x2-plus";
    iconBadge.appendChild(icon);

    const textBlock = document.createElement("div");
    textBlock.className = "app-copy";

    const title = document.createElement("h3");
    title.className = "app-title";
    title.textContent = tile.title || "Naamloze app";

    const description = document.createElement("p");
    description.className = "app-description";
    description.textContent = tile.description || "Geen beschrijving beschikbaar.";

    textBlock.append(title, description);
    link.append(iconBadge, textBlock);

    return link;
}

function createNewsCard(item) {
    const article = document.createElement("article");
    article.className = "news-card";

    const title = document.createElement("h2");
    title.textContent = item.title || "Naamloos bericht";

    const meta = document.createElement("div");
    meta.className = "news-meta";
    meta.append(
        createMetaText(item.source || "Onbekende bron"),
        createMetaSeparator(),
        createMetaText(formatDate(item.published || item.publishedAt)),
    );

    const link = document.createElement("a");
    link.className = "news-link";
    link.href = item.url || item.link || "#";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Lees bericht";

    article.append(title, meta);

    if (item.summary) {
        const summary = document.createElement("p");
        summary.className = "news-summary";
        summary.textContent = item.summary;
        article.append(summary);
    }

    article.append(link);
    return article;
}

function createMetaText(text) {
    const span = document.createElement("span");
    span.textContent = text;
    return span;
}

function createMetaSeparator() {
    const separator = document.createElement("span");
    separator.className = "meta-dot";
    separator.textContent = "|";
    return separator;
}

function formatDate(value, compact = false) {
    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "Datum onbekend";
    }

    const options = compact
        ? { day: "numeric", month: "short" }
        : { day: "numeric", month: "long", year: "numeric" };

    return new Intl.DateTimeFormat("nl-NL", options).format(date);
}

function pluralize(count, singular, plural) {
    return count === 1 ? singular : plural;
}

function getLoadErrorMessage(subject) {
    if (window.location.protocol === "file:") {
        return `${subject} konden niet worden geladen via file://. Open BobOS via GitHub Pages of een lokale server.`;
    }

    return `${subject} konden niet worden geladen.`;
}

function replaceIcons() {
    // Lucide vervangt de placeholders uit HTML en JSON door echte SVG-iconen.
    if (window.lucide && typeof window.lucide.createIcons === "function") {
        window.lucide.createIcons();
    }
}
