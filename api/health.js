"use strict";

const {
    detectTransportMode,
    isAllowedOrigin,
    REPOSITORY,
    sendError,
    sendJson,
} = require("./_lib/refresh");

module.exports = async function handler(req, res) {
    const origin = req.headers.origin || "";

    if (origin && !isAllowedOrigin(origin)) {
        sendError(res, 403, "Origin niet toegestaan.", origin);
        return;
    }

    if (req.method === "OPTIONS") {
        sendJson(
            res,
            204,
            {},
            origin,
        );
        return;
    }

    if (req.method !== "GET") {
        sendError(res, 405, "Methode niet toegestaan.", origin);
        return;
    }

    sendJson(
        res,
        200,
        {
            ok: true,
            status: "ready",
            transport: detectTransportMode(),
            repo: `${REPOSITORY.owner}/${REPOSITORY.repo}`,
        },
        origin,
    );
};
