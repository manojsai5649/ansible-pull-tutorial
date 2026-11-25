
#!/usr/bin/env python3

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import sqlite3
import urllib.parse
import os

# Server configuration
DB_PATH = "/var/lib/node-telemetry/metrics.db"
HOST = "0.0.0.0"
PORT = 8080

# Create database directory and table
def initialize_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS node_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,
            hostname TEXT NOT NULL,
            os_version TEXT NOT NULL,
            cpu_vcpus INTEGER NOT NULL,
            memory_total_mb INTEGER NOT NULL,
            environment TEXT NOT NULL,
            owner_label TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# Dashboard HTML
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Node Telemetry Dashboard</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f1f5f9;
    color: #1e293b;
}

header {
    background: #172554;
    color: white;
    padding: 25px;
    text-align: center;
}

.container {
    max-width: 1100px;
    margin: 30px auto;
    padding: 20px;
}

.card {
    background: white;
    padding: 25px;
    margin-bottom: 25px;
    border-radius: 12px;
    box-shadow: 0 3px 12px rgba(0,0,0,0.08);
}

h2 {
    color: #1d4ed8;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 18px;
}

label {
    font-weight: bold;
}

input {
    width: 100%;
    padding: 11px;
    margin-top: 7px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
}

button {
    margin-top: 20px;
    padding: 12px 25px;
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
}

button:hover {
    background: #1e40af;
}

.message {
    color: #15803d;
    font-weight: bold;
    margin-bottom: 15px;
}

.table-wrapper {
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
    background: white;
}

th {
    background: #1e3a8a;
    color: white;
}

th, td {
    padding: 12px;
    border: 1px solid #e2e8f0;
    text-align: center;
}

tr:nth-child(even) {
    background: #f8fafc;
}

footer {
    text-align: center;
    padding: 20px;
    color: #64748b;
}

@media(max-width: 650px) {
    .form-grid {
        grid-template-columns: 1fr;
    }
}
</style>
</head>

<body>

<header>
    <h1>Node Telemetry Dashboard</h1>
    <p>Infrastructure Monitoring Using Ansible and Python</p>
</header>

<div class="container">

<div class="card">
    <h2>Add Node Snapshot Entry</h2>

    <p class="message">{message}</p>

    <form method="POST" action="/add">

        <div class="form-grid">

            <label>
                Hostname
                <input name="hostname" value="{hostname}" required maxlength="255">
            </label>

            <label>
                OS Version
                <input name="os_version" value="{os_version}" required maxlength="255">
            </label>

            <label>
                CPU vCPUs
                <input type="number" name="cpu_vcpus" value="2"
                       min="1" max="4096" required>
            </label>

            <label>
                Memory (MB)
                <input type="number" name="memory_total_mb" value="908"
                       min="1" required>
            </label>

            <label>
                Environment
                <input name="environment" value="staging" required maxlength="100">
            </label>

            <label>
                Owner Label
                <input name="owner_label" value="platform-team" required maxlength="100">
            </label>

        </div>

        <button type="submit">Save Node Snapshot</button>

    </form>
</div>

<div class="card">
    <h2>Recent Node Records</h2>

    <div class="table-wrapper">
    <table>
        <tr>
            <th>ID</th>
            <th>Recorded At</th>
            <th>Hostname</th>
            <th>OS</th>
            <th>CPU</th>
            <th>RAM (MB)</th>
            <th>Environment</th>
            <th>Owner</th>
        </tr>

        {rows}

    </table>
    </div>
</div>

</div>

<footer>
    Node Telemetry System | Powered by Python, SQLite and Ansible
</footer>

</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):

    def render_page(self, message="", status=200):

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        cur.execute("""
            SELECT id, recorded_at, hostname, os_version,
                   cpu_vcpus, memory_total_mb, environment, owner_label
            FROM node_snapshots
            ORDER BY id DESC
            LIMIT 10
        """)

        records = cur.fetchall()
        conn.close()

        rows_html = ""

        for record in records:
            rows_html += "<tr>"
            for value in record:
                rows_html += f"<td>{html.escape(str(value))}</td>"
            rows_html += "</tr>"

        if not records:
            rows_html = '<tr><td colspan="8">No records available</td></tr>'

        page = HTML_TEMPLATE.format(
            hostname=html.escape(os.uname().nodename),
            os_version=html.escape("Linux"),
            message=html.escape(message),
            rows=rows_html
        ).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def do_GET(self):
        self.render_page()

    def do_POST(self):

        try:
            length = int(self.headers.get("Content-Length", "0"))

            if length <= 0 or length > 16384:
                raise ValueError("Invalid request size")

            body = self.rfile.read(length).decode("utf-8")
            data = urllib.parse.parse_qs(body)

            hostname = data.get("hostname", [""])[0].strip()
            os_version = data.get("os_version", [""])[0].strip()
            cpu_vcpus = int(data.get("cpu_vcpus", ["1"])[0])
            memory_total_mb = int(data.get("memory_total_mb", ["0"])[0])
            environment = data.get("environment", ["staging"])[0].strip()
            owner_label = data.get("owner_label", ["platform-team"])[0].strip()

            if not all([hostname, os_version, environment, owner_label]):
                raise ValueError("All fields are required")

            if not (1 <= cpu_vcpus <= 4096 and memory_total_mb > 0):
                raise ValueError("Invalid CPU or memory value")

            recorded_at = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

            conn = sqlite3.connect(DB_PATH)

            conn.execute("""
                INSERT INTO node_snapshots (
                    recorded_at, hostname, os_version,
                    cpu_vcpus, memory_total_mb,
                    environment, owner_label
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                recorded_at,
                hostname,
                os_version,
                cpu_vcpus,
                memory_total_mb,
                environment,
                owner_label
            ))

            conn.commit()
            conn.close()

            self.render_page("Node snapshot saved successfully!")

        except (ValueError, UnicodeDecodeError) as error:
            self.render_page(f"Error: {error}", status=400)

        except sqlite3.Error:
            self.render_page("Database error. Please try again.", status=500)


if __name__ == "__main__":

    initialize_database()

    print("======================================")
    print(" Node Telemetry Dashboard Started")
    print("======================================")
    print(f" Server: http://localhost:{PORT}")
    print(f" Database: {DB_PATH}")

    server = HTTPServer((HOST, PORT), Handler)
    server.serve_forever()
