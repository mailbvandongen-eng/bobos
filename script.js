const DATA_PATHS = {
    tiles: "data/tiles.json",
    news: "data/news.json",
};

const ASSET_PATHS = {
    logos: {
        dark: "assets/bobos-logo-dark.svg",
        light: "assets/bobos-logo-light.svg",
    },
};

const STORAGE_KEYS = {
    theme: "bobos-theme",
};

const DASHBOARD_CONFIG = {
    homepageNewsLimit: 3,
    newsSummaryLength: 120,
};

const CATEGORY_ICON_MAP = {
    algemeen: "newspaper",
    archeologie: "newspaper",
    darts: "trophy",
    "formule 1": "flag",
    gadgets: "cpu",
    ruimte: "telescope",
    sport: "trophy",
    technologie: "cpu",
    voetbal: "goal",
    wetenschap: "atom",
    ruimtevaart: "telescope",
    sterrenkunde: "telescope",
    natuurkunde: "atom",
    scheikunde: "atom",
    musea: "landmark",
};

document.addEventListener("DOMContentLoaded", () => {
    initTheme();

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
    const newsList = document.getElementById("dashboard-news-list");
    const tilesGrid = document.getElementById("tiles-grid");
    const greeting = document.getElementById("dashboard-greeting");

    if (!newsList || !tilesGrid || !greeting) {
        return;
    }

    greeting.textContent = getGreetingByLocalTime();

    try {
        const [newsItems, tiles] = await Promise.all([
            fetchJson(DATA_PATHS.news),
            fetchJson(DATA_PATHS.tiles),
        ]);

        const normalizedNews = normalizeArray(newsItems);
        const headlineItems = pickHomepageItems(normalizedNews, DASHBOARD_CONFIG.homepageNewsLimit);

        renderCompactNews(newsList, headlineItems, false);
        renderTiles(tilesGrid, tiles);
        replaceIcons();
    } catch (error) {
        console.error(error);
        renderStatus(newsList, getLoadErrorMessage("Het nieuws"));
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
        renderCompactNews(newsList, items, true);
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

function initTheme() {
    const savedTheme = getStoredTheme();
    applyTheme(savedTheme);
    bindThemeToggles();
}

function getStoredTheme() {
    try {
        const savedTheme = localStorage.getItem(STORAGE_KEYS.theme);
        return savedTheme === "light" ? "light" : "dark";
    } catch (error) {
        console.warn("Kon thema niet uit localStorage lezen.", error);
        return "dark";
    }
}

function applyTheme(theme) {
    const nextTheme = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = nextTheme;
    updateThemeLogos(nextTheme);
    updateThemeMetaColor(nextTheme);
    updateThemeToggleButtons(nextTheme);
}

function bindThemeToggles() {
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
        if (button.dataset.bound === "true") {
            return;
        }

        button.dataset.bound = "true";
        button.addEventListener("click", () => {
            const currentTheme = document.documentElement.dataset.theme === "light" ? "light" : "dark";
            const nextTheme = currentTheme === "dark" ? "light" : "dark";

            try {
                localStorage.setItem(STORAGE_KEYS.theme, nextTheme);
            } catch (error) {
                console.warn("Kon thema niet opslaan in localStorage.", error);
            }

            applyTheme(nextTheme);
        });
    });
}

function updateThemeToggleButtons(theme) {
    const nextModeLabel = theme === "dark" ? "Licht thema" : "Donker thema";
    const nextModeIcon = theme === "dark" ? "sun" : "moon";

    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
        button.setAttribute("aria-pressed", String(theme === "light"));
        button.setAttribute("aria-label", nextModeLabel);
        button.title = nextModeLabel;

        const icon = button.querySelector("[data-theme-icon]");

        if (icon) {
            icon.dataset.lucide = nextModeIcon;
        }
    });

    replaceIcons();
}

function updateThemeMetaColor(theme) {
    const themeColor = theme === "light" ? "#edf3f7" : "#091017";
    const metaThemeColor = document.querySelector('meta[name="theme-color"]');

    if (metaThemeColor) {
        metaThemeColor.setAttribute("content", themeColor);
    }
}

function updateThemeLogos(theme) {
    const source = theme === "light" ? ASSET_PATHS.logos.light : ASSET_PATHS.logos.dark;

    document.querySelectorAll("[data-bobos-logo]").forEach((image) => {
        if (image.getAttribute("src") !== source) {
            image.setAttribute("src", source);
        }
    });
}

function getGreetingByLocalTime(now = new Date()) {
    const hour = now.getHours();

    if (hour >= 5 && hour <= 11) {
        return "Goedemorgen Bob";
    }

    if (hour >= 12 && hour <= 17) {
        return "Goedemiddag Bob";
    }

    if (hour >= 18 && hour <= 23) {
        return "Goedenavond Bob";
    }

    return "Goedenacht Bob";
}

