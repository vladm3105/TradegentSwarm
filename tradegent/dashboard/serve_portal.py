#!/usr/bin/env python3
"""
Tradegent Portal Server
Serves the landing page with links to all services.

Run: python dashboard/serve_portal.py
Opens: http://localhost:8000
"""
import http.server
import socketserver
import os
import webbrowser
from pathlib import Path

PORT = 8000
DIRECTORY = Path(__file__).parent

os.chdir(DIRECTORY)

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def do_GET(self):
        if self.path == '/' or self.path == '':
            self.path = '/portal.html'
        return super().do_GET()

    def log_message(self, format, *args):
        # Quieter logging
        pass

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"╔══════════════════════════════════════════╗")
        print(f"║  Tradegent Portal                        ║")
        print(f"║  http://localhost:{PORT}                    ║")
        print(f"╚══════════════════════════════════════════╝")
        print()
        print("Services:")
        print(f"  • Portal:     http://localhost:{PORT}")
        print(f"  • Streamlit:  http://localhost:8501")
        print(f"  • Metabase:   http://localhost:3001")
        print(f"  • Neo4j:      http://localhost:7475")
        print()
        print("Press Ctrl+C to stop")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
