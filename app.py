# app.py
# Purpose: Entrypoint - starts the idle monitor thread and the HTTP server.

import threading
from http.server import ThreadingHTTPServer

from core.constants import PORT
from core.firewall import firewall_worker
from core.handler import Handler
from core.idle import idle_monitor
from core.match_history import ensure_schema

if __name__ == "__main__":
    ensure_schema()
    threading.Thread(target=idle_monitor, daemon=True).start()
    threading.Thread(target=firewall_worker, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
