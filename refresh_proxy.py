from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib import error, parse, request

REPOSITORY = {
    "owner": "mailbvandongen-eng",
    "repo": "bobos",
    "ref": "main",
    "api_version": "2022-11-28",
}

WORKFLOWS = {
    "news": {
        "id": "news.yml",
        "label": "Nieuws",
    },
    "sport": {
        "id": "sport.yml",
        "label": "Sport",
    },
    "detectie": {
        "id": "detectie.yml",
        "label": "Detectie",
    },
    "vissen": {
        "id": "vissen.yml",
        "label": "Vissen",
    },
}

TOKEN_ENV_KEYS = (
    "BOBOS_GITHUB_TOKEN",
    "GITHUB_TOKEN",
    "GH_TOKEN",
)


def read_server_token() -> tuple[str, str]:
    for key in TOKEN_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            return value, key
    return "", ""


def is_origin_allowed(origin: str) -> bool:
    if not origin:
        return True

    parsed = parse.urlparse(origin)
    hostname = (parsed.hostname or "").lower()

    if parsed.scheme == "https" and hostname == "mailbvandongen-eng.github.io":
        return True

    if parsed.scheme == "http" and hostname in {"127.0.0.1", "localhost"}:
        return True

    return False


def gh_path() -> str:
    return shutil.which("gh") or ""


def gh_is_ready() -> tuple[bool, str]:
    executable = gh_path()
    if not executable:
        return False, "GitHub CLI niet gevonden. Installeer gh of zet BOBOS_GITHUB_TOKEN."

    result = subprocess.run(
        [executable, "auth", "status"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        return False, "GitHub CLI is niet ingelogd. Voer gh auth login uit of zet BOBOS_GITHUB_TOKEN."

    return True, ""


def detect_transport_mode() -> str:
    token, _ = read_server_token()
    if token:
        return "token"

    ready, _ = gh_is_ready()
    if ready:
        return "gh"

    return "unavailable"


def parse_error_message(raw_body: bytes) -> str:
    body_text = raw_body.decode("utf-8", errors="replace").strip()
    if not body_text:
        return ""

    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError:
        return body_text

    return str(payload.get("message") or "").strip()


def dispatch_with_token(workflow_id: str, token: str) -> str:
    dispatch_url = (
        f"https://api.github.com/repos/{REPOSITORY['owner']}/{REPOSITORY['repo']}"
        f"/actions/workflows/{workflow_id}/dispatches"
    )
    payload = json.dumps({"ref": REPOSITORY["ref"]}).encode("utf-8")
    req = request.Request(
        dispatch_url,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": REPOSITORY["api_version"],
        },
    )

    try:
        with request.urlopen(req, timeout=20) as response:
            if response.status not in {200, 201, 202, 204}:
                raise RuntimeError(f"GitHub gaf status {response.status} terug.")
    except error.HTTPError as exc:
        message = parse_error_message(exc.read())
        raise RuntimeError(message or f"GitHub gaf status {exc.code} terug.") from exc
    except error.URLError as exc:
        raise RuntimeError(f"GitHub is niet bereikbaar: {exc.reason}.") from exc

    return "token"


def dispatch_with_gh(workflow_id: str) -> str:
    ready, message = gh_is_ready()
    if not ready:
        raise RuntimeError(message)

    executable = gh_path()
    result = subprocess.run(
        [
            executable,
            "workflow",
            "run",
            workflow_id,
            "--repo",
            f"{REPOSITORY['owner']}/{REPOSITORY['repo']}",
            "--ref",
            REPOSITORY["ref"],
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(message or "GitHub workflow kon niet worden gestart via gh.")

    return "gh"


def dispatch_workflow(target_key: str) -> dict[str, Any]:
    workflow = WORKFLOWS.get(target_key)
    if not workflow:
        raise KeyError(target_key)

    token, token_key = read_server_token()

    if token:
        transport = dispatch_with_token(workflow["id"], token)
        return {
            "label": workflow["label"],
            "transport": transport,
            "credential_source": token_key,
        }

    transport = dispatch_with_gh(workflow["id"])
    return {
        "label": workflow["label"],
        "transport": transport,
        "credential_source": "gh auth",
    }


class RefreshProxyHandler(BaseHTTPRequestHandler):
    server_version = "BobOSRefreshProxy/0.1"
    protocol_version = "HTTP/1.1"

    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin and not is_origin_allowed(origin):
            self.send_error_json(403, {"ok": False, "message": "Origin niet toegestaan."}, origin)
            return

        self.send_json(204, {}, origin)

    def do_GET(self) -> None:
        origin = self.headers.get("Origin", "")
        parsed = parse.urlparse(self.path)

        if parsed.path != "/health":
            self.send_error_json(404, {"ok": False, "message": "Onbekend endpoint."}, origin)
            return

        self.send_json(
            200,
            {
                "ok": True,
                "status": "ready",
                "transport": detect_transport_mode(),
                "repo": f"{REPOSITORY['owner']}/{REPOSITORY['repo']}",
            },
            origin,
        )

    def do_POST(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin and not is_origin_allowed(origin):
            self.send_error_json(403, {"ok": False, "message": "Origin niet toegestaan."}, origin)
            return

        parsed = parse.urlparse(self.path)
        if not parsed.path.startswith("/dispatch/"):
            self.send_error_json(404, {"ok": False, "message": "Onbekend endpoint."}, origin)
            return

        target_key = parsed.path.rsplit("/", 1)[-1].strip().lower()
        if target_key not in WORKFLOWS:
            self.send_error_json(404, {"ok": False, "message": "Onbekende workflow."}, origin)
            return

        try:
            self.read_request_body()
            dispatch_result = dispatch_workflow(target_key)
        except KeyError:
            self.send_error_json(404, {"ok": False, "message": "Onbekende workflow."}, origin)
            return
        except RuntimeError as exc:
            self.send_error_json(502, {"ok": False, "message": str(exc)}, origin)
            return
        except Exception as exc:  # pragma: no cover - defensive fallback
            self.send_error_json(500, {"ok": False, "message": f"Interne fout: {exc}"}, origin)
            return

        self.send_json(
            200,
            {
                "ok": True,
                "target": target_key,
                "transport": dispatch_result["transport"],
                "message": (
                    f"{dispatch_result['label']} gestart via {dispatch_result['credential_source']}. "
                    "GitHub Actions pakt dit nu op; ververs BobOS over ongeveer een minuut."
                ),
            },
            origin,
        )

    def read_request_body(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length <= 0:
            return
        self.rfile.read(content_length)

    def send_json(self, status_code: int, payload: dict[str, Any], origin: str = "") -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")

        if origin and is_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

        self.end_headers()
        if body:
            self.wfile.write(body)

    def send_error_json(self, status_code: int, payload: dict[str, Any], origin: str = "") -> None:
        self.send_json(status_code, payload, origin)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[refresh_proxy] {self.address_string()} - {fmt % args}")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BobOS tokenloze refreshservice")
    parser.add_argument("--host", default="127.0.0.1", help="Host om op te luisteren")
    parser.add_argument("--port", default=8787, type=int, help="Poort om op te luisteren")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), RefreshProxyHandler)

    transport = detect_transport_mode()
    print(f"BobOS refresh proxy draait op http://{args.host}:{args.port}")
    if transport == "gh":
        print("Authenticatie: gebruikt lokale gh login.")
    elif transport == "token":
        print("Authenticatie: gebruikt server-side GitHub token.")
    else:
        print("Authenticatie: nog niet klaar. Gebruik gh auth login of zet BOBOS_GITHUB_TOKEN.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
