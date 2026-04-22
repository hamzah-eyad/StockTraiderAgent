"""
Plaid Link helper server — two roles in one:

  GET  http://localhost:8508?token=<link_token>
       Serves the full standalone Plaid Link HTML page.
       This page MUST run outside an iframe (Plaid requirement),
       so the dashboard opens it via webbrowser.open() / a new tab link.

  POST http://localhost:8508
       Receives the public_token from Plaid Link's onSuccess callback,
       exchanges it for a permanent access_token, and saves it to disk.
"""
from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

CALLBACK_PORT = 8508
_server_instance: HTTPServer | None = None


def _build_link_page(link_token: str) -> str:
    """Return a complete HTML page that runs Plaid Link at the top level (no iframe)."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Connect Your Bank — StockTraiderAgent</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0e1117;
      color: #fff;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0;
    }}
    .card {{
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 16px;
      padding: 40px 48px;
      max-width: 480px;
      width: 92%;
      text-align: center;
      box-shadow: 0 8px 32px #0008;
    }}
    .logo {{ font-size: 2.5rem; margin-bottom: 8px; }}
    h1 {{ color: #00d4aa; font-size: 1.4rem; margin: 0 0 12px; }}
    p  {{ color: #8b949e; font-size: 0.9rem; line-height: 1.6; margin: 0 0 10px; }}
    #btn {{
      display: inline-block;
      background: #00d4aa;
      color: #000;
      border: none;
      padding: 13px 30px;
      border-radius: 10px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      margin-top: 20px;
      transition: opacity .2s;
    }}
    #btn:disabled {{ opacity: .45; cursor: default; }}
    #status {{
      margin-top: 18px;
      min-height: 44px;
      font-size: 0.9rem;
      line-height: 1.5;
    }}
    .tip {{
      margin-top: 28px;
      font-size: 0.78rem;
      color: #484f58;
      border-top: 1px solid #21262d;
      padding-top: 18px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">🏦</div>
    <h1>Connect Your Bank</h1>
    <p>Your login goes directly to <strong>Plaid's</strong> secure servers.<br>
       This app never sees your bank password.</p>

    <button id="btn" onclick="handler.open()">Connect Your Bank Account</button>
    <div id="status"></div>

    <p class="tip">
      After linking, close this tab and click<br>
      <strong>🔄 Refresh Linked Banks</strong> in the dashboard.
    </p>
  </div>

  <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
  <script>
    function status(html, color) {{
      document.getElementById('status').innerHTML =
        '<span style="color:' + (color || '#8b949e') + '">' + html + '</span>';
    }}

    var handler = Plaid.create({{
      token: '{link_token}',
      onSuccess: function(public_token, metadata) {{
        var btn = document.getElementById('btn');
        btn.disabled = true;
        status('⏳ Saving your bank connection…', '#ff9900');

        var institution = (metadata && metadata.institution) || {{}};
        fetch('http://localhost:{CALLBACK_PORT}', {{
          method:  'POST',
          headers: {{'Content-Type': 'application/json'}},
          body:    JSON.stringify({{
            public_token: public_token,
            institution:  institution
          }})
        }})
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
          if (data.status === 'success') {{
            btn.textContent = '✓ Connected';
            status(
              '✅ <strong>' + (data.institution_name || 'Bank') +
              '</strong> linked!<br>' +
              '<span style="font-size:.85em">Return to the dashboard and click Refresh.</span>',
              '#00d4aa'
            );
          }} else {{
            status('❌ ' + (data.error || 'Unknown error'), '#ff4444');
            btn.disabled = false;
          }}
        }})
        .catch(function(err) {{
          status('❌ Connection error: ' + err.message, '#ff4444');
          btn.disabled = false;
        }});
      }},
      onExit: function(err) {{
        if (err) status('⚠️ ' + (err.display_message || 'Cancelled'), '#ff9900');
      }}
    }});

    // Auto-open as soon as the page loads
    window.addEventListener('load', function() {{ handler.open(); }});
  </script>
</body>
</html>"""


class _PlaidCallbackHandler(BaseHTTPRequestHandler):

    # ── Serve Plaid Link HTML page ────────────────────────────────────────
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        link_token = params.get("token", [""])[0]

        if not link_token:
            body = b"<h2>Missing ?token= parameter</h2>"
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = _build_link_page(link_token).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── CORS pre-flight ───────────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    # ── Receive public_token from Plaid Link JS ───────────────────────────
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            self._respond(400, {"error": "Invalid JSON"})
            return

        public_token = body.get("public_token", "")
        institution = body.get("institution", {})
        institution_name = (
            institution.get("name", "Unknown Bank")
            if isinstance(institution, dict) else "Unknown Bank"
        )

        if not public_token:
            self._respond(400, {"error": "No public_token provided"})
            return

        try:
            from mcp_servers.banking_server import exchange_and_save_real_token
            result = exchange_and_save_real_token(public_token, institution_name)
            self._respond(200, result)
        except Exception as e:
            logger.error(f"Plaid callback error: {e}", exc_info=True)
            self._respond(500, {"status": "error", "error": str(e)})

    # ── Helpers ───────────────────────────────────────────────────────────
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _respond(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Silence per-request noise in terminal


def start_callback_server():
    """Start the server as a daemon thread. Safe to call multiple times."""
    global _server_instance
    if _server_instance is not None:
        return
    try:
        server = HTTPServer(("localhost", CALLBACK_PORT), _PlaidCallbackHandler)
        _server_instance = server
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info(f"Plaid Link server started on http://localhost:{CALLBACK_PORT}")
    except OSError:
        logger.warning(f"Port {CALLBACK_PORT} already in use — server may already be running")


def is_running() -> bool:
    return _server_instance is not None


def link_page_url(link_token: str) -> str:
    """Full URL of the standalone Plaid Link page for a given link_token."""
    return f"http://localhost:{CALLBACK_PORT}?token={link_token}"

