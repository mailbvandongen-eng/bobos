const APP_META = {
    name: "BobOS",
    version: "0.3",
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
    detailNewsLimit: 12,
    compactSummaryLength: 120,
    compactSourceLimit: 6,
};

const NAVIGATION_LINKS = {
    sport: {
        href: "sport.html",
    },
    detectie: {
        href: "detectie.html",
    },
    vissen: {
        href: "vissen.html",
    },
    steentijd: {
        href: "https://steentijd-app.pages.dev/",
        external: true,
    },
    meer: {
        href: "meer.html",
    },
};

const AGENT_PAGE_CONFIGS = {
    news: {
        dataPath: DATA_PATHS.news,
        defaultOpenUrl: "https://news.google.com/home?hl=nl&gl=NL&ceid=NL:nl",
        defaultOpenLabel: "Open Google Nieuws",
        scoreLabel: "",
    },
    sport: {
        dataPath: DATA_PATHS.sport,
        defaultOpenUrl: "https://mailbvandongen-eng.github.io/sport-op-tv/",
        defaultOpenLabel: "Open Sport op TV",
        scoreLabel: "",
    },
    detectie: {
        dataPath: DATA_PATHS.detectie,
        defaultOpenUrl: "https://mailbvandongen-eng.github.io/detect/",
        defaultOpenLabel: "Open Detectorapp",
        scoreLabel: "Zoekconditie",
    },
    vissen: {
        dataPath: DATA_PATHS.vissen,
        defaultOpenUrl: "https://mailbvandongen-eng.github.io/visapp/",
        defaultOpenLabel: "Open Visapp",
        scoreLabel: "Visscore",
    },
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
    hydrateNavigationLinks();

    const page = document.body.dataset.page || "";

    if (page === "dashboard") {
        initDashboard();
    }

    if (page.startsWith("agent-")) {
        initAgentPage(page.replace("agent-", ""));
    }

    replaceIcons();
});

async function initDashboard() {
    const newsList = document.getElementById("dashboard-news-list");

    if (!newsList) {
        return;
    }

    try {
        const items = normalizeArray(await fetchJson(DATA_PATHS.news));
        const headlineItems = pickHomepageItems(items, DASHBOARD_CONFIG.dashboardNewsLimit);
        renderCompactNews(newsList, headlineItems, false);
        replaceIcons();
    } catch (error) {
        console.error(error);
        renderStatus(newsList, getLoadErrorMessage("Het nieuws"));
    }
}

async function initAgentPage(agentKey) {
    const panel = document.querySelector("[data-agent-key]");
    const config = AGENT_PAGE_CONFIGS[agentKey];

    if (!panel || !config) {
        return;
    }

    try {
        const rawPayload = await fetchJson(config.dataPath);
        const model = buildAgentPageModel(agentKey, rawPayload, config);
        renderAgentPage(panel, model, config);
        replaceIcons();
    } catch (error) {
        console.error(error);
        renderAgentPageError(panel, agentKey, config);
    }
}

function buildAgentPageModel(agentKey, rawPayload, config) {
    switch (agentKey) {
        case "news":
            return buildNewsPageModel(rawPayload, config);
        case "sport":
            return buildSportPageModel(rawPayload, config);
        case "detectie":
            return buildDetectiePageModel(rawPayload, config);
        case "vissen":
            return buildVissenPageModel(rawPayload, config);
        default:
            throw new Error(`Onbekende agentpagina: ${agentKey}`);
    }
}

