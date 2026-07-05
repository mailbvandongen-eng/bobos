const APP_META = {
    name: "BobOS",
    version: "0.2",
};

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
    dashboardNewsLimit: 3,
    detailNewsLimit: 50,
    compactSummaryLength: 120,
    compactDomainLimit: 3,
};

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
    const greeting = document.getElementById("dashboard-greeting");
    const newsSlot = document.getElementById("dashboard-news-domain");
    const domainGrid = document.getElementById("dashboard-domain-grid");

    if (!greeting || !newsSlot || !domainGrid) {
        return;
    }

    greeting.textContent = getGreetingByLocalTime();

    try {
        const tiles = normalizeArray(await fetchJson(DATA_PATHS.tiles));
        const domains = await Promise.all(tiles.map(loadDashboardDomain));
        const newsDomain = domains.find((domain) => domain.tile.key === "news");
        const otherDomains = domains.filter((domain) => domain.tile.key !== "news");

        renderFeaturedDomain(newsSlot, newsDomain);
        renderDomainGrid(domainGrid, otherDomains);
        replaceIcons();
    } catch (error) {
        console.error(error);
        renderStatus(newsSlot, getLoadErrorMessage("Het dashboard"));
        renderStatus(domainGrid, getLoadErrorMessage("De domeintegels"));
    }
}

async function initNewsPage() {
    const newsList = document.getElementById("news-list");

    if (!newsList) {
        return;
    }

    try {
        const items = normalizeArray(await fetchJson(DATA_PATHS.news));
        renderNewsDetailList(newsList, items);
        replaceIcons();
    } catch (error) {
        console.error(error);
        renderStatus(newsList, getLoadErrorMessage("De nieuwsberichten"));
    }
}

async function loadDashboardDomain(tile) {
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

function renderFeaturedDomain(container, domain) {
    container.innerHTML = "";

    if (!domain) {
        renderStatus(container, "De nieuwstegel is niet beschikbaar.");
        return;
    }

    container.appendChild(createDomainCard(domain, true));
}

function renderDomainGrid(container, domains) {
    container.innerHTML = "";

    if (!Array.isArray(domains) || domains.length === 0) {
        renderStatus(container, "Er zijn nog geen domeintegels beschikbaar.");
        return;
    }

    const fragment = document.createDocumentFragment();

    domains.forEach((domain) => {
        fragment.appendChild(createDomainCard(domain, false));
    });

    container.appendChild(fragment);
}

function renderNewsDetailList(container, items) {
    container.innerHTML = "";

    if (!Array.isArray(items) || items.length === 0) {
        renderStatus(container, "Er zijn nog geen nieuwsberichten beschikbaar.");
        return;
    }

    container.appendChild(
        createNewsList(items, DASHBOARD_CONFIG.detailNewsLimit, true, "news-detail-list")
    );
}

function createDomainCard(domain, featured) {
    const card = document.createElement("section");
    card.className = featured ? "domain-card domain-card--featured" : "domain-card";

    const header = document.createElement("div");
    header.className = "domain-card-header";

    const titleRow = document.createElement("div");
    titleRow.className = "domain-card-title-row";

    const iconFrame = document.createElement("span");
    iconFrame.className = "domain-card-icon";
    iconFrame.setAttribute("aria-hidden", "true");

    const icon = document.createElement("i");
    icon.dataset.lucide = resolveIconName(domain.tile.icon || "newspaper");
    iconFrame.appendChild(icon);

    const copy = document.createElement("div");
    copy.className = "domain-card-copy";

    const title = document.createElement(featured ? "h2" : "h3");
    title.textContent = domain.tile.title || "Domein";

    const status = document.createElement("p");
    status.className = "domain-card-status";
    status.textContent = getDomainStatus(domain);

    copy.append(title, status);
    titleRow.append(iconFrame, copy);
    header.append(titleRow);

    const action = createActionLink(domain.tile);
    if (action) {
        header.append(action);
    }

    const body = document.createElement("div");
    body.className = "domain-card-body";
    body.appendChild(createDomainBody(domain));

    card.append(header, body);
    return card;
}

function createActionLink(tile) {
    const targetUrl = String(tile.target_url || "").trim();

    if (!targetUrl) {
        return null;
    }

    const link = document.createElement("a");
    link.className = "domain-card-action";
    link.href = targetUrl;
    link.textContent = tile.target_label || "Open";

    if (tile.external) {
        link.target = "_blank";
        link.rel = "noopener noreferrer";
    }

    return link;
}

function createDomainBody(domain) {
    switch (domain.tile.key) {
        case "news":
            return createNewsList(
                normalizeArray(domain.payload),
                DASHBOARD_CONFIG.dashboardNewsLimit,
                false,
                "news-tile-list"
            );
        case "sport":
            return createSportList(domain.payload);
        case "detectie":
        case "vissen":
            return createConditionList(domain.payload);
        default:
            return createInlineStatus("Dit domein heeft nog geen weergave.");
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

function createSportList(payload) {
    const items = normalizeArray(payload && payload.items);

    if (items.length === 0) {
        return createInlineStatus("Nog geen sportitems beschikbaar.");
    }

    const list = document.createElement("div");
    list.className = "domain-list";

    items.slice(0, DASHBOARD_CONFIG.compactDomainLimit).forEach((item) => {
        const row = document.createElement("a");
        row.className = "domain-list-item";
        row.href = item.url || payload.url || "#";
        row.target = "_blank";
        row.rel = "noopener noreferrer";

        const leading = document.createElement("span");
        leading.className = "domain-list-leading";
        leading.textContent = item.time || "--:--";

        const text = document.createElement("div");
        text.className = "domain-list-main";

        const title = document.createElement("p");
        title.className = "domain-list-title";
        title.textContent = item.title || "Sportitem";

        const meta = document.createElement("p");
        meta.className = "domain-list-meta";
        meta.textContent = item.category || "Sport";

        text.append(title, meta);
        row.append(leading, text);
        list.append(row);
    });

    return list;
}

function createConditionList(payload) {
    const items = normalizeArray(payload && payload.items);

    if (items.length === 0) {
        return createInlineStatus("Nog geen statusregels beschikbaar.");
    }

    const list = document.createElement("div");
    list.className = "value-list";

    items.slice(0, DASHBOARD_CONFIG.compactDomainLimit).forEach((item) => {
        const row = document.createElement("div");
        row.className = "value-list-item";

        const label = document.createElement("span");
        label.className = "value-list-label";
        label.textContent = item.label || "Label";

        const value = document.createElement("span");
        value.className = "value-list-value";
        value.textContent = item.value || "-";

        row.append(label, value);
        list.append(row);
    });

    return list;
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
