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

const RUNTIME_CONFIG = window.BOBOS_CONFIG && typeof window.BOBOS_CONFIG === "object"
    ? window.BOBOS_CONFIG
    : {};

const DASHBOARD_CONFIG = {
    dashboardNewsLimit: 5,
    detailNewsLimit: 12,
    newsExplorerInitialBatch: 12,
    newsExplorerBatchSize: 10,
    compactSummaryLength: 120,
    compactSourceLimit: 6,
};

const NEWS_CATEGORY_PREFERRED_ORDER = [
    "Alle",
    "Archeologie",
    "Wetenschap",
    "Sport",
    "Voetbal",
    "Formule 1",
    "Gadgets",
    "Algemeen",
];

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

const DEFAULT_REFRESH_SERVICE = {
    localBaseUrl: "http://127.0.0.1:8787",
    productionBaseUrl: "",
    timeoutMs: 15000,
};

const WORKFLOW_CONFIGS = {
    news: {
        label: "Nieuws",
    },
    sport: {
        label: "Sport",
    },
    detectie: {
        label: "Detectie",
    },
    vissen: {
        label: "Vissen",
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
    bindWorkflowButtons();

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
    const latestItem = items[0] || null;
    const sourceSummary = summarizeNewsSources(items);
    const categorySummary = uniqueTextValues(items.map((item) => item.category)).slice(0, 5);

    return {
        status: latestItem
            ? `${items.length} nieuwsbericht(en) geladen`
            : "Geen nieuws beschikbaar",
        score: null,
        scoreLabel: config.scoreLabel,
        itemMode: "news",
        items: items,
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
            "Gebruik de categorieknoppen bovenaan om sneller door archeologie, wetenschap, sport en andere clusters te bladeren.",
            "De homepage blijft bewust compact; deze pagina toont de volledige selectie zonder volledige artikelen op te slaan.",
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
        score: clampScore(item.score) || 1,
        must_watch: Boolean(item.must_watch),
        reason: String(item.reason || "").trim(),
    }));
    const categories = uniqueTextValues(items.map((item) => item.category));
    const sourceSummary = normalizeSourceItems(payload.sources, [
        { label: "OpenFootball", value: "Voetbalbron" },
        { label: "ESPN", value: "Scoreboard" },
        { label: "OpenF1", value: "Sessies" },
        { label: "PDC", value: "Dartsfixtures" },
    ]);
    const mustWatchCount = items.filter((item) => item.must_watch).length;
    const topItem = items[0] || null;

    return {
        status: String(payload.status || (items.length ? "Vandaag interessant" : "Geen sport gevonden voor vandaag")).trim(),
        score: null,
        scoreLabel: config.scoreLabel,
        scoreMode: "default",
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
                topItem
                    ? `Topkeuze: ${topItem.title} (${topItem.score}/5) - ${topItem.reason || "hoogste prioriteit"}.`
                    : "Gebruik de hoogste score als startpunt.",
                mustWatchCount
                    ? `${mustWatchCount} item(s) vallen in de categorie Must see.`
                    : "Er is geen directe must-see, maar de hoogste scores blijven het meest relevant.",
            ]
            : [
                "Later opnieuw proberen kan nieuwe wedstrijden, darts of F1-sessies opleveren.",
                "Alleen voetbal, darts en Formule 1 tellen mee voor deze selectie.",
            ],
        profiles: [],
        sources: sourceSummary,
        openUrl: String(payload.url || config.defaultOpenUrl).trim() || config.defaultOpenUrl,
        openLabel: config.defaultOpenLabel,
        openExternal: true,
    };
}