function buildNewsPageModel(rawPayload, config) {
    const items = normalizeArray(rawPayload);
    const visibleItems = items.slice(0, DASHBOARD_CONFIG.detailNewsLimit);
    const latestItem = visibleItems[0] || null;
    const sourceSummary = summarizeNewsSources(items);
    const categorySummary = uniqueTextValues(items.map((item) => item.category)).slice(0, 5);

    return {
        status: latestItem
            ? `${items.length} nieuwsbericht(en) geladen`
            : "Geen nieuws beschikbaar",
        score: null,
        scoreLabel: config.scoreLabel,
        itemMode: "news",
        items: visibleItems,
        analysis: [
            latestItem
                ? `Laatste bronupdate: ${formatDate(latestItem.published || latestItem.publishedAt, false)}.`
                : "Er is nog geen recente update beschikbaar.",
            sourceSummary.length
                ? `${sourceSummary.length} Nederlandstalige bron(nen) actief in deze selectie.`
                : "Er zijn nog geen actieve bronnen in de selectie.",
            categorySummary.length
                ? `Categorieen in beeld: ${categorySummary.join(", ")}.`
                : "Er zijn nog geen categorieen in beeld.",
        ],
        advice: [
            "Gebruik deze selectie voor snelle orientatie en open daarna de originele bron voor de volledige context.",
            "De homepage blijft bewust compact; deze pagina toont meer berichten tegelijk zonder volledige artikelen op te slaan.",
        ],
        sources: sourceSummary,
        openUrl: latestItem && latestItem.url ? latestItem.url : config.defaultOpenUrl,
        openLabel: latestItem && latestItem.url ? "Open laatste bron" : config.defaultOpenLabel,
        openExternal: true,
    };
}

function buildSportPageModel(rawPayload, config) {
    const payload = isPlainObject(rawPayload) ? rawPayload : {};
    const items = normalizeArray(payload.items).map((item) => ({
        time: String(item.time || "--:--").trim(),
        title: String(item.title || "Sportitem").trim(),
        category: String(item.category || "Sport").trim(),
        source: String(item.source || "").trim(),
    }));
    const categories = uniqueTextValues(items.map((item) => item.category));
    const sourceSummary = normalizeSourceItems(payload.sources, [
        { label: "OpenFootball", value: "Voetbalbron" },
        { label: "ESPN", value: "Scoreboard" },
        { label: "OpenF1", value: "Sessies" },
        { label: "PDC", value: "Dartsfixtures" },
    ]);

    return {
        status: String(payload.status || "Geen sport gevonden voor vandaag").trim(),
        score: null,
        scoreLabel: config.scoreLabel,
        itemMode: "sport",
        items,
        analysis: normalizeStringArray(payload.details, [
            items.length
                ? `${items.length} sportitem(s) gevonden voor vandaag.`
                : "Er zijn geen voetbal-, darts- of F1-items gevonden voor vandaag.",
            categories.length
                ? `Categorieen vandaag: ${categories.join(", ")}.`
                : "Er zijn geen sportcategorieen beschikbaar.",
            "Bronnen die tijdelijk niet reageren worden overgeslagen.",
        ]),
        advice: items.length
            ? [
                "Gebruik SportAgent als snelle voorselectie voordat je de volledige Sport op TV-pagina opent.",
                "Open Sport op TV voor alle zenders, extra wedstrijden en eventuele latere aanvullingen.",
            ]
            : [
                "Later opnieuw proberen kan nieuwe wedstrijden, darts of F1-sessies opleveren.",
                "Alleen voetbal, darts en Formule 1 tellen mee voor deze selectie.",
            ],
        sources: sourceSummary,
        openUrl: String(payload.url || config.defaultOpenUrl).trim() || config.defaultOpenUrl,
        openLabel: config.defaultOpenLabel,
        openExternal: true,
    };
}

function buildDetectiePageModel(rawPayload, config) {
    const payload = isPlainObject(rawPayload) ? rawPayload : {};
    const items = normalizeConditionItems(payload.items);
    const context = isPlainObject(payload.context) ? payload.context : {};
    const rainfall = safeNumber(context.rain_last_7_days_mm);
    const mondayDate = String(context.monday_date || "").trim();
    const mondayPrecipitation = safeNumber(context.monday_precipitation_mm);
    const sourceSummary = normalizeSourceItems(payload.sources, [
        { label: "Open-Meteo", value: "Weerdata" },
        { label: "Detectieregels", value: "Lokale regelset" },
    ]);

    const contextLine = rainfall !== null && mondayDate
        ? `Referentie: ${rainfall.toFixed(1)} mm regen in de afgelopen 7 dagen, maandag ${mondayDate} circa ${formatNumericValue(mondayPrecipitation, "mm")}.`
        : "";

    return {
        status: String(payload.status || "Maandagadvies").trim(),
        score: clampScore(payload.score),
        scoreLabel: config.scoreLabel,
        itemMode: "condition",
        items,
        analysis: compactLines(
            normalizeStringArray(payload.details),
            contextLine ? [contextLine] : []
        ),
        advice: buildAdviceLinesFromItems(items, {
            "Beste keuze": "Beste terrein",
            "Vermijd": "Vermijd",
            "Tip": "Tip",
        }),
        sources: sourceSummary,
        openUrl: String(payload.url || config.defaultOpenUrl).trim() || config.defaultOpenUrl,
        openLabel: config.defaultOpenLabel,
        openExternal: true,
    };
}

