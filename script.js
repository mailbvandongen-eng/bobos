const APP_META = {
    name: "BobOS",
    version: "0.2",
};

const DATA_PATHS = {
    news: "data/news.json",
    sport: "data/sport.json",
    detectie: "data/detectie.json",
    vissen: "data/vissen.json",
};

const STORAGE_KEYS = {
    theme: "bobos-theme",
};

const DASHBOARD_CONFIG = {
    dashboardNewsLimit: 5,
    detailNewsLimit: 50,
    compactSummaryLength: 120,
    compactDomainLimit: 3,
};

const DASHBOARD_AGENT_TILES = [
    {
        key: "sport",
        title: "Sport",
        icon: "trophy",
        status_fallback: "Sport op TV vandaag",
        target_url: "https://mailbvandongen-eng.github.io/sport-op-tv/",
        data_path: DATA_PATHS.sport,
        external: true,
        footer_label: "Open Sport op TV",
    },
    {
        key: "detectie",
        title: "Detectie",
        icon: "map",
        status_fallback: "Maandagcondities",
        target_url: "https://mailbvandongen-eng.github.io/detect/",
        data_path: DATA_PATHS.detectie,
        external: true,
        footer_label: "Open Detectie",
    },
    {
        key: "vissen",
        title: "Vissen",
        icon: "fish",
        status_fallback: "Viskansen vandaag",
        target_url: "https://mailbvandongen-eng.github.io/visapp/",
        data_path: DATA_PATHS.vissen,
        external: true,
        footer_label: "Open Visapp",
    },
    {
        key: "meer",
        title: "Meer...",
        icon: "grid-2x2-plus",
        status_fallback: "Ruimte voor toekomstige agents",
        placeholder_lines: [
            "Nieuwe tegel",
            "Toekomstige agent",
            "Nog leeg",
        ],
    },
];

const CATEGORY_ICON_MAP = {
    algemeen: "newspaper",
    archeologie: "newspaper",
    darts: "trophy",
    detectie: "map",
    gadgets: "cpu",
    "formule 1": "flag",
    musea: "landmark",
    natuurkunde: "atom",
    ruimte: "telescope",
    ruimtevaart: "telescope",
    scheikunde: "atom",
    sport: "trophy",
    sterrenkunde: "telescope",
    technologie: "cpu",
    vissen: "fish",
    voetbal: "goal",
    wetenschap: "atom",
};

