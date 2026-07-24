"use strict";

const {
    dispatchWorkflow,
    getWorkflow,
    isAllowedOrigin,
    sendError,
    sendJson,
} = require("../_lib/refresh");

module.exports = async function handler(req, res) {
    const origin = req.headers.origin || "";

    if (origin && !isAllowedOrigin(origin)) {
        sendError(res, 403, "Origin niet toegestaan.", origin);
        return;
    }

    if (req.method === "OPTIONS") {
        sendJson(res, 204, {}, origin);
        return;
    }

    if (req.method !== "POST") {
        sendError(res, 405, "Methode niet toegestaan.", origin);
        return;
    }

    const targetKey = String(req.query.target || "").trim().toLowerCase();
    const workflow = getWorkflow(targetKey);
    if (!workflow) {
        sendError(res, 404, "Onbekende workflow.", origin);
        return;
    }

    try {
        const result = await dispatchWorkflow(targetKey);
        sendJson(
            res,
            200,
            {
                ok: true,
                target: targetKey,
                transport: result.transport,
                message: `${result.label} gestart via ${result.credentialSource}. GitHub Actions pakt dit nu op; ververs BobOS over ongeveer een minuut.`,
            },
            origin,
        );
    } catch (error) {
        sendError(
            res,
            502,
            error instanceof Error
                ? error.message
                : `${workflow.label} kon niet worden gestart.`,
            origin,
        );
    }
};