function buildVissenPageModel(rawPayload, config) {
    const payload = isPlainObject(rawPayload) ? rawPayload : {};
    const items = normalizeConditionItems(payload.items);
    const context = isPlainObject(payload.context) ? payload.context : {};
    const windValue = safeNumber(context.wind_avg_kmh);
    const pressureValue = safeNumber(context.pressure_avg_hpa);
    const eveningPrecipitation = safeNumber(context.evening_precipitation_mm);
    const sourceSummary = normalizeSourceItems(payload.sources, [
        { label: "Open-Meteo", value: "Weerdata" },
        { label: "Visregels", value: "Lokale regelset" },
    ]);

    const contextLine = windValue !== null && pressureValue !== null
        ? `Referentie: wind gemiddeld ${windValue.toFixed(1)} km/u, luchtdruk rond ${pressureValue.toFixed(1)} hPa en neerslag vanavond circa ${formatNumericValue(eveningPrecipitation, "mm")}.`
        : "";

    return {
        status: String(payload.status || "Viscondities vandaag").trim(),
        score: clampScore(payload.score),
        scoreLabel: config.scoreLabel,
        itemMode: "condition",
        items,
        analysis: compactLines(
            normalizeStringArray(payload.details),
            contextLine ? [contextLine] : []
        ),
        advice: buildAdviceLinesFromItems(items, {
            "Wind": "Windbeeld",
            "Luchtdruk": "Drukbeeld",
            "Beste tijd": "Beste moment",
            "Tip": "Tip",
        }),
        sources: sourceSummary,
        openUrl: String(payload.url || config.defaultOpenUrl).trim() || config.defaultOpenUrl,
        openLabel: config.defaultOpenLabel,
        openExternal: true,
    };
}

function renderAgentPage(panel, model, config) {
    const statusNode = panel.querySelector("[data-agent-status]");
    const scoreNode = panel.querySelector("[data-agent-score]");
    const itemsNode = panel.querySelector("[data-agent-items]");
    const analysisNode = panel.querySelector("[data-agent-analysis]");
    const adviceNode = panel.querySelector("[data-agent-advice]");
    const sourcesNode = panel.querySelector("[data-agent-sources]");
    const openLink = panel.querySelector("[data-agent-open-link]");
    const openLabel = panel.querySelector("[data-agent-open-label]");

    if (statusNode) {
        statusNode.textContent = `Status: ${model.status}`;
    }

    if (scoreNode) {
        if (Number.isFinite(model.score) && model.score > 0 && model.scoreLabel) {
            scoreNode.hidden = false;
            scoreNode.textContent = `${model.scoreLabel}: ${Math.round(model.score)}/5`;
        } else {
            scoreNode.hidden = true;
            scoreNode.textContent = "";
        }
    }

    if (itemsNode) {
        renderAgentItems(itemsNode, model);
    }

    if (analysisNode) {
        renderLineBlock(analysisNode, model.analysis, "Nog geen analyse beschikbaar.");
    }

    if (adviceNode) {
        renderLineBlock(adviceNode, model.advice, "Nog geen advies beschikbaar.");
    }

    if (sourcesNode) {
        renderSourceBlock(sourcesNode, model.sources);
    }

    if (openLink) {
        const href = String(model.openUrl || config.defaultOpenUrl).trim() || "#";
        openLink.setAttribute("href", href);

        if (model.openExternal) {
            openLink.setAttribute("target", "_blank");
            openLink.setAttribute("rel", "noopener noreferrer");
        } else {
            openLink.removeAttribute("target");
            openLink.removeAttribute("rel");
        }
    }

    if (openLabel) {
        openLabel.textContent = model.openLabel || config.defaultOpenLabel;
    }
}

