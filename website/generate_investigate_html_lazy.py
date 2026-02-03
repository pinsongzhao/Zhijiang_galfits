#!/usr/bin/env python3
"""
generate_investigate_html_lazy.py

Generates investigate_fitting_results.html which references PNGs on jsDelivr (primary)
and uses an IntersectionObserver + concurrency-limited loader with fallbacks to reduce
network load and improve page responsiveness.

This modified generator also emits client-side code that:
- fetches existing persisted per-object inputs from the server (GET /api/results)
- autosaves drafts to sessionStorage and debounced POSTs to the server (POST /api/results)
- keeps styles and features unchanged
"""
import os
import json
import urllib.parse

# === Configuration ===
source_directory = "/mnt/f/webpage5/website"
output_html = "investigate_fitting_results.html"

# Primary CDN (fast, public)
jsdelivr_base = "https://cdn.jsdelivr.net/gh/pinsongzhao/Zhijiang_galfits@main/website"
# Raw GitHub (fallback)
github_raw_base = "https://raw.githubusercontent.com/pinsongzhao/Zhijiang_galfits/main/website"
# Additional mirror fallback
fastgit_base = "https://raw.fastgit.org/pinsongzhao/Zhijiang_galfits/main/website"

# Loader tuning
CONCURRENCY = 4                 # number of images to download at once
PRELOAD_ROOT_MARGIN = "400px"   # when image is within this margin, start loading
PLACEHOLDER_SVG = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'/>"
)

# Where HTML will be written (used for relative local links)
html_output_path = os.path.abspath(output_html)
html_dir = os.path.dirname(html_output_path) if os.path.dirname(html_output_path) else os.getcwd()

def make_local_src(path):
    """Return a relative URL from the HTML file to the given local path if possible.
    Falls back to file:// absolute URL. URL-encodes path components."""
    abs_path = os.path.abspath(path)
    try:
        rel_path = os.path.relpath(abs_path, start=html_dir)
        rel_posix = rel_path.replace(os.path.sep, "/")
        parts = rel_posix.split("/")
        return "/".join(urllib.parse.quote(p) for p in parts)
    except Exception:
        abs_posix = abs_path.replace(os.path.sep, "/")
        return "file://" + urllib.parse.quote(abs_posix)

# === Discover object ids ===
objids = set()
for filename in os.listdir(source_directory):
    if not filename.startswith("obj"):
        continue
    if filename.endswith("image_fit.png"):
        objid = filename[len("obj") : -len("image_fit.png")]
        objids.add(objid)
    elif filename.endswith("SED_model.png"):
        objid = filename[len("obj") : -len("SED_model.png")]
        objids.add(objid)
    elif filename.endswith(".gssummary"):
        objid = filename[len("obj") : -len(".gssummary")]
        objids.add(objid)

# === HTML header and styles (unchanged layout) ===
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fitting Results Investigation</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f8f8f8;
            color: #333;
            line-height: 1.6;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px auto;
            background: white;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }

        th, td {
            padding: 15px;
            text-align: center;
            border: 1px solid #ddd;
            vertical-align: top;
        }

        th {
            background-color: #1976d2;
            color: white;
        }

        td.image-section img {
            max-width: 400px;
            max-height: 450px;
            display: block;
            margin: 0 auto;
            object-fit: contain;
            background: #fff;
        }

        .gssummary-section {
            display: block;
            max-width: 650px;
            max-height: 450px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 10px;
            background: #f9f9f9;
            font-size: 14px;
            text-align: left;
            word-wrap: break-word;
        }

        .rating-section, .comment-section {
            text-align: left;
            padding: 8px 15px;
        }

        .comment-section h4 {
            margin-top: 10px;
        }

        textarea {
            width: 95%;
            height: 70px;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #ccc;
            margin-top: 10px;
        }

        .save-button-container {
            text-align: center;
            margin: 20px 0;
        }

        .save-button {
            padding: 12px 20px;
            background-color: #1976d2;
            color: white;
            font-size: 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }

        .save-button:hover {
            background-color: #145ca8;
        }
    </style>
</head>
<body>
    <h1 style="text-align: center;">Fitting Results Investigation</h1>
    <table>
        <thead>
            <tr>
                <th>Object ID</th>
                <th>Image Fit</th>
                <th>SED Model</th>
                <th>Summary</th>
            </tr>
        </thead>
        <tbody>
