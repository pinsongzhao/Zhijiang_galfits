#!/usr/bin/env python3
"""
Minimal Flask server to serve the static website folder and persist per-object inputs.

Usage:
    pip install flask
    python website/server.py

Endpoints:
- GET  /api/results        -> returns JSON mapping: { "<objid>": { ...payload... }, ... }
- POST /api/results        -> accepts JSON body:
    { "objid": "<id>", "payload": {...} }    (single object update)
    or
    { "bulk": [ { "objid": "...", "payload": {...} }, ... ] }  (bulk replace/merge)
The server stores data in data/fitting_results.json.

Warning: no authentication by default. Anyone who can reach the server can modify data.
Add auth or network restrictions for production.
"""
import os
import json
from flask import Flask, send_from_directory, jsonify, request, abort

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "fitting_results.json")
STATIC_DIR = APP_DIR  # serve files from website/ directory

os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')

def atomic_write(path, content_bytes):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(content_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        # corrupted file -> overwrite
        return {}

def save_data(mapping):
    try:
        atomic_write(DATA_FILE, json.dumps(mapping, indent=2, ensure_ascii=False).encode("utf-8"))
        return True
    except Exception as e:
        print("Failed to write data file:", e)
        return False

@app.route('/api/results', methods=['GET'])
def api_get_results():
    data = load_data()
    return jsonify(data)

@app.route('/api/results', methods=['POST'])
def api_post_results():
    if not request.is_json:
        return abort(400, description="Expected application/json")
    body = request.get_json()
    if not isinstance(body, dict):
        return abort(400, description="Invalid JSON body")
    current = load_data()

    # Bulk update: expect body.bulk = [ { objid, payload }, ... ]
    if 'bulk' in body:
        bulk = body.get('bulk') or []
        if not isinstance(bulk, list):
            return abort(400, description="Invalid bulk format")
        for entry in bulk:
            if not isinstance(entry, dict):
                continue
            objid = str(entry.get('objid', '')).strip()
            payload = entry.get('payload')
            if objid and isinstance(payload, dict):
                current[objid] = payload
        ok = save_data(current)
        if ok:
            return jsonify({"ok": True}), 200
        else:
            return abort(500, description="Failed to save data")

    # Single update: expect body.objid and body.payload
    objid = body.get('objid')
    payload = body.get('payload')
    if objid is None or payload is None or not isinstance(payload, dict):
        return abort(400, description="Expected { objid, payload } or { bulk: [...] }")
    objid = str(objid)
    current[objid] = payload
    ok = save_data(current)
    if ok:
        return jsonify({"ok": True}), 200
    else:
        return abort(500, description="Failed to save data")

# Serve the generated HTML and other static files from this directory
@app.route('/', defaults={'path': 'investigate_fitting_results.html'})
@app.route('/<path:path>')
def static_proxy(path):
    # Danger: this will serve files from the website/ folder. Restrict or harden as needed.
    safe_path = os.path.join(STATIC_DIR, path)
    if not os.path.exists(safe_path):
        return send_from_directory(STATIC_DIR, 'investigate_fitting_results.html')
    # send requested file
    return send_from_directory(STATIC_DIR, path)

if __name__ == '__main__':
    # Do not use Flask's dev server for production. Use gunicorn/uwsgi behind a proper server in production.
    print("Starting server on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