function buildDetectiePageModel(rawPayload, config) {
    const payload = isPlainObject(rawPayload) ? rawPayload : {};
    const items = normalizeConditionItems(payload.items);
    const profiles = normalizeProfileItems(payload.profiles);
    const context = isPlainObject(payload.context) ? payload.context : {};
    const rainfall = safeNumber(context.rain_last_7_days_mm);
    const mondayDate = String(context.monday_date || "").trim();
    const mondayPrecipitation = safeNumber(context.monday_precipitation_mm);
    const seasonLabel = String(context.season_label || "").trim();
    const fieldAccess = String(context.field_access || "").trim();
    const sourceSummary = normalizeSourceItems(payload.sources, [
        { label: "Open-Meteo", value: "Weerdata" },
        { label: "Detectieregels", value: "Lokale regelset" },
    ]);

    const contextLine = rainfall !== null && mondayDate
        ? `Referentie: ${rainfall.toFixed(1)} mm regen in de afgelopen 7 dagen, maandag ${mondayDate} circa ${formatNumericValue(mondayPrecipitation, "mm")}.`
        : "";
    const seasonLine = seasonLabel ? `${seasonLabel}: ${fieldAccess || "Kijk vooral naar bereikbare en vrijliggende percelen."}` : "";

    return {
        status: String(payload.status || "Maandagadvies").trim(),
        score: clampScore(payload.score),
        scoreLabel: config.scoreLabel,
        scoreMode: "default",
        itemMode: "condition",
        items,
        analysis: compactLines(
            normalizeStringArray(payload.details),
            [
                ...(seasonLine ? [seasonLine] : []),
                ...(contextLine ? [contextLine] : []),
            ]
        ),
        advice: buildAdviceLinesFromItems(items, {
            "Beste keuze": "Beste terrein",
            "Vermijd": "Vermijd",
            "Tip": "Tip",
        }),
        profiles,
        sources: sourceSummary,
        openUrl: String(payload.url || config.defaultOpenUrl).trim() || config.defaultOpenUrl,
        openLabel: config.defaultOpenLabel,
        openExternal: true,
    };
}

function buildVissenPageModel(rawPayload, config) {
    const payload = isPlainObject(rawPayload) ? rawPayload : {};
    const items = normalizeConditionItems(payload.items);
    const profiles = normalizeProfileItems(payload.profiles);
    const context = isPlainObject(payload.context) ? payload.context : {};
    const details = normalizeStringArray(payload.details);
    const windItemValue = getConditionItemValue(items, "Wind");
    const pressureItemValue = getConditionItemValue(items, "Luchtdruk");
    const bestTime = getConditionItemValue(items, "Beste tijd");
    const windValue = safeNumber(context.wind_avg_kmh);
    const pressureValue = safeNumber(context.pressure_avg_hpa);
    const eveningPrecipitation = safeNumber(context.evening_precipitation_mm);
    const seasonLabel = String(context.season_label || "").trim();
    const pressureTrend = safeNumber(context.pressure_delta_48h_hpa);
    const temperatureDelta = safeNumber(context.temperature_delta_c);
    const sourceSummary = normalizeSourceItems(payload.sources, [
        { label: "Open-Meteo", value: "Weerdata" },
        { label: "Visregels", value: "Lokale regelset" },
    ]);

    const contextLine = windValue !== null && pressureValue !== null
        ? `Referentie: wind gemiddeld ${windValue.toFixed(1)} km/u, luchtdruk rond ${pressureValue.toFixed(1)} hPa en neerslag vanavond circa ${formatNumericValue(eveningPrecipitation, "mm")}.`
        : "";
    const trendLine = pressureTrend !== null || temperatureDelta !== null
        ? `Trend: luchtdruk ${formatSignedValue(pressureTrend, "hPa")} en temperatuur ${formatSignedValue(temperatureDelta, "C")}.`
        : "";
    const seasonLine = seasonLabel ? `${seasonLabel}: schemer en seizoensritme wegen mee in het advies.` : "";

    return {
        status: String(payload.status || "Visadvies vandaag").trim(),
        score: clampScore(payload.score),
        scoreLabel: config.scoreLabel,
        scoreMode: "fish",
        itemMode: "condition",
        items,
        analysis: compactLines(
            details,
            [
                ...(seasonLine ? [seasonLine] : []),
                ...(trendLine ? [trendLine] : []),
                ...(contextLine ? [contextLine] : []),
            ]
        ),
        advice: buildAdviceLinesFromItems(items, {
            "Wind": "Windbeeld",
            "Luchtdruk": "Drukbeeld",
            "Beste tijd": "Beste moment",
            "Tip": "Tip",
        }),
        profiles,
        chart: buildFishingChartModel({
            context,
            details,
            windItemValue,
            pressureItemValue,
            bestTime,
        }),
        sources: sourceSummary,
        openUrl: String(payload.url || config.defaultOpenUrl).trim() || config.defaultOpenUrl,
        openLabel: config.defaultOpenLabel,
        openExternal: true,
    };
}

function getConditionItemValue(items, label) {
    const match = normalizeConditionItems(items).find((item) => item.label.toLowerCase() === String(label || "").trim().toLowerCase());
    return match ? match.value : "";
}