"""

# === Build rows with lazy/queued loading attributes ===
for objid in sorted(objids, key=lambda x: (len(x), x)):
    image_fit_filename = f"obj{objid}image_fit.png"
    sed_model_filename = f"obj{objid}SED_model.png"
    gssummary_filename = f"obj{objid}.gssummary"

    image_fit_path = os.path.join(source_directory, image_fit_filename)
    sed_model_path = os.path.join(source_directory, sed_model_filename)
    gssummary_path = os.path.join(source_directory, gssummary_filename)

    # Ordered fallbacks: primary jsDelivr, then raw, then fastgit, then local (if exists)
    image_fit_jsdel = f"{jsdelivr_base}/{image_fit_filename}"
    sed_model_jsdel = f"{jsdelivr_base}/{sed_model_filename}"
    image_fit_raw = f"{github_raw_base}/{image_fit_filename}"
    sed_model_raw = f"{github_raw_base}/{sed_model_filename}"
    image_fit_fastgit = f"{fastgit_base}/{image_fit_filename}"
    sed_model_fastgit = f"{fastgit_base}/{sed_model_filename}"

    image_fallbacks = [image_fit_jsdel, image_fit_raw, image_fit_fastgit]
    sed_fallbacks = [sed_model_jsdel, sed_model_raw, sed_model_fastgit]

    if os.path.exists(image_fit_path):
        image_local = make_local_src(image_fit_path)
        image_fallbacks.append(image_local)
    if os.path.exists(sed_model_path):
        sed_local = make_local_src(sed_model_path)
        sed_fallbacks.append(sed_local)

    image_fallbacks_json = json.dumps(image_fallbacks)
    sed_fallbacks_json = json.dumps(sed_fallbacks)

    # Read gssummary locally (embed text)
    gssummary_content = ""
    if os.path.exists(gssummary_path):
        try:
            with open(gssummary_path, "r", encoding="utf-8", errors="ignore") as tf:
                gssummary_content = tf.read().replace("\n", "<br>")
        except Exception:
            gssummary_content = ""

    # Use tiny svg placeholder initially to avoid starting downloads; data-srcs holds candidates
    image_fit_tag = (
        f'<img decoding="async" src="{PLACEHOLDER_SVG}" data-srcs=\'{image_fallbacks_json}\' '
        f'data-raw="{image_fit_jsdel}" alt="Image Fit" class="deferred-image">'
    )
    sed_model_tag = (
        f'<img decoding="async" src="{PLACEHOLDER_SVG}" data-srcs=\'{sed_fallbacks_json}\' '
        f'data-raw="{sed_model_jsdel}" alt="SED Model" class="deferred-image">'
    )

    html_content += f"""
    <tr>
        <td rowspan="2">ID{objid}</td>
        <td class="image-section">
            {image_fit_tag}
        </td>
        <td class="image-section">
            {sed_model_tag}
        </td>
        <td class="gssummary-section">
            {gssummary_content if gssummary_content else "GSSummary Not Available"}
        </td>
    </tr>
    <tr>
        <td colspan="3">
            <div class="rating-section">
                <h3>Rating</h3>
                <input type="radio" id="good-{objid}" name="rating-{objid}" value="Good">
                <label for="good-{objid}">Good</label>
                <input type="radio" id="bad-{objid}" name="rating-{objid}" value="Bad">
                <label for="bad-{objid}">Bad</label>
            </div>
            <div class="comment-section">
                <h4>Noticed Fitting Problems:</h4>
                <textarea id="noticed-{objid}" placeholder="Describe any fitting problems..."></textarea>
                <h4>Next Step:</h4>
                <textarea id="nextstep-{objid}" placeholder="Define next steps for investigation..."></textarea>
                <h4>Reasons:</h4>
                <textarea id="reasons-{objid}" placeholder="Provide detailed reasons, if any..."></textarea>
            </div>
        </td>
    </tr>
    """

# === JS loader: IntersectionObserver + concurrency queue + fallback retries ===
# This block is extended to fetch /api/results on load and POST updates to /api/results so data
# persists across browser restarts and is visible to all visitors.
html_content += f"""
        </tbody>
    </table>
    <div class="save-button-container">
        <button class="save-button" id="save-button">Save Results</button>
    </div>

    <script>
    (function() {{
      const CONCURRENCY = {CONCURRENCY};
      const observerOptions = {{
        root: null,
        rootMargin: '{PRELOAD_ROOT_MARGIN}',
        threshold: 0.01
      }};

      // Queue & concurrency control
      const loadQueue = [];
      let activeLoads = 0;

      function scheduleLoad(img) {{
        loadQueue.push(img);
        processQueue();
      }}

      function processQueue() {{
        if (activeLoads >= CONCURRENCY) return;
        const img = loadQueue.shift();
        if (!img) return;
        activeLoads++;
        loadImageWithFallbacks(img).finally(() => {{
          activeLoads--;
          processQueue();
        }});
      }}

      // Attempt to load image from list of urls in order (data-srcs JSON array)
      function loadImageWithFallbacks(img) {{
        return new Promise((resolve) => {{
          let urls = [];
          try {{
            urls = JSON.parse(img.getAttribute('data-srcs') || '[]');
          }} catch (e) {{
            urls = [];
          }}
          let idx = 0;

          function tryNext() {{
            if (idx >= urls.length) {{
              // failed all, replace with a small link
              const raw = img.getAttribute('data-raw') || '';
              img.style.display = 'none';
              const d = document.createElement('div');
              d.innerHTML = '<a href="' + raw + '" target="_blank" rel="noopener noreferrer">Open expected image</a>';
              img.parentNode.appendChild(d);
              resolve(false);
              return;
            }}
            const url = urls[idx++];
            // Create a temporary image for probing (so we can attach load/error)
            const probe = new Image();
            probe.decoding = 'async';
            probe.onload = function() {{
              // success: set real img.src to this url
              img.src = url;
              // remove placeholder attributes to avoid reloading
              img.removeAttribute('data-srcs');
              resolve(true);
            }};
            probe.onerror = function() {{
              // try next
              tryNext();
            }};
            // Start request
            probe.src = url;
          }}

          tryNext();
        }});
      }}

      // IntersectionObserver to defer loads until near viewport
      const observer = new IntersectionObserver((entries) => {{
        entries.forEach(entry => {{
          if (entry.isIntersecting) {{
            const img = entry.target;
            observer.unobserve(img);
            scheduleLoad(img);
          }}
        }});
      }}, observerOptions);

      // Initialize: observe all deferred-image elements
      document.addEventListener('DOMContentLoaded', function() {{
        const imgs = document.querySelectorAll('img.deferred-image');
        imgs.forEach(img => {{
          observer.observe(img);
        }});

        // Also kick-start visible images immediately
        window.requestAnimationFrame(() => {{
          processQueue();
        }});

        // After DOM ready, fetch persisted results from server and restore them,
        // then attach autosave handlers that POST updates to the server.
        loadPersistedFromServer().then(() => {{
          restoreAllAndAttachHandlers();
        }});
      }});

      // --- persistence: sessionStorage + server-side store (so all visitors see latest) ---
      function debounce(fn, wait) {{
        let t;
        return function(...args) {{
          clearTimeout(t);
          t = setTimeout(() => fn.apply(this, args), wait);
        }};
      }}

      function draftKey(objid) {{
        return 'fitting:' + objid;
      }}

      // Send a single object's payload to server (debounced on the client)
      function pushDraftToServer(objid, payload) {{
        // POST { objid: "...", payload: {...} } to /api/results
        fetch('/api/results', {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json'
          }},
          body: JSON.stringify({{ objid: String(objid), payload: payload }})
        }}).catch(err => {{
          console.warn('Failed to push draft to server for', objid, err);
        }});
      }}

      function saveDraft(objid) {{
        try {{
          const good = document.getElementById('good-' + objid);
          const bad = document.getElementById('bad-' + objid);
          const noticed = document.getElementById('noticed-' + objid);
          const nextStep = document.getElementById('nextstep-' + objid);
          const reasons = document.getElementById('reasons-' + objid);
          if (!noticed || !nextStep || !reasons) return;
          const payload = {{
            rating: good && good.checked ? 'Good' : bad && bad.checked ? 'Bad' : 'Not Rated',
            noticed: noticed.value,
            nextStep: nextStep.value,
            reasons: reasons.value,
            savedAt: new Date().toISOString()
          }};
          // save locally for quick reload in same tab
          try {{
            sessionStorage.setItem(draftKey(objid), JSON.stringify(payload));
          }} catch (e) {{
            // ignore sessionStorage errors
          }}
          // push to server so all visitors will see it
          pushDraftToServer(objid, payload);
        }} catch (e) {{
          console.warn('Could not save draft for', objid, e);
        }}
      }}

      const saveDraftDebounced = debounce(saveDraft, 250);

      function restoreDraft(objid) {{
        try {{
          // Prefer server-supplied persisted data populated earlier (serverDataCache),
          // but fall back to sessionStorage if no server data exists.
          if (window.__serverData && window.__serverData[objid]) {{
            applyPayloadToDom(objid, window.__serverData[objid]);
            return;
          }}
          const raw = sessionStorage.getItem(draftKey(objid));
          if (!raw) return;
          const payload = JSON.parse(raw);
          if (!payload) return;
          applyPayloadToDom(objid, payload);
        }} catch (e) {{
          console.warn('Could not restore draft for', objid, e);
        }}
      }}

      function applyPayloadToDom(objid, payload) {{
        try {{
          const good = document.getElementById('good-' + objid);
          const bad = document.getElementById('bad-' + objid);
          const noticed = document.getElementById('noticed-' + objid);
          const nextStep = document.getElementById('nextstep-' + objid);
          const reasons = document.getElementById('reasons-' + objid);
          if (!noticed || !nextStep || !reasons) return;
          if (good && bad) {{
            if (payload.rating === 'Good') {{ good.checked = true; }}
            else if (payload.rating === 'Bad') {{ bad.checked = true; }}
            else {{ good.checked = bad.checked = false; }}
          }}
          noticed.value = payload.noticed || '';
          nextStep.value = payload.nextStep || '';
          reasons.value = payload.reasons || '';
        }} catch(e) {{
          console.warn('applyPayloadToDom failed for', objid, e);
        }}
      }}

      function attachAutoSaveHandlers(objid) {{
        const good = document.getElementById('good-' + objid);
        const bad = document.getElementById('bad-' + objid);
        const noticed = document.getElementById('noticed-' + objid);
        const nextStep = document.getElementById('nextstep-' + objid);
        const reasons = document.getElementById('reasons-' + objid);
        if (good) good.addEventListener('change', () => saveDraftDebounced(objid));
        if (bad) bad.addEventListener('change', () => saveDraftDebounced(objid));
        if (noticed) noticed.addEventListener('input', () => saveDraftDebounced(objid));
        if (nextStep) nextStep.addEventListener('input', () => saveDraftDebounced(objid));
        if (reasons) reasons.addEventListener('input', () => saveDraftDebounced(objid));
      }}

      function restoreAllAndAttachHandlers() {{
        const rows = document.querySelectorAll("tbody tr:nth-child(2n+1)");
        rows.forEach(function (row) {{
          const objid = row.querySelector("td").innerText.replace("ID", "").trim();
          if (!objid) return;
          restoreDraft(objid);
          attachAutoSaveHandlers(objid);
        }});
      }}

      // Load persisted data map from server and cache it in window.__serverData
      function loadPersistedFromServer() {{
        return fetch('/api/results', {{ credentials: 'same-origin' }})
          .then(resp => {{
            if (!resp.ok) throw new Error('Failed to fetch persisted results: ' + resp.status);
            return resp.json();
          }})
          .then(json => {{
            window.__serverData = json || {{}};
          }})
          .catch(err => {{
            console.warn('Could not load persisted results from server', err);
            window.__serverData = {{}};
          }});
      }}

      // Optional: allow convenient manual push for the whole page (Save button)
      document.getElementById('save-button').addEventListener('click', function () {{
          const results = [];
          const rows = document.querySelectorAll("tbody tr:nth-child(2n+1)"); // Select the first row for each object
          rows.forEach(function (row) {{
              const objid = row.querySelector("td").innerText.replace("ID", "").trim();
              const ratingGood = document.getElementById('good-' + objid).checked;
              const ratingBad = document.getElementById('bad-' + objid).checked;
              const noticed = document.getElementById('noticed-' + objid).value.trim();
              const nextStep = document.getElementById('nextstep-' + objid).value.trim();
              const reasons = document.getElementById('reasons-' + objid).value.trim();
              const payload = {{
                  rating: ratingGood ? "Good" : ratingBad ? "Bad" : "Not Rated",
                  noticed: noticed || "",
                  nextStep: nextStep || "",
                  reasons: reasons || "",
                  savedAt: new Date().toISOString()
              }};
              results.push({{ objid: objid, payload: payload }});
          }});
          // Download local copy (unchanged behavior)
          const blob = new Blob([JSON.stringify(results, null, 2)], {{ type: "application/json" }});
          const url = URL.createObjectURL(blob);
          const downloadLink = document.createElement("a");
          downloadLink.href = url;
          downloadLink.download = "fitting_results.json";
          downloadLink.click();
          URL.revokeObjectURL(url);

          // Also send all to server in bulk (so other visitors see latest)
          fetch('/api/results', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ bulk: results }})
          }}).catch(err => console.warn('Bulk save to server failed', err));
      }});
    }})();
    </script>
</body>
</html>
"""

# === Write out the HTML ===
with open(output_html, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Generated {output_html} (lazy, queued image loading via jsDelivr primary) with server-backed persistence hooks.")
