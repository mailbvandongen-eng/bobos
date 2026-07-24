"use strict";

const REPOSITORY = {
    owner: "mailbvandongen-eng",
    repo: "bobos",
    ref: "main",
    apiVersion: "2022-11-28",
};

const WORKFLOWS = {
    news: {
        id: "news.yml",
        label: "Nieuws",
    },
    sport: {
        id: "sport.yml",
        label: "Sport",
    },
    detectie: {
        id: "detectie.yml",
        label: "Detectie",
    },
    vissen: {
        id: "vissen.yml",
        label: "Vissen",
    },
};

const TOKEN_ENV_KEYS = [
    "BOBOS_GITHUB_TOKEN",
    "GITHUB_TOKEN",
    "GH_TOKEN",
];

const ALLOWED_EXACT_ORIGINS = new Set([
    "https://mailbvandongen-eng.github.io",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8011",
    "http://127.0.0.1:8787",
    "http://localhost:8000",
    "http://localhost:8011",
    "http://localhost:8787",
]);

function readServerToken() {
    for (const key of TOKEN_ENV_KEYS) {
        const value = String(process.env[key] || "").trim();
        if (value) {
            return { token: value, source: key };
        }
    }

    return { token: "", source: "" };
}

function isAllowedOrigin(origin) {
    const normalizedOrigin = String(origin || "").trim();
    if (!normalizedOrigin) {
        return true;
    }

    if (ALLOWED_EXACT_ORIGINS.has(normalizedOrigin)) {
        return true;
    }

    try {
        const url = new URL(normalizedOrigin);
        return url.protocol === "https:" && url.hostname.endsWith(".vercel.app");
    } catch (error) {
        return false;
    }
}

function sendJson(res, statusCode, payload, origin = "") {
    if (origin && isAllowedOrigin(origin)) {
        res.setHeader("Access-Control-Allow-Origin", origin);
        res.setHeader("Vary", "Origin");
    }

    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    res.setHeader("Access-Control-Max-Age", "600");
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.status(statusCode).send(payload);
}

function sendError(res, statusCode, message, origin = "") {
    sendJson(
        res,
        statusCode,
        {
            ok: false,
            message,
        },
        origin,
    );
}

function getWorkflow(targetKey) {
    return WORKFLOWS[String(targetKey || "").trim().toLowerCase()] || null;
}

async function dispatchWithToken(workflowId, token) {
    const dispatchUrl = `https://api.github.com/repos/${REPOSITORY.owner}/${REPOSITORY.repo}/actions/workflows/${workflowId}/dispatches`;
    const response = await fetch(dispatchUrl, {
        method: "POST",
        headers: {
            Accept: "application/vnd.github+json",
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": REPOSITORY.apiVersion,
            "User-Agent": "BobOS-Vercel-Refresh/1.0",
        },
        body: JSON.stringify({ ref: REPOSITORY.ref }),
    });

    if (!response.ok) {
        const message = await readGithubError(response);
        throw new Error(message || `GitHub gaf status ${response.status} terug.`);
    }

    return "token";
}

async function readGithubError(response) {
    try {
        const payload = await response.json();
        return String(payload.message || "").trim();
    } catch (error) {
        return "";
    }
}

function detectTransportMode() {
    const { token } = readServerToken();
    return token ? "token" : "unavailable";
}

async function dispatchWorkflow(targetKey) {
    const workflow = getWorkflow(targetKey);
    if (!workflow) {
        throw new Error("Onbekende workflow.");
    }

    const { token, source } = readServerToken();
    if (!token) {
        throw new Error("Server-side GitHub token ontbreekt. Zet BOBOS_GITHUB_TOKEN in Vercel.");
    }

    const transport = await dispatchWithToken(workflow.id, token);
    return {
        label: workflow.label,
        transport,
        credentialSource: source,
    };
}

module.exports = {
    detectTransportMode,
    dispatchWorkflow,
    getWorkflow,
    isAllowedOrigin,
    readServerToken,
    sendError,
    sendJson,
    REPOSITORY,
};