function buildFishingChartModel({ context, details, windItemValue, pressureItemValue, bestTime }) {
    const windSpeed = safeNumber(context.wind_avg_kmh) ?? extractWindSpeedFromText(windItemValue);
    const pressure = safeNumber(context.pressure_avg_hpa) ?? extractPressureFromText(pressureItemValue);
    const precipitation = safeNumber(context.evening_precipitation_mm) ?? extractPrecipitationFromDetails(details);
    const temperature = safeNumber(context.evening_temperature_c);
    const directionDegrees = safeNumber(context.wind_direction_deg);
    const directionLabel = String(context.wind_direction_label || "").trim() || extractWindDirectionLabel(windItemValue) || degreesToWindLabel(directionDegrees);
    const safeDirectionDegrees = directionDegrees ?? windLabelToDegrees(directionLabel);
    const metrics = [];

    if (pressure !== null) {
        metrics.push({
            label: "Luchtdruk",
            value: `${pressure.toFixed(0)} hPa`,
            ratio: normalizeMetricValue(pressure, 995, 1035),
        });
    }

    if (windSpeed !== null) {
        metrics.push({
            label: "Wind",
            value: `${windSpeed.toFixed(0)} km/u`,
            ratio: normalizeMetricValue(windSpeed, 0, 40),
        });
    }

    if (precipitation !== null) {
        metrics.push({
            label: "Neerslag",
            value: `${precipitation.toFixed(1)} mm`,
            ratio: normalizeMetricValue(precipitation, 0, 8),
        });
    }

    if (temperature !== null) {
        metrics.push({
            label: "Temp",
            value: `${temperature.toFixed(0)} C`,
            ratio: normalizeMetricValue(temperature, 8, 28),
        });
    }

    if (!metrics.length && !directionLabel && !bestTime) {
        return null;
    }

    return {
        metrics,
        directionLabel: directionLabel || "Onbekend",
        directionDegrees: safeDirectionDegrees ?? 0,
        bestTime: String(bestTime || "").trim(),
    };
}

function extractNumericMatch(text, pattern) {
    const match = String(text || "").match(pattern);
    if (!match) {
        return null;
    }

    const normalized = match[1].replace(",", ".");
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
}

function extractWindSpeedFromText(text) {
    const directValue = extractNumericMatch(text, /(\d+(?:[.,]\d+)?)\s*km\/u/i);
    if (directValue !== null) {
        return directValue;
    }

    const bftValue = extractNumericMatch(text, /(\d+(?:[.,]\d+)?)\s*Bft/i);
    if (bftValue === null) {
        return null;
    }

    return beaufortToApproxKmh(bftValue);
}

function extractPressureFromText(text) {
    return extractNumericMatch(text, /(\d+(?:[.,]\d+)?)\s*hPa/i);
}

function extractPrecipitationFromDetails(details) {
    for (const detail of normalizeStringArray(details)) {
        const directMatch = extractNumericMatch(detail, /(\d+(?:[.,]\d+)?)\s*mm\s*neerslag/i);
        if (directMatch !== null) {
            return directMatch;
        }
    }

    return null;
}

function extractWindDirectionLabel(text) {
    const match = String(text || "").trim().match(/\b(NNO|ONO|ZZO|WZW|WNW|NNW|OZO|ZZW|NO|ZO|ZW|NW|N|O|Z|W)\b/i);
    return match ? match[1].toUpperCase() : "";
}

function normalizeMetricValue(value, min, max) {
    if (!Number.isFinite(value)) {
        return 0;
    }

    const normalized = (value - min) / (max - min);
    return Math.max(0.08, Math.min(1, normalized));
}

function beaufortToApproxKmh(bftValue) {
    const table = [0, 3, 8, 15, 24, 34, 45, 56, 68, 82, 96, 110, 125];
    const safeIndex = Math.max(0, Math.min(table.length - 1, Math.round(bftValue)));
    return table[safeIndex];
}

function degreesToWindLabel(degrees) {
    if (!Number.isFinite(degrees)) {
        return "";
    }

    const labels = ["N", "NO", "O", "ZO", "Z", "ZW", "W", "NW"];
    const normalized = ((degrees % 360) + 360) % 360;
    const index = Math.round(normalized / 45) % labels.length;
    return labels[index];
}

function windLabelToDegrees(label) {
    const mapping = {
        N: 0,
        NNO: 22.5,
        NO: 45,
        ONO: 67.5,
        O: 90,
        OZO: 112.5,
        ZO: 135,
        ZZO: 157.5,
        Z: 180,
        ZZW: 202.5,
        ZW: 225,
        WZW: 247.5,
        W: 270,
        WNW: 292.5,
        NW: 315,
        NNW: 337.5,
    };

    return Object.prototype.hasOwnProperty.call(mapping, label) ? mapping[label] : null;
}

