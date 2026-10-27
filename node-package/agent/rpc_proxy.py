"""Minimal read-only JSON-RPC gateway used by the browser Observer."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


UPSTREAM = os.getenv("BESU_RPC_URL", "http://besu-validator-1:8545")
METADATA_API = os.getenv("METADATA_API_URL", "").rstrip("/")
METADATA_HOST_HEADER = os.getenv("METADATA_HOST_HEADER") or urllib.parse.urlsplit(METADATA_API).netloc
PORT = int(os.getenv("RPC_PROXY_PORT", "8080"))
MAX_BODY = 64 * 1024
ALLOWED_METHODS = {
    "eth_chainId",
    "eth_blockNumber",
    "eth_getBlockByNumber",
    "eth_getTransactionByHash",
    "eth_getTransactionReceipt",
    "eth_syncing",
    "net_peerCount",
    "qbft_getValidatorsByBlockNumber",
    "admin_nodeInfo",
    "admin_peers",
}
ALLOWED_METADATA_GET = (
    "/api/v1/me/",
    "/api/v1/observer/nfts/",
    "/api/v1/observer/analytics/",
    "/api/v1/observer/search/",
)
ALLOWED_METADATA_POST = {"/api/v1/auth/token/", "/api/v1/auth/token/refresh/"}


class Handler(BaseHTTPRequestHandler):
    server_version = "ChainControlReadOnlyRPC/1.0"

    def send_json(self, status: int, document) -> None:
        body = json.dumps(document).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            return self.proxy_metadata("POST")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY:
                return self.send_json(413, {"error": {"code": -32600, "message": "Invalid request size"}})
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or payload.get("method") not in ALLOWED_METHODS or not isinstance(payload.get("params", []), list):
                request_id = payload.get("id") if isinstance(payload, dict) else None
                return self.send_json(403, {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method is not available through the read-only Observer"}})
            request = urllib.request.Request(UPSTREAM, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=12) as response:
                result = json.load(response)
            return self.send_json(200, result)
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": {"code": -32700, "message": "Invalid JSON"}})
        except (OSError, urllib.error.URLError, urllib.error.HTTPError):
            return self.send_json(502, {"error": {"code": -32000, "message": "Local Besu is unavailable"}})

    def metadata_allowed(self, method: str) -> bool:
        path = urllib.parse.urlsplit(self.path).path
        if method == "POST":
            return path in ALLOWED_METADATA_POST
        if path in ALLOWED_METADATA_GET:
            return True
        return path.startswith("/api/v1/observer/nfts/") and path.removeprefix("/api/v1/observer/nfts/").strip("/").isdigit()

    def proxy_metadata(self, method: str) -> None:
        if not METADATA_API or not self.metadata_allowed(method):
            return self.send_json(403, {"error": {"code": "METADATA_ROUTE_DENIED", "message": "This metadata route is not available through the Observer."}})
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            return self.send_json(413, {"error": {"code": "REQUEST_TOO_LARGE", "message": "Request is too large."}})
        body = self.rfile.read(length) if length else None
        headers = {"Accept": "application/json"}
        if METADATA_HOST_HEADER:
            headers["Host"] = METADATA_HOST_HEADER
        if self.headers.get("Content-Type"):
            headers["Content-Type"] = self.headers["Content-Type"]
        if self.headers.get("Authorization"):
            headers["Authorization"] = self.headers["Authorization"]
        request = urllib.request.Request(f"{METADATA_API}{self.path}", data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                result, status = response.read(), response.status
                content_type = response.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as exc:
            result, status = exc.read(), exc.code
            content_type = exc.headers.get("Content-Type", "application/json")
        except (OSError, urllib.error.URLError):
            return self.send_json(503, {"error": {"code": "METADATA_UNAVAILABLE", "message": "Django metadata is temporarily unavailable."}})
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(result)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/"):
            return self.proxy_metadata("GET")
        self.send_json(405, {"error": {"code": -32600, "message": "POST required"}})

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
