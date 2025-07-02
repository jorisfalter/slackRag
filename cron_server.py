#!/usr/bin/env python3
import http.server
import socketserver
import threading
import subprocess
import time
import os

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "slack-cron"}')
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 3000))
    with socketserver.TCPServer(("", port), HealthHandler) as httpd:
        print(f"Health check server running on port {port}")
        httpd.serve_forever()

def run_cron():
    print("Starting cron daemon...")
    subprocess.run(["cron", "-f"])

if __name__ == "__main__":
    print("🕒 Starting Slack Cron Service")
    print("   - Health check endpoint: /health")
    print("   - Cron job: Daily at 9:00 AM UTC")
    
    # Start HTTP server in background
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Give the server a moment to start
    time.sleep(2)
    
    # Run cron in foreground
    run_cron() 