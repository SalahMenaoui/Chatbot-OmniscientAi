"""
crop_tool.py
Visual logo crop editor. Opens a browser interface to manually select a crop zone.
The crop is saved to assets/logo_cropped.png and applied to the chatbot immediately.

Usage:
    py tools/crop_tool.py <client_name>

Example:
    py tools/crop_tool.py plombier_expert_terrebonne
"""

import sys, os, json, base64, io, webbrowser, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs

try:
    from PIL import Image
except ImportError:
    print("ERROR: Run: pip install Pillow")
    sys.exit(1)

BASE_DIR = Path(__file__).parent.parent

# ── Find best source logo ──────────────────────────────────────────────────────

def find_source_logo(client_name):
    assets = BASE_DIR / "clients" / client_name / "assets"
    for name in ["apple_touch_icon.png", "profile_pic.jpg", "favicon.png", "logo.png", "logo.jpg"]:
        p = assets / name
        if p.exists():
            return p
    return None


# ── HTML page ──────────────────────────────────────────────────────────────────

def build_html(client_name, img_b64, img_w, img_h, mime):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Logo Crop — {client_name}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0f0f0f; color: #f0f0f0;
    display: flex; flex-direction: column; align-items: center;
    padding: 32px 16px; gap: 24px; min-height: 100vh;
  }}
  h1 {{ font-size: 18px; font-weight: 600; color: #fff; }}
  p.sub {{ font-size: 13px; color: #888; }}

  .workspace {{
    display: flex; gap: 40px; align-items: flex-start; flex-wrap: wrap; justify-content: center;
  }}

  .editor-wrap {{
    display: flex; flex-direction: column; gap: 10px; align-items: center;
  }}
  .editor-label {{ font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: .05em; }}

  #canvas-wrap {{
    position: relative; cursor: crosshair;
    border: 1px solid #333; border-radius: 8px; overflow: visible;
    background: repeating-conic-gradient(#1a1a1a 0% 25%, #222 0% 50%) 0 0 / 16px 16px;
  }}
  #source-img {{ display: block; max-width: 400px; max-height: 400px; }}
  #crop-box {{
    position: absolute; border: 2px solid #3b82f6;
    box-shadow: 0 0 0 9999px rgba(0,0,0,0.55);
    cursor: move;
  }}
  .handle {{
    position: absolute; width: 10px; height: 10px;
    background: #fff; border: 2px solid #3b82f6; border-radius: 2px;
  }}
  .handle.tl {{ top:-5px; left:-5px; cursor:nwse-resize; }}
  .handle.tr {{ top:-5px; right:-5px; cursor:nesw-resize; }}
  .handle.bl {{ bottom:-5px; left:-5px; cursor:nesw-resize; }}
  .handle.br {{ bottom:-5px; right:-5px; cursor:nwse-resize; }}

  .preview-wrap {{
    display: flex; flex-direction: column; gap: 16px; align-items: center;
  }}
  .preview-block {{ display: flex; flex-direction: column; gap: 6px; align-items: center; }}
  .preview-label {{ font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: .05em; }}

  .circle-preview {{
    border-radius: 50%; overflow: hidden; background: #fff;
    border: 2px solid #333; flex-shrink: 0;
  }}
  .circle-preview canvas {{ display: block; }}

  .actions {{
    display: flex; gap: 12px; flex-wrap: wrap; justify-content: center;
  }}
  button {{
    padding: 10px 24px; border-radius: 8px; border: none;
    font-size: 14px; font-weight: 600; cursor: pointer;
    transition: opacity .15s, transform .1s;
  }}
  button:hover {{ opacity: .85; }}
  button:active {{ transform: scale(.97); }}
  #btn-save {{
    background: #3b82f6; color: #fff;
  }}
  #btn-reset {{
    background: #333; color: #aaa;
  }}
  #status {{
    font-size: 13px; color: #22c55e; min-height: 20px; text-align: center;
  }}
  .coords {{
    font-size: 11px; color: #555; font-family: monospace;
  }}
</style>
</head>
<body>

<h1>Logo Crop — {client_name}</h1>
<p class="sub">Drag the blue box to select the crop area. The circle previews how it'll look as the chatbot avatar.</p>

<div class="workspace">

  <div class="editor-wrap">
    <div class="editor-label">Source image</div>
    <div id="canvas-wrap">
      <img id="source-img" src="data:{mime};base64,{img_b64}" draggable="false">
      <div id="crop-box">
        <div class="handle tl" data-corner="tl"></div>
        <div class="handle tr" data-corner="tr"></div>
        <div class="handle bl" data-corner="bl"></div>
        <div class="handle br" data-corner="br"></div>
      </div>
    </div>
    <div class="coords" id="coords">x: 0  y: 0  w: 0  h: 0</div>
  </div>

  <div class="preview-wrap">
    <div class="editor-label">Avatar preview</div>
    <div class="preview-block">
      <div class="circle-preview" style="width:80px;height:80px">
        <canvas id="prev80" width="80" height="80"></canvas>
      </div>
      <div class="preview-label">80px</div>
    </div>
    <div class="preview-block">
      <div class="circle-preview" style="width:44px;height:44px">
        <canvas id="prev44" width="44" height="44"></canvas>
      </div>
      <div class="preview-label">44px (header)</div>
    </div>
    <div class="preview-block">
      <div class="circle-preview" style="width:34px;height:34px">
        <canvas id="prev34" width="34" height="34"></canvas>
      </div>
      <div class="preview-label">34px (bubble)</div>
    </div>
  </div>

</div>

<div class="actions">
  <button id="btn-reset">Reset</button>
  <button id="btn-save">Save crop</button>
</div>
<div id="status"></div>

<script>
const IMG_W = {img_w};
const IMG_H = {img_h};

const wrap    = document.getElementById('canvas-wrap');
const img     = document.getElementById('source-img');
const cropBox = document.getElementById('crop-box');
const coordEl = document.getElementById('coords');
const status  = document.getElementById('status');

// ── State ──────────────────────────────────────────────────────────────────────
// Crop in IMAGE pixels (not display pixels)
let crop = {{ x: 0, y: 0, w: IMG_W, h: IMG_H }};

// ── Scale helpers ──────────────────────────────────────────────────────────────
function displayToImg(v, axis) {{
  const r = axis === 'x' ? IMG_W / img.width : IMG_H / img.height;
  return v * r;
}}
function imgToDisplay(v, axis) {{
  const r = axis === 'x' ? img.width / IMG_W : img.height / IMG_H;
  return v * r;
}}

// ── Render crop box ────────────────────────────────────────────────────────────
function renderBox() {{
  const x = imgToDisplay(crop.x, 'x');
  const y = imgToDisplay(crop.y, 'y');
  const w = imgToDisplay(crop.w, 'x');
  const h = imgToDisplay(crop.h, 'y');
  cropBox.style.left   = x + 'px';
  cropBox.style.top    = y + 'px';
  cropBox.style.width  = w + 'px';
  cropBox.style.height = h + 'px';
  coordEl.textContent  = `x: ${{Math.round(crop.x)}}  y: ${{Math.round(crop.y)}}  w: ${{Math.round(crop.w)}}  h: ${{Math.round(crop.h)}}`;
  renderPreviews();
}}

// ── Previews ───────────────────────────────────────────────────────────────────
function renderPreviews() {{
  ['prev80','prev44','prev34'].forEach(id => {{
    const canvas = document.getElementById(id);
    const size   = canvas.width;
    const ctx    = canvas.getContext('2d');
    ctx.clearRect(0, 0, size, size);
    // White background
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(size/2, size/2, size/2, 0, Math.PI*2);
    ctx.fill();
    // Clip to circle
    ctx.save();
    ctx.beginPath();
    ctx.arc(size/2, size/2, size/2, 0, Math.PI*2);
    ctx.clip();
    // Handle out-of-bounds crop: only draw the portion that intersects the image
    const srcX = Math.max(0, crop.x);
    const srcY = Math.max(0, crop.y);
    const srcW = Math.min(crop.w - (srcX - crop.x), IMG_W - srcX);
    const srcH = Math.min(crop.h - (srcY - crop.y), IMG_H - srcY);
    if (srcW > 0 && srcH > 0) {{
      const dstX = ((srcX - crop.x) / crop.w) * size;
      const dstY = ((srcY - crop.y) / crop.h) * size;
      const dstW = (srcW / crop.w) * size;
      const dstH = (srcH / crop.h) * size;
      ctx.drawImage(img, srcX, srcY, srcW, srcH, dstX, dstY, dstW, dstH);
    }}
    ctx.restore();
  }});
}}

// ── Drag to draw new crop ──────────────────────────────────────────────────────
let drawing = false, drawStart = null;

wrap.addEventListener('mousedown', e => {{
  if (e.target !== img && e.target !== wrap) return;
  const r = img.getBoundingClientRect();
  drawStart = {{ x: e.clientX - r.left, y: e.clientY - r.top }};
  drawing = true;
  e.preventDefault();
}});

window.addEventListener('mousemove', e => {{
  if (!drawing) return;
  const r = img.getBoundingClientRect();
  const cx = Math.max(0, Math.min(img.width,  e.clientX - r.left));
  const cy = Math.max(0, Math.min(img.height, e.clientY - r.top));
  const x = Math.min(drawStart.x, cx);
  const y = Math.min(drawStart.y, cy);
  const w = Math.abs(cx - drawStart.x);
  const h = Math.abs(cy - drawStart.y);
  if (w > 4 && h > 4) {{
    crop = {{
      x: Math.round(displayToImg(x, 'x')),
      y: Math.round(displayToImg(y, 'y')),
      w: Math.round(displayToImg(w, 'x')),
      h: Math.round(displayToImg(h, 'y')),
    }};
    renderBox();
  }}
}});
window.addEventListener('mouseup', () => drawing = false);

// ── Move crop box ──────────────────────────────────────────────────────────────
let moving = false, moveStart = null, cropAtMove = null;

cropBox.addEventListener('mousedown', e => {{
  if (e.target.classList.contains('handle')) return;
  const r = img.getBoundingClientRect();
  moveStart  = {{ x: e.clientX - r.left, y: e.clientY - r.top }};
  cropAtMove = {{ ...crop }};
  moving = true;
  e.preventDefault();
  e.stopPropagation();
}});

window.addEventListener('mousemove', e => {{
  if (!moving) return;
  const r  = img.getBoundingClientRect();
  const cx = e.clientX - r.left;
  const cy = e.clientY - r.top;
  const dx = displayToImg(cx - moveStart.x, 'x');
  const dy = displayToImg(cy - moveStart.y, 'y');
  crop.x = Math.round(cropAtMove.x + dx);
  crop.y = Math.round(cropAtMove.y + dy);
  renderBox();
}});
window.addEventListener('mouseup', () => moving = false);

// ── Resize via corner handles ──────────────────────────────────────────────────
let resizing = false, resizeCorner = null, cropAtResize = null, resizeStart = null;

document.querySelectorAll('.handle').forEach(h => {{
  h.addEventListener('mousedown', e => {{
    resizeCorner  = e.target.dataset.corner;
    resizeStart   = {{ x: e.clientX, y: e.clientY }};
    cropAtResize  = {{ ...crop }};
    resizing = true;
    e.preventDefault();
    e.stopPropagation();
  }});
}});

window.addEventListener('mousemove', e => {{
  if (!resizing) return;
  const dx = displayToImg(e.clientX - resizeStart.x, 'x');
  const dy = displayToImg(e.clientY - resizeStart.y, 'y');
  let {{x, y, w, h}} = cropAtResize;
  if (resizeCorner === 'tl') {{ x += dx; y += dy; w -= dx; h -= dy; }}
  if (resizeCorner === 'tr') {{          y += dy; w += dx; h -= dy; }}
  if (resizeCorner === 'bl') {{ x += dx;          w -= dx; h += dy; }}
  if (resizeCorner === 'br') {{                   w += dx; h += dy; }}
  if (w < 10 || h < 10) return;
  crop = {{ x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h) }};
  renderBox();
}});
window.addEventListener('mouseup', () => resizing = false);