document.addEventListener("DOMContentLoaded", () => {
    syncAppVersion();
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

    if (!newsList) {
        return;
    }

    try {
        const normalizedNews = normalizeArray(await fetchJson(DATA_PATHS.news));
        const headlineItems = pickHomepageItems(normalizedNews, DASHBOARD_CONFIG.dashboardNewsLimit);

        renderCompactNews(newsList, headlineItems, false);
        replaceIcons();
    } catch (error) {
        console.error(error);
        renderStatus(newsList, getLoadErrorMessage("Het nieuws"));
    }
}

async function initNewsPage() {
    const newsList = document.getElementById("news-list");

    if (!newsList) {
        return;
    }

    try {
        const items = normalizeArray(await fetchJson(DATA_PATHS.news));
        renderCompactNews(newsList, items, true);
        replaceIcons();
    } catch (error) {
        console.error(error);
        renderStatus(newsList, getLoadErrorMessage("De nieuwsberichten"));
    }
}

async function loadDashboardDomain(tile) {
    if (!tile.data_path) {
        return { tile, payload: null, error: null };
    }

    try {
        const payload = await fetchJson(tile.data_path);
        return { tile, payload, error: null };
    } catch (error) {
        console.error(`Kon ${tile.data_path} niet laden.`, error);
        return { tile, payload: null, error };
    }
}

async function fetchJson(path) {
    const response = await fetch(path, { cache: "no-store" });

    if (!response.ok) {
        throw new Error(`Kon ${path} niet laden (${response.status}).`);
    }

    return response.json();
}

function syncAppVersion() {
    document.querySelectorAll("[data-app-version]").forEach((node) => {
        node.textContent = `Versie ${APP_META.version}`;
    });
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

    container.appendChild(
        createNewsList(
            items,
            showSummary ? DASHBOARD_CONFIG.detailNewsLimit : DASHBOARD_CONFIG.dashboardNewsLimit,
            showSummary,
            showSummary ? "news-detail-list" : "news-compact-list"
        )
    );
}

function renderDashboardTiles(container, domains) {
    container.innerHTML = "";

    if (!Array.isArray(domains) || domains.length === 0) {
        renderStatus(container, "Er zijn nog geen agenttegels beschikbaar.");
        return;
    }

    const fragment = document.createDocumentFragment();

    domains.forEach((domain) => {
        fragment.appendChild(createAgentTile(domain));
    });

    container.appendChild(fragment);
}

function createAgentTile(domain) {
    const targetUrl = String(domain.tile.target_url || "").trim();
    const tile = document.createElement(targetUrl ? "a" : "section");
    tile.className = "agent-tile";
    tile.dataset.domain = domain.tile.key || "agent";

    if (domain.tile.key) {
        tile.classList.add(`agent-tile--${domain.tile.key}`);
        tile.id = `agent-${domain.tile.key}`;
    }

    if (targetUrl) {
        tile.classList.add("agent-tile--link");
        tile.href = targetUrl;

        if (domain.tile.external) {
            tile.target = "_blank";
            tile.rel = "noopener noreferrer";
        }
    } else {
        tile.classList.add("agent-tile--placeholder");
    }

    const header = document.createElement("div");
    header.className = "agent-tile-header";

    const top = document.createElement("div");
    top.className = "agent-tile-top";

    const iconFrame = document.createElement("span");
    iconFrame.className = "agent-tile-icon";
    iconFrame.setAttribute("aria-hidden", "true");

    const icon = document.createElement("i");
    icon.dataset.lucide = resolveIconName(domain.tile.icon || "newspaper");
    iconFrame.appendChild(icon);

    const copy = document.createElement("div");
    copy.className = "agent-tile-copy";

    const title = document.createElement("h3");
    title.textContent = domain.tile.title || "Agent";

    const status = document.createElement("p");
    status.className = "agent-tile-status";
    status.textContent = getDomainStatus(domain);

    copy.append(title, status);
    top.append(iconFrame, copy);
    header.append(top);

    const body = document.createElement("div");
    body.className = "agent-tile-body";
    body.appendChild(createAgentTileBody(domain));

    tile.append(header, body);

    if (targetUrl && domain.tile.footer_label) {
        const footer = document.createElement("span");
        footer.className = "agent-tile-footer";
        footer.textContent = domain.tile.footer_label;
        tile.append(footer);
    }

    return tile;
}

function createAgentTileBody(domain) {
    if (domain.error) {
        return createAgentFallback("Data tijdelijk niet beschikbaar.");
    }

    switch (domain.tile.key) {
        case "sport":
            return createSportMiniList(domain.payload);
        case "detectie":
        case "vissen":
            return createConditionMiniList(domain.payload);
        default:
            return createPlaceholderMiniList(domain.tile.placeholder_lines);
    }
}

function createNewsList(items, limit, showSummary, className) {
    if (!Array.isArray(items) || items.length === 0) {
        return createInlineStatus("Nog geen items beschikbaar.");
    }

    const list = document.createElement("div");
    list.className = className;

    items.slice(0, limit).forEach((item) => {
        list.appendChild(createNewsItem(item, showSummary));
    });

    return list;
}

function createNewsItem(item, showSummary) {
    const link = document.createElement("a");
    link.className = showSummary ? "news-item news-item--detail" : "news-item";
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
        createMetaText(formatDate(item.published || item.publishedAt, !showSummary)),
    );

    body.append(title, meta);

    if (showSummary) {
        const summaryText = truncateText(item.summary || "", DASHBOARD_CONFIG.compactSummaryLength);

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

function createSportMiniList(payload) {
    const items = normalizeArray(payload && payload.items);

    if (items.length === 0) {
        return createAgentFallback("Nog geen sportitems beschikbaar.");
    }

    const list = document.createElement("div");
    list.className = "agent-mini-list";

    items.slice(0, DASHBOARD_CONFIG.compactDomainLimit).forEach((item) => {
        const row = document.createElement("div");
        row.className = "agent-mini-row agent-mini-row--sport";

        const leading = document.createElement("span");
        leading.className = "agent-mini-leading";
        leading.textContent = item.time || "--:--";

        const text = document.createElement("div");
        text.className = "agent-mini-copy";

        const title = document.createElement("span");
        title.className = "agent-mini-title";
        title.textContent = item.title || "Sportitem";

        const meta = document.createElement("span");
        meta.className = "agent-mini-meta";
        meta.textContent = item.category || "Sport";

        text.append(title, meta);
        row.append(leading, text);
        list.append(row);
    });

    return list;
}

function createConditionMiniList(payload) {
    const items = normalizeArray(payload && payload.items);

    if (items.length === 0) {
        return createAgentFallback("Nog geen statusregels beschikbaar.");
    }

    const list = document.createElement("div");
    list.className = "agent-mini-list";

    items.slice(0, DASHBOARD_CONFIG.compactDomainLimit).forEach((item) => {
        const row = document.createElement("div");
        row.className = "agent-mini-row";

        const label = document.createElement("span");
        label.className = "agent-mini-label";
        label.textContent = `${item.label || "Label"}:`;

        const value = document.createElement("span");
        value.className = "agent-mini-value";
        value.textContent = item.value || "-";

        row.append(label, value);
        list.append(row);
    });

    return list;
}

function createPlaceholderMiniList(lines) {
    const list = document.createElement("div");
    list.className = "agent-mini-list";

    normalizeArray(lines).slice(0, DASHBOARD_CONFIG.compactDomainLimit).forEach((line) => {
        const row = document.createElement("div");
        row.className = "agent-mini-row agent-mini-row--placeholder";
        row.textContent = line;
        list.append(row);
    });

    if (!list.childElementCount) {
        return createAgentFallback("Nog geen inhoud beschikbaar.");
    }

    return list;
}

function createAgentFallback(message) {
    const note = document.createElement("div");
    note.className = "agent-mini-empty";
    note.textContent = message;
    return note;
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

function getDomainStatus(domain) {
    if (domain.tile.key === "news") {
        return getNewsStatus(normalizeArray(domain.payload));
    }

    if (domain.tile.key === "detectie") {
        const baseStatus = domain.payload && typeof domain.payload.status === "string" && domain.payload.status.trim()
            ? domain.payload.status.trim()
            : (domain.tile.status_fallback || "Nog niet bijgewerkt");
        const score = Number(domain.payload && domain.payload.score);

        if (Number.isFinite(score) && score > 0) {
            return `${baseStatus} - Zoekconditie: ${Math.round(score)}/5`;
        }

        return baseStatus;
    }

    if (domain.payload && typeof domain.payload.status === "string" && domain.payload.status.trim()) {
        return domain.payload.status.trim();
    }

    return domain.tile.status_fallback || "Nog niet bijgewerkt";
}

function getNewsStatus(items) {
    if (!Array.isArray(items) || items.length === 0) {
        return "Nog geen nieuws";
    }

    const latestItemDate = new Date(items[0].published || items[0].publishedAt || "");

    if (Number.isNaN(latestItemDate.getTime())) {
        return "Laatste update onbekend";
    }

    if (isSameLocalDay(latestItemDate, new Date())) {
        return "Bijgewerkt vandaag";
    }

    return `Laatste update ${formatDate(latestItemDate.toISOString(), true)}`;
}

function isSameLocalDay(left, right) {
    return (
        left.getFullYear() === right.getFullYear() &&
        left.getMonth() === right.getMonth() &&
        left.getDate() === right.getDate()
    );
}

function iconNameForCategory(category) {
    const normalized = normalizeCategory(category);

    if (normalized.includes("formule 1")) {
        return "flag";
    }

    if (normalized.includes("voetbal") || normalized.includes("manchester united")) {
        return "goal";
    }

    if (normalized.includes("wetenschap") || normalized.includes("natuurkunde") || normalized.includes("scheikunde")) {
        return "atom";
    }

    if (normalized.includes("ruimte") || normalized.includes("sterrenkunde")) {
        return "telescope";
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

    if (normalized.includes("detectie")) {
        return "map";
    }

    if (normalized.includes("vissen")) {
        return "fish";
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

function renderStatus(container, message) {
    container.innerHTML = "";
    container.appendChild(createInlineStatus(message));
}

function createInlineStatus(message) {
    const card = document.createElement("div");
    card.className = "status-card";
    card.textContent = message;
    return card;
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