function renderAgentPageError(panel, agentKey, config) {
    const statusNode = panel.querySelector("[data-agent-status]");
    const scoreNode = panel.querySelector("[data-agent-score]");
    const itemsNode = panel.querySelector("[data-agent-items]");
    const analysisNode = panel.querySelector("[data-agent-analysis]");
    const adviceNode = panel.querySelector("[data-agent-advice]");
    const sourcesNode = panel.querySelector("[data-agent-sources]");
    const openLink = panel.querySelector("[data-agent-open-link]");
    const openLabel = panel.querySelector("[data-agent-open-label]");

    if (statusNode) {
        statusNode.textContent = "Status: Data tijdelijk niet beschikbaar";
    }

    if (scoreNode) {
        scoreNode.hidden = true;
        scoreNode.textContent = "";
    }

    if (itemsNode) {
        renderStatus(itemsNode, "Nog geen actuele data beschikbaar.");
    }

    if (analysisNode) {
        renderLineBlock(
            analysisNode,
            [`De bron voor ${agentKey} kon niet worden geladen.`],
            "Bron tijdelijk niet beschikbaar."
        );
    }

    if (adviceNode) {
        renderLineBlock(
            adviceNode,
            ["Probeer later opnieuw; falende bronnen worden bewust overgeslagen."],
            "Nog geen advies beschikbaar."
        );
    }

    if (sourcesNode) {
        renderLineBlock(
            sourcesNode,
            ["Lokale pagina blijft bruikbaar, maar de JSON-bron was nu niet leesbaar."],
            "Nog geen bronnen beschikbaar."
        );
    }

    if (openLink) {
        openLink.setAttribute("href", config.defaultOpenUrl || "#");
        openLink.setAttribute("target", "_blank");
        openLink.setAttribute("rel", "noopener noreferrer");
    }

    if (openLabel) {
        openLabel.textContent = config.defaultOpenLabel;
    }
}

function renderAgentItems(container, model) {
    container.innerHTML = "";

    if (model.itemMode === "news") {
        const newsItems = normalizeArray(model.items);

        if (!newsItems.length) {
            renderStatus(container, "Nog geen nieuwsitems beschikbaar.");
            return;
        }

        container.appendChild(
            createNewsList(
                newsItems,
                DASHBOARD_CONFIG.detailNewsLimit,
                true,
                "news-detail-list"
            )
        );
        return;
    }

    if (model.itemMode === "sport") {
        const sportItems = normalizeArray(model.items);

        if (!sportItems.length) {
            renderStatus(container, "Geen sportitems gevonden voor vandaag.");
            return;
        }

        container.appendChild(createSportMiniList({ items: sportItems }));
        return;
    }

    const conditionItems = normalizeConditionItems(model.items);

    if (!conditionItems.length) {
        renderStatus(container, "Nog geen regels beschikbaar.");
        return;
    }

    container.appendChild(createConditionMiniList({ items: conditionItems }));
}

function renderLineBlock(container, lines, fallbackMessage) {
    container.innerHTML = "";

    const entries = normalizeStringArray(lines);
    if (!entries.length) {
        renderStatus(container, fallbackMessage);
        return;
    }

    const list = document.createElement("ul");
    list.className = "agent-detail-list";

    entries.forEach((line) => {
        const item = document.createElement("li");
        item.className = "agent-detail-item";
        item.textContent = line;
        list.appendChild(item);
    });

    container.appendChild(list);
}