// ── Reset ──────────────────────────────────────────────────────────────────────
document.getElementById('btn-reset').addEventListener('click', () => {{
  crop = {{ x: 0, y: 0, w: IMG_W, h: IMG_H }};
  renderBox();
}});

// ── Save ───────────────────────────────────────────────────────────────────────
document.getElementById('btn-save').addEventListener('click', async () => {{
  status.textContent = 'Saving…';
  try {{
    const res = await fetch('/save', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ x: crop.x, y: crop.y, w: crop.w, h: crop.h }})
    }});
    const data = await res.json();
    if (data.ok) {{
      status.textContent = '✓ Saved to ' + data.path;
    }} else {{
      status.textContent = '✗ Error: ' + data.error;
    }}
  }} catch(e) {{
    status.textContent = '✗ ' + e.message;
  }}
}});

// ── Init ───────────────────────────────────────────────────────────────────────
img.onload = renderBox;
if (img.complete) renderBox();
</script>
</body>
</html>"""


# ── HTTP handler ───────────────────────────────────────────────────────────────

class CropHandler(BaseHTTPRequestHandler):
    client_name = None
    source_path = None

    def do_GET(self):
        src = Path(self.source_path)
        img = Image.open(src)
        img_w, img_h = img.size
        mime = "image/png" if src.suffix.lower() == ".png" else "image/jpeg"
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        html = build_html(self.client_name, b64, img_w, img_h, mime)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/save":
            self.send_response(404); self.end_headers(); return
        length = int(self.headers.get("Content-Length", 0))
        data   = json.loads(self.rfile.read(length))
        x, y, w, h = int(data["x"]), int(data["y"]), int(data["w"]), int(data["h"])

        try:
            src      = Image.open(self.source_path).convert("RGBA")
            img_w, img_h = src.size

            # Canvas = crop area (transparent background, supports out-of-bounds)
            canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

            # Intersection of crop rect with image bounds
            src_x  = max(0, x);   src_y  = max(0, y)
            src_x2 = min(img_w, x + w); src_y2 = min(img_h, y + h)
            if src_x2 > src_x and src_y2 > src_y:
                region  = src.crop((src_x, src_y, src_x2, src_y2))
                paste_x = src_x - x   # offset inside canvas (0 if x>=0, positive if x<0)
                paste_y = src_y - y
                canvas.paste(region, (paste_x, paste_y))

            # Make square
            size   = max(w, h)
            square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            square.paste(canvas, ((size - w) // 2, (size - h) // 2))

            out_path = BASE_DIR / "clients" / self.client_name / "assets" / "logo_cropped.png"
            square.save(out_path)

            # Also copy to chatbot folder if it exists
            chatbot_logo = BASE_DIR / "clients" / self.client_name / "chatbot" / "logo_cropped.png"
            if chatbot_logo.parent.exists():
                import shutil
                shutil.copy2(out_path, chatbot_logo)

            rel = f"clients/{self.client_name}/assets/logo_cropped.png"
            resp = json.dumps({"ok": True, "path": rel}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(resp))
            self.end_headers()
            self.wfile.write(resp)
        except Exception as e:
            resp = json.dumps({"ok": False, "error": str(e)}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(resp))
            self.end_headers()
            self.wfile.write(resp)

    def log_message(self, fmt, *args):
        pass  # Silent


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py tools/crop_tool.py <client_name>")
        sys.exit(1)

    client_name = sys.argv[1]
    source_path = find_source_logo(client_name)

    if not source_path:
        print(f"No logo found in clients/{client_name}/assets/")
        print("Run: py tools/download_brand_assets.py <client_name>")
        sys.exit(1)

    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001

    CropHandler.client_name = client_name
    CropHandler.source_path = str(source_path)

    print(f"")
    print(f"  Crop Tool — {client_name}")
    print(f"  Source:  {source_path.name}")
    print(f"  Open:    http://localhost:{port}")
    print(f"  Press Ctrl+C to stop.")
    print(f"")

    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    HTTPServer(("", port), CropHandler).serve_forever()