function scoreToFishUnits(score) {
    const normalized = clampScore(score) ?? 1;
    const mapping = {
        1: 0,
        2: 0.5,
        3: 1,
        4: 1.5,
        5: 3,
    };

    return mapping[normalized] ?? 0;
}

function formatFishUnitsLabel(units) {
    if (units <= 0) {
        return "Visgraat";
    }

    const display = Number.isInteger(units) ? `${units}` : `${String(units).replace(".", ",")}`;
    return `${display} vis${units === 1 ? "" : "jes"}`;
}

function renderAgentPage(panel, model, config) {
    const statusNode = panel.querySelector("[data-agent-status]");
    const scoreNode = panel.querySelector("[data-agent-score]");
    const itemsNode = panel.querySelector("[data-agent-items]");
    const chartNode = panel.querySelector("[data-agent-chart]");
    const chartCard = panel.querySelector("[data-agent-chart-card]");
    const analysisNode = panel.querySelector("[data-agent-analysis]");
    const adviceNode = panel.querySelector("[data-agent-advice]");
    const profilesNode = panel.querySelector("[data-agent-profiles]");
    const sourcesNode = panel.querySelector("[data-agent-sources]");
    const openLink = panel.querySelector("[data-agent-open-link]");
    const openLabel = panel.querySelector("[data-agent-open-label]");

    if (statusNode) {
        statusNode.textContent = model.status;
    }

    renderAgentScore(scoreNode, model);

    if (itemsNode) {
        if (model.itemMode === "news" && panel.dataset.agentKey === "news") {
            renderNewsExplorer(panel, itemsNode, model);
        } else {
            renderAgentItems(itemsNode, model);
        }
    }

    renderAgentChart(chartCard, chartNode, model);

    if (analysisNode) {
        renderLineBlock(analysisNode, model.analysis, "Nog geen analyse beschikbaar.");
    }

    if (adviceNode) {
        renderLineBlock(adviceNode, model.advice, "Nog geen advies beschikbaar.");
    }

    if (profilesNode) {
        renderProfileBlock(profilesNode, model.profiles);
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
    const chartNode = panel.querySelector("[data-agent-chart]");
    const chartCard = panel.querySelector("[data-agent-chart-card]");
    const analysisNode = panel.querySelector("[data-agent-analysis]");
    const adviceNode = panel.querySelector("[data-agent-advice]");
    const profilesNode = panel.querySelector("[data-agent-profiles]");
    const sourcesNode = panel.querySelector("[data-agent-sources]");
    const openLink = panel.querySelector("[data-agent-open-link]");
    const openLabel = panel.querySelector("[data-agent-open-label]");

    resetNewsExplorer(panel);

    if (statusNode) {
        statusNode.textContent = "Data tijdelijk niet beschikbaar";
    }

    if (scoreNode) {
        scoreNode.hidden = true;
        scoreNode.innerHTML = "";
    }

    if (itemsNode) {
        renderStatus(itemsNode, "Nog geen actuele data beschikbaar.");
    }

    if (chartCard) {
        chartCard.hidden = true;
    }

    if (chartNode) {
        chartNode.innerHTML = "";
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

    if (profilesNode) {
        renderLineBlock(
            profilesNode,
            ["Profielscores worden zichtbaar zodra de verrijkte brondata weer beschikbaar is."],
            "Nog geen profielen beschikbaar."
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

function renderAgentScore(container, model) {
    if (!container) {
        return;
    }

    const score = clampScore(model.score);
    if (!score || !model.scoreLabel) {
        container.hidden = true;
        container.innerHTML = "";
        return;
    }

    container.hidden = false;
    container.innerHTML = "";

    if (model.scoreMode === "fish") {
        container.appendChild(createFishScoreDisplay(model.scoreLabel, score));
        replaceIcons();
        return;
    }

    container.textContent = `${model.scoreLabel}: ${score}/5`;
}

function renderAgentChart(card, container, model) {
    if (!card || !container) {
        return;
    }

    if (!model.chart) {
        card.hidden = true;
        container.innerHTML = "";
        return;
    }

    card.hidden = false;
    container.innerHTML = "";
    container.appendChild(createFishingChart(model.chart));
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

function createFishScoreDisplay(label, score) {
    const wrapper = document.createElement("div");
    wrapper.className = "agent-score-row";

    const scoreText = document.createElement("span");
    scoreText.textContent = `${label}: ${score}/5`;

    const fishBlock = document.createElement("span");
    fishBlock.className = "agent-score-fish";

    const units = scoreToFishUnits(score);
    const fishLabel = document.createElement("span");
    fishLabel.className = "agent-score-fish-label";
    fishLabel.textContent = units <= 0 ? "Slecht" : formatFishUnitsLabel(units);

    const fishRating = document.createElement("span");
    fishRating.className = "fish-rating";

    if (units <= 0) {
        fishRating.classList.add("fish-rating--empty");
        const emptyText = document.createElement("span");
        emptyText.className = "fish-rating-text";
        emptyText.textContent = "visgraat";
        fishRating.appendChild(emptyText);
    } else {
        for (let index = 0; index < 3; index += 1) {
            const slot = document.createElement("span");
            slot.className = "fish-rating-slot";
            const remaining = units - index;

            if (remaining >= 1) {
                slot.classList.add("is-filled");
            } else if (remaining >= 0.5) {
                slot.classList.add("is-half");
            }

            const icon = document.createElement("i");
            icon.dataset.lucide = "fish";
            slot.appendChild(icon);
            fishRating.appendChild(slot);
        }
    }

    fishBlock.append(fishLabel, fishRating);
    wrapper.append(scoreText, fishBlock);
    return wrapper;
}

function createFishingChart(chart) {
    const wrapper = document.createElement("div");
    wrapper.className = "fish-chart";

    const metricsGrid = document.createElement("div");
    metricsGrid.className = "fish-chart-grid";

    normalizeArray(chart.metrics).forEach((metric) => {
        const metricNode = document.createElement("div");
        metricNode.className = "fish-chart-metric";

        const meta = document.createElement("div");
        meta.className = "fish-chart-meta";

        const label = document.createElement("span");
        label.className = "fish-chart-label";
        label.textContent = metric.label;

        const value = document.createElement("span");
        value.className = "fish-chart-value";
        value.textContent = metric.value;

        const bar = document.createElement("div");
        bar.className = "fish-chart-bar";

        const fill = document.createElement("span");
        fill.style.width = `${Math.round((Number(metric.ratio) || 0) * 100)}%`;
        bar.appendChild(fill);

        meta.append(label, value);
        metricNode.append(meta, bar);
        metricsGrid.appendChild(metricNode);
    });

    wrapper.appendChild(metricsGrid);

    const compass = document.createElement("div");
    compass.className = "fish-chart-compass";

    const compassRing = document.createElement("span");
    compassRing.className = "fish-chart-compass-ring";
    compassRing.style.setProperty("--wind-angle", `${Number(chart.directionDegrees) || 0}deg`);

    const compassValue = document.createElement("span");
    compassValue.className = "fish-chart-value";
    compassValue.textContent = `Windrichting ${chart.directionLabel || "Onbekend"}`;

    compass.append(compassRing, compassValue);
    wrapper.appendChild(compass);

    if (chart.bestTime) {
        const context = document.createElement("p");
        context.className = "fish-chart-context";
        context.textContent = `Beste tijd: ${chart.bestTime}.`;
        wrapper.appendChild(context);
    }

    replaceIcons();
    return wrapper;
}

function renderNewsExplorer(panel, container, model) {
    resetNewsExplorer(panel);

    const items = normalizeArray(model.items);
    const categoryNode = panel.querySelector("[data-news-categories]");
    const metaNode = panel.querySelector("[data-news-feed-meta]");

    if (!items.length) {
        if (categoryNode) {
            categoryNode.innerHTML = "";
        }

        if (metaNode) {
            metaNode.textContent = "Nog geen nieuwsberichten beschikbaar.";
        }

        renderStatus(container, "Nog geen nieuwsitems beschikbaar.");
        return;
    }

    const categoryOptions = buildNewsCategoryOptions(items);
    const requestedCategory = readRequestedNewsCategory(categoryOptions);
    const listNode = document.createElement("div");
    listNode.className = "news-compact-list news-feed-list";

    const sentinelNode = document.createElement("div");
    sentinelNode.className = "news-feed-sentinel";
    sentinelNode.setAttribute("aria-hidden", "true");

    const endNode = document.createElement("p");
    endNode.className = "news-feed-end";
    endNode.hidden = true;

    container.innerHTML = "";
    container.append(listNode, sentinelNode, endNode);

    const state = {
        panel,
        container,
        categoryNode,
        metaNode,
        listNode,
        sentinelNode,
        endNode,
        allItems: items,
        categoryOptions,
        activeCategory: requestedCategory,
        filteredItems: [],
        visibleCount: 0,
        supportsInfiniteScroll: "IntersectionObserver" in window,
        observer: null,
        isRendering: false,
    };

    panel.__newsExplorerState = state;
    renderNewsCategoryButtons(state);
    applyNewsCategory(state, requestedCategory);
}

function resetNewsExplorer(panel) {
    const state = panel && panel.__newsExplorerState;
    if (!state) {
        const categoryNode = panel ? panel.querySelector("[data-news-categories]") : null;
        const metaNode = panel ? panel.querySelector("[data-news-feed-meta]") : null;

        if (categoryNode) {
            categoryNode.innerHTML = "";
        }

        if (metaNode) {
            metaNode.textContent = "";
        }
        return;
    }

    if (state.observer) {
        state.observer.disconnect();
    }

    if (state.categoryNode) {
        state.categoryNode.innerHTML = "";
    }

    if (state.metaNode) {
        state.metaNode.textContent = "";
    }

    delete panel.__newsExplorerState;
}

function buildNewsCategoryOptions(items) {
    const categories = uniqueTextValues(items.map((item) => item.category));
    const ordered = [];

    NEWS_CATEGORY_PREFERRED_ORDER.forEach((category) => {
        if (!ordered.some((item) => item.toLowerCase() === category.toLowerCase())) {
            ordered.push(category);
        }
    });

    categories
        .filter((category) => !ordered.some((item) => item.toLowerCase() === category.toLowerCase()))
        .sort((left, right) => left.localeCompare(right, "nl"))
        .forEach((category) => ordered.push(category));

    return ordered;
}

function readRequestedNewsCategory(categoryOptions) {
    const params = new URLSearchParams(window.location.search);
    const requested = String(params.get("category") || "").trim().toLowerCase();

    if (!requested) {
        return "Alle";
    }

    return categoryOptions.find((category) => category.toLowerCase() === requested) || "Alle";
}

function renderNewsCategoryButtons(state) {
    if (!state.categoryNode) {
        return;
    }

    state.categoryNode.innerHTML = "";

    state.categoryOptions.forEach((category) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "news-category-button";
        button.textContent = category;

        if (category.toLowerCase() === state.activeCategory.toLowerCase()) {
            button.classList.add("is-active");
            button.setAttribute("aria-pressed", "true");
        } else {
            button.setAttribute("aria-pressed", "false");
        }

        button.addEventListener("click", () => {
            applyNewsCategory(state, category);
        });

        state.categoryNode.appendChild(button);
    });
}

function applyNewsCategory(state, category) {
    state.activeCategory = category;
    state.filteredItems = filterNewsItemsByCategory(state.allItems, category);
    state.visibleCount = 0;
    state.listNode.innerHTML = "";
    state.endNode.hidden = true;
    state.endNode.textContent = "";

    renderNewsCategoryButtons(state);
    syncNewsCategoryQuery(category);
    ensureNewsExplorerObserver(state);
    renderNextNewsBatch(
        state,
        state.supportsInfiniteScroll
            ? DASHBOARD_CONFIG.newsExplorerInitialBatch
            : state.filteredItems.length
    );
}

function filterNewsItemsByCategory(items, category) {
    if (String(category || "").trim().toLowerCase() === "alle") {
        return normalizeArray(items);
    }

    return normalizeArray(items).filter((item) => {
        return normalizeCategory(item.category) === normalizeCategory(category);
    });
}

function ensureNewsExplorerObserver(state) {
    if (!state.sentinelNode) {
        return;
    }

    if (!state.supportsInfiniteScroll) {
        state.sentinelNode.hidden = true;
        return;
    }

    if (state.observer) {
        state.observer.disconnect();
    }

    state.observer = new IntersectionObserver((entries) => {
        const shouldLoadMore = entries.some((entry) => entry.isIntersecting);
        if (shouldLoadMore) {
            renderNextNewsBatch(state, DASHBOARD_CONFIG.newsExplorerBatchSize);
        }
    }, {
        rootMargin: "280px 0px 280px 0px",
    });

    state.observer.observe(state.sentinelNode);
}

function renderNextNewsBatch(state, batchSize) {
    if (state.isRendering) {
        return;
    }

    state.isRendering = true;

    const nextItems = state.filteredItems.slice(state.visibleCount, state.visibleCount + batchSize);

    if (!nextItems.length && !state.visibleCount) {
        state.listNode.innerHTML = "";
        state.listNode.appendChild(createInlineStatus("Geen nieuwsberichten in deze categorie."));
        state.sentinelNode.hidden = true;
        state.endNode.hidden = true;
        updateNewsFeedMeta(state);
        state.isRendering = false;
        return;
    }

    nextItems.forEach((item) => {
        state.listNode.appendChild(createNewsItem(item, false));
    });

    state.visibleCount += nextItems.length;

    const hasMore = state.visibleCount < state.filteredItems.length;
    state.sentinelNode.hidden = !hasMore;
    state.endNode.hidden = hasMore || !state.filteredItems.length;
    state.endNode.textContent = hasMore
        ? ""
        : `Alle ${state.filteredItems.length} berichten${state.activeCategory === "Alle" ? "" : ` in ${state.activeCategory.toLowerCase()}`} zijn geladen.`;

    updateNewsFeedMeta(state);
    replaceIcons();
    state.isRendering = false;
}

function updateNewsFeedMeta(state) {
    if (!state.metaNode) {
        return;
    }

    const total = state.filteredItems.length;
    const visible = Math.min(state.visibleCount, total);

    if (!total) {
        state.metaNode.textContent = state.activeCategory === "Alle"
            ? "Geen nieuwsberichten beschikbaar."
            : `Geen nieuwsberichten in ${state.activeCategory.toLowerCase()}.`;
        return;
    }

    state.metaNode.textContent = state.activeCategory === "Alle"
        ? `${visible} van ${total} berichten zichtbaar.${state.supportsInfiniteScroll && visible < total ? " Scroll verder voor meer." : ""}`
        : `${visible} van ${total} berichten zichtbaar in ${state.activeCategory.toLowerCase()}.${state.supportsInfiniteScroll && visible < total ? " Scroll verder voor meer." : ""}`;
}

function syncNewsCategoryQuery(category) {
    if (!window.history || !window.history.replaceState) {
        return;
    }

    const url = new URL(window.location.href);
    if (String(category || "").trim().toLowerCase() === "alle") {
        url.searchParams.delete("category");
    } else {
        url.searchParams.set("category", category);
    }

    window.history.replaceState({}, "", url);
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

function renderProfileBlock(container, profiles) {
    container.innerHTML = "";

    const entries = normalizeProfileItems(profiles);
    if (!entries.length) {
        renderStatus(container, "Nog geen profielen beschikbaar.");
        return;
    }

    container.appendChild(createProfileList(entries));
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

function formatSignedValue(value, unit) {
    const parsed = safeNumber(value);
    if (parsed === null) {
        return "onbekend";
    }

    return `${parsed >= 0 ? "+" : ""}${parsed.toFixed(1)} ${unit}`;
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

function normalizeProfileItems(items) {
    return normalizeArray(items)
        .map((item) => ({
            name: String(item && item.name ? item.name : "").trim(),
            score: clampScore(item && item.score),
            advice: String(item && item.advice ? item.advice : "").trim(),
        }))
        .filter((item) => item.name && item.score && item.advice);
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
        const value = /[.!?]$/.test(item.value) ? item.value : `${item.value}.`;
        return `${prefix}: ${value}`;
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

function bindWorkflowButtons() {
    document.querySelectorAll("[data-workflow-target]").forEach((button) => {
        const targetKey = String(button.dataset.workflowTarget || "").trim();
        const config = WORKFLOW_CONFIGS[targetKey];

        if (!config) {
            return;
        }

        button.setAttribute("aria-label", `${config.label} verversen`);
        button.setAttribute("title", `${config.label} verversen`);

        if (button.dataset.bound === "true") {
            return;
        }

        button.dataset.bound = "true";
        button.addEventListener("click", () => {
            void triggerWorkflowDispatch(targetKey, button);
        });
    });
}

function normalizeRefreshServiceUrl(value) {
    return String(value || "").trim().replace(/\/+$/, "");
}

function isLocalRefreshContext() {
    return window.location.protocol === "http:"
        && ["127.0.0.1", "localhost"].includes(window.location.hostname);
}

function getRefreshServiceBaseUrl() {
    const configuredUrl = normalizeRefreshServiceUrl(RUNTIME_CONFIG.refreshServiceUrl);
    if (configuredUrl) {
        return configuredUrl;
    }

    if (isLocalRefreshContext()) {
        return DEFAULT_REFRESH_SERVICE.localBaseUrl;
    }

    return normalizeRefreshServiceUrl(DEFAULT_REFRESH_SERVICE.productionBaseUrl);
}

function workflowDispatchUrl(targetKey) {
    const baseUrl = getRefreshServiceBaseUrl();
    if (!baseUrl) {
        return "";
    }

    return `${baseUrl}/dispatch/${targetKey}`;
}

function getWorkflowFeedbackNode(targetKey) {
    return document.querySelector(`[data-refresh-feedback="${targetKey}"]`);
}

function getRefreshServiceUnavailableMessage() {
    return isLocalRefreshContext()
        ? "Verversservice niet gevonden. Start python refresh_proxy.py."
        : "Verversservice nog niet geconfigureerd voor de live site.";
}

function getRefreshServiceUnreachableMessage() {
    return isLocalRefreshContext()
        ? "Verversservice niet bereikbaar. Start python refresh_proxy.py en probeer opnieuw."
        : "Verversservice niet bereikbaar.";
}

async function readWorkflowResponseMessage(response) {
    try {
        const payload = await response.json();
        return String(payload.message || "").trim();
    } catch (error) {
        return "";
    }
}

function setWorkflowButtonState(button, isRunning) {
    button.disabled = isRunning;
    button.classList.toggle("is-running", isRunning);
    button.setAttribute("aria-busy", String(isRunning));
}

function setWorkflowFeedback(targetKey, message, state = "info") {
    const feedbackNode = getWorkflowFeedbackNode(targetKey);
    if (!feedbackNode) {
        return;
    }

    feedbackNode.textContent = message || "";
    feedbackNode.dataset.state = state;
    feedbackNode.hidden = !message;
}

async function buildWorkflowError(response, label) {
    const apiMessage = await readWorkflowResponseMessage(response);

    if (response.status === 404) {
        return apiMessage || `${label} kon niet worden gestart: onbekende workflow.`;
    }

    if (response.status === 403) {
        return apiMessage || `${label} kon niet worden gestart: aanvraag geblokkeerd door de verversservice.`;
    }

    if (response.status === 502) {
        return apiMessage || `${label} kon niet worden gestart via GitHub.`;
    }

    return apiMessage || `${label} kon niet worden gestart (${response.status}).`;
}

async function triggerWorkflowDispatch(targetKey, button) {
    const config = WORKFLOW_CONFIGS[targetKey];
    if (!config || button.disabled) {
        return;
    }

    const dispatchUrl = workflowDispatchUrl(targetKey);
    if (!dispatchUrl) {
        setWorkflowFeedback(targetKey, getRefreshServiceUnavailableMessage(), "error");
        return;
    }

    setWorkflowButtonState(button, true);
    setWorkflowFeedback(targetKey, `${config.label} wordt gestart...`, "info");

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), DEFAULT_REFRESH_SERVICE.timeoutMs);

    try {
        const response = await fetch(dispatchUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                source: "bobos-ui",
                page: window.location.pathname,
            }),
            signal: controller.signal,
        });

        if (!response.ok) {
            throw new Error(await buildWorkflowError(response, config.label));
        }

        const successMessage = await readWorkflowResponseMessage(response);
        setWorkflowFeedback(targetKey, successMessage || `${config.label} gestart. Ververs BobOS over ongeveer een minuut.`, "success");
    } catch (error) {
        console.error(error);
        const message = error instanceof DOMException && error.name === "AbortError"
            ? "Verversservice reageert te traag."
            : error instanceof TypeError
                ? getRefreshServiceUnreachableMessage()
                : error instanceof Error
                    ? error.message
                    : `${config.label} kon niet worden gestart.`;
        setWorkflowFeedback(targetKey, message, "error");
    } finally {
        window.clearTimeout(timeoutId);
        setWorkflowButtonState(button, false);
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
        row.className = "agent-mini-row agent-mini-row--sport agent-mini-row--sport-ranked";

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

        const score = document.createElement("span");
        score.className = "agent-mini-score";
        score.textContent = item.must_watch
            ? `Must see ${item.score || 1}/5`
            : `Score ${item.score || 1}/5`;

        const reason = document.createElement("span");
        reason.className = "agent-mini-reason";
        reason.textContent = item.reason || "Vandaag relevant";

        text.append(title, meta, score, reason);
        row.append(leading, text);
        list.append(row);
    });

    return list;
}

function createProfileList(items) {
    const list = document.createElement("div");
    list.className = "agent-profile-list";

    items.forEach((item) => {
        const row = document.createElement("div");
        row.className = "agent-profile-item";

        const heading = document.createElement("div");
        heading.className = "agent-profile-heading";

        const name = document.createElement("span");
        name.className = "agent-profile-name";
        name.textContent = item.name;

        const score = document.createElement("span");
        score.className = "agent-profile-score";
        score.textContent = `${item.score}/5`;

        const advice = document.createElement("p");
        advice.className = "agent-profile-advice";
        advice.textContent = item.advice;

        heading.append(name, score);
        row.append(heading, advice);
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