function renderSourceBlock(container, sources) {
    container.innerHTML = "";

    const entries = normalizeConditionItems(sources);
    if (!entries.length) {
        renderStatus(container, "Nog geen bronnen beschikbaar.");
        return;
    }

    container.appendChild(createConditionMiniList({ items: entries }));
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

function isPlainObject(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function safeNumber(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
}

function clampScore(value) {
    const parsed = safeNumber(value);
    if (parsed === null) {
        return null;
    }

    return Math.max(1, Math.min(5, Math.round(parsed)));
}

function formatNumericValue(value, unit) {
    const parsed = safeNumber(value);
    if (parsed === null) {
        return "onbekend";
    }

    return `${parsed.toFixed(1)} ${unit}`;
}

function normalizeConditionItems(items) {
    return normalizeArray(items)
        .map((item) => ({
            label: String(item && item.label ? item.label : "").trim(),
            value: String(item && item.value ? item.value : "").trim(),
        }))
        .filter((item) => item.label && item.value);
}

function normalizeSourceItems(items, fallbackItems = []) {
    const sourceItems = normalizeArray(items)
        .map((item) => {
            if (isPlainObject(item)) {
                const name = String(item.name || item.label || "").trim();
                const url = String(item.url || "").trim();
                const note = String(item.note || "").trim();

                return {
                    label: name || "Bron",
                    value: note || summarizeUrl(url) || "Beschikbaar",
                };
            }

            if (typeof item === "string") {
                return {
                    label: item.trim() || "Bron",
                    value: "Beschikbaar",
                };
            }

            return null;
        })
        .filter(Boolean);

    if (sourceItems.length) {
        return sourceItems;
    }

    return normalizeConditionItems(fallbackItems);
}

function summarizeUrl(url) {
    try {
        return new URL(url).hostname.replace(/^www\./, "");
    } catch (error) {
        return "";
    }
}

function summarizeNewsSources(items) {
    const sourceMap = new Map();

    normalizeArray(items).forEach((item) => {
        const source = String(item && item.source ? item.source : "").trim();
        if (!source) {
            return;
        }

        const current = sourceMap.get(source) || { count: 0, url: "" };
        current.count += 1;

        if (!current.url && item && item.url) {
            current.url = String(item.url).trim();
        }

        sourceMap.set(source, current);
    });

    return Array.from(sourceMap.entries())
        .sort((left, right) => right[1].count - left[1].count || left[0].localeCompare(right[0], "nl"))
        .slice(0, DASHBOARD_CONFIG.compactSourceLimit)
        .map(([label, meta]) => ({
            label,
            value: `${meta.count} bericht(en)`,
        }));
}

function uniqueTextValues(values) {
    const seen = new Set();
    const unique = [];

    values.forEach((value) => {
        const text = String(value || "").trim();
        const key = text.toLowerCase();

        if (!text || seen.has(key)) {
            return;
        }

        seen.add(key);
        unique.push(text);
    });

    return unique;
}

function compactLines(primaryLines, secondaryLines = []) {
    return normalizeStringArray([...normalizeStringArray(primaryLines), ...normalizeStringArray(secondaryLines)]);
}

function normalizeStringArray(values, fallback = []) {
    const base = normalizeArray(values)
        .map((value) => String(value || "").trim())
        .filter(Boolean);

    if (base.length) {
        return base;
    }

    return normalizeArray(fallback)
        .map((value) => String(value || "").trim())
        .filter(Boolean);
}

function buildAdviceLinesFromItems(items, labels) {
    return normalizeConditionItems(items).map((item) => {
        const prefix = labels[item.label] || item.label;
        return `${prefix}: ${item.value}.`;
    });
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

function hydrateNavigationLinks() {
    document.querySelectorAll("[data-nav-target]").forEach((link) => {
        const targetKey = String(link.dataset.navTarget || "").trim();
        const config = NAVIGATION_LINKS[targetKey];

        if (!config || !config.href) {
            return;
        }

        link.setAttribute("href", config.href);

        if (config.external) {
            link.setAttribute("target", "_blank");
            link.setAttribute("rel", "noopener noreferrer");
        } else {
            link.removeAttribute("target");
            link.removeAttribute("rel");
        }
    });
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
        createMetaText(formatDate(item.published || item.publishedAt, !showSummary))
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

    if (!items.length) {
        return createInlineStatus("Nog geen sportitems beschikbaar.");
    }

    const list = document.createElement("div");
    list.className = "agent-mini-list";

    items.forEach((item) => {
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
        meta.textContent = [item.category, item.source].filter(Boolean).join(" | ") || "Sport";

        text.append(title, meta);
        row.append(leading, text);
        list.append(row);
    });

    return list;
}

function createConditionMiniList(payload) {
    const items = normalizeArray(payload && payload.items);

    if (!items.length) {
        return createInlineStatus("Nog geen statusregels beschikbaar.");
    }

    const list = document.createElement("div");
    list.className = "agent-mini-list";

    items.forEach((item) => {
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