function pickHomepageItems(items, limit) {
    const selected = [];
    const usedSources = new Set();

    for (const item of normalizeArray(items)) {
        const sourceKey = String(item.source || "").trim().toLowerCase();

        if (!sourceKey || usedSources.has(sourceKey)) {
            continue;
        }

        selected.push(item);
        usedSources.add(sourceKey);

        if (selected.length === limit) {
            return selected;
        }
    }

    for (const item of normalizeArray(items)) {
        if (selected.includes(item)) {
            continue;
        }

        selected.push(item);

        if (selected.length === limit) {
            break;
        }
    }

    return selected;
}

function renderCompactNews(container, items, showSummary) {
    container.innerHTML = "";

    if (!Array.isArray(items) || items.length === 0) {
        renderStatus(container, "Er zijn nog geen nieuwsberichten beschikbaar.");
        return;
    }

    const fragment = document.createDocumentFragment();

    items.forEach((item) => {
        fragment.appendChild(createNewsItem(item, showSummary));
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

function renderStatus(container, message) {
    container.innerHTML = "";

    const card = document.createElement("div");
    card.className = "status-card";
    card.textContent = message;

    container.appendChild(card);
}

function createNewsItem(item, showSummary) {
    const link = document.createElement("a");
    link.className = "news-item";
    link.href = item.url || "#";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.setAttribute("aria-label", `${item.title || "Nieuws"} openen in een nieuwe tab`);

    const media = createNewsMedia(item);
    const body = document.createElement("div");
    body.className = "news-item-body";

    const title = document.createElement("h3");
    title.className = "news-item-title";
    title.textContent = item.title || "Naamloos bericht";

    const meta = document.createElement("div");
    meta.className = "news-meta";
    meta.append(
        createMetaText(item.source || "Onbekende bron"),
        createMetaSeparator(),
        createMetaText(formatDate(item.published || item.publishedAt, showSummary ? false : true)),
    );

    body.append(title, meta);

    if (showSummary) {
        const summaryText = truncateText(item.summary || "", DASHBOARD_CONFIG.newsSummaryLength);

        if (summaryText) {
            const summary = document.createElement("p");
            summary.className = "news-item-summary";
            summary.textContent = summaryText;
            body.append(summary);
        }
    }

    link.append(media, body);
    return link;
}

function createNewsMedia(item) {
    const imageUrl = String(item.image || "").trim();

    if (imageUrl) {
        const image = document.createElement("img");
        image.className = "news-thumb";
        image.src = imageUrl;
        image.alt = "";
        image.loading = "lazy";
        image.referrerPolicy = "no-referrer";
        image.addEventListener("error", () => {
            image.replaceWith(createIconFrame(item.category));
            replaceIcons();
        }, { once: true });
        return image;
    }

    return createIconFrame(item.category);
}

function createIconFrame(category) {
    const frame = document.createElement("span");
    frame.className = "news-icon-frame";
    frame.setAttribute("aria-hidden", "true");

    const icon = document.createElement("i");
    icon.dataset.lucide = resolveIconName(iconNameForCategory(category));
    frame.appendChild(icon);

    return frame;
}

function iconNameForCategory(category) {
    const normalized = normalizeCategory(category);

    if (normalized.includes("formule 1")) {
        return "flag";
    }

    if (normalized.includes("voetbal")) {
        return "goal";
    }

    if (normalized.includes("manchester united")) {
        return "goal";
    }

    if (normalized.includes("wetenschap")) {
        return "atom";
    }

    if (normalized.includes("ruimte") || normalized.includes("sterrenkunde")) {
        return "telescope";
    }

    if (normalized.includes("natuurkunde") || normalized.includes("scheikunde")) {
        return "atom";
    }

    if (normalized.includes("musea")) {
        return "landmark";
    }

    if (normalized.includes("gadget") || normalized.includes("technologie")) {
        return "cpu";
    }

    if (normalized.includes("sport")) {
        return "trophy";
    }

    return CATEGORY_ICON_MAP[normalized] || "newspaper";
}

function normalizeCategory(value) {
    return String(value || "algemeen").trim().toLowerCase();
}

function resolveIconName(iconName) {
    const icons = window.lucide && window.lucide.icons;

    if (icons && icons[iconName]) {
        return iconName;
    }

    return fallbackIconName(iconName);
}

function fallbackIconName(iconName) {
    const fallbacks = {
        atom: "cpu",
        goal: "trophy",
        landmark: "newspaper",
        telescope: "newspaper",
    };

    return fallbacks[iconName] || "newspaper";
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
    iconBadge.className = "app-icon";
    iconBadge.setAttribute("aria-hidden", "true");

    const icon = document.createElement("i");
    icon.dataset.lucide = resolveIconName(tile.icon || "grid-2x2-plus");
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

function truncateText(value, maxLength) {
    const text = String(value || "").trim();

    if (!text) {
        return "";
    }

    if (text.length <= maxLength) {
        return text;
    }

    return `${text.slice(0, maxLength).trimEnd()}...`;
}

function getLoadErrorMessage(subject) {
    if (window.location.protocol === "file:") {
        return `${subject} konden niet worden geladen via file://. Open BobOS via GitHub Pages of een lokale server.`;
    }

    return `${subject} konden niet worden geladen.`;
}

function replaceIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
        window.lucide.createIcons();
    }
}
