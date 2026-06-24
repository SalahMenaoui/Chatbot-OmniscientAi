"""
process_logo.py
Auto-crops a logo by scanning outward from center to find where the background ends.
Algorithm: starting from center, find the outermost concentric circle where the
entire circumference is a single solid color — that's the background border to remove.

Usage:
    py tools/process_logo.py <input_image> <output_image>
    py tools/process_logo.py clients/my_client/assets/logo.png clients/my_client/assets/logo_cropped.png
"""

import sys
import os
import math

try:
    from PIL import Image
except ImportError:
    print("ERROR: Run: pip install Pillow")
    sys.exit(1)


def color_distance(c1, c2):
    """Euclidean distance between two RGB(A) colors."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1[:3], c2[:3])))


def get_background_color(pixels, width, height, sample_size=4):
    """Detect background color by averaging the 4 corners."""
    corners = []
    for x in range(sample_size):
        for y in range(sample_size):
            corners += [
                pixels[x, y],
                pixels[width - 1 - x, y],
                pixels[x, height - 1 - y],
                pixels[width - 1 - x, height - 1 - y],
            ]
    r = sum(c[0] for c in corners) // len(corners)
    g = sum(c[1] for c in corners) // len(corners)
    b = sum(c[2] for c in corners) // len(corners)
    return (r, g, b)


def sample_circumference(cx, cy, radius, num_samples=64):
    """Return a list of (x, y) integer points on a circle."""
    points = []
    for i in range(num_samples):
        angle = 2 * math.pi * i / num_samples
        x = int(round(cx + radius * math.cos(angle)))
        y = int(round(cy + radius * math.sin(angle)))
        points.append((x, y))
    return points


def is_solid_color(pixels, points, width, height, threshold=18):
    """Return True if all in-bounds points are within threshold of each other."""
    valid = []
    for x, y in points:
        if 0 <= x < width and 0 <= y < height:
            valid.append(pixels[x, y])
    if len(valid) < 4:
        return True  # Too few points — treat as background
    ref = valid[0]
    return all(color_distance(c, ref) <= threshold for c in valid[1:])


def find_content_radius(pixels, width, height, threshold=18):
    """
    Scan outward from center. Return the radius at which the circumference
    stops being a single solid color — that's where real content begins.
    Then return the max radius where content is still present.
    """
    cx, cy = width // 2, height // 2
    max_radius = int(math.sqrt(cx**2 + cy**2))

    bg_color = get_background_color(pixels, width, height)

    content_start = None
    content_end   = 0

    for r in range(1, max_radius + 1):
        points = sample_circumference(cx, cy, r, num_samples=max(16, r))
        solid  = is_solid_color(pixels, points, width, height, threshold)

        if solid:
            # Check if this solid ring matches background
            sample_pts = [(x, y) for x, y in points if 0 <= x < width and 0 <= y < height]
            if sample_pts:
                ring_color = pixels[sample_pts[0][0], sample_pts[0][1]]
                if color_distance(ring_color, bg_color) > threshold:
                    # Solid but NOT background — still content
                    content_end = r
                    if content_start is None:
                        content_start = r
        else:
            # Mixed colors — definitely content
            content_end = r
            if content_start is None:
                content_start = r

    return content_start, content_end, cx, cy, bg_color


def is_transparent_png(img):
    """Returns True if the image uses transparency as its background."""
    pixels = img.load()
    w, h   = img.size
    corners = [pixels[0,0], pixels[w-1,0], pixels[0,h-1], pixels[w-1,h-1]]
    return all(len(c) == 4 and c[3] < 30 for c in corners)


def bbox_from_alpha(img, threshold=10):
    """Find bounding box of non-transparent pixels."""
    pixels = img.load()
    w, h   = img.size
    minx, miny, maxx, maxy = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            c = pixels[x, y]
            if len(c) == 4 and c[3] > threshold:
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
    return (minx, miny, maxx, maxy) if maxx > minx else None


def process_logo(input_path, output_path, padding=8):
    img = Image.open(input_path).convert("RGBA")
    width, height = img.size

    print(f"  Input:  {input_path}  ({width}x{height})")

    # ── Transparent PNG: crop by alpha bounding box ───────────────────
    if is_transparent_png(img):
        bbox = bbox_from_alpha(img, threshold=10)
        if bbox is None:
            print("  Transparent logo but no visible content — using original.")
            img.save(output_path)
            return

        minx, miny, maxx, maxy = bbox
        # Add padding
        minx = max(0, minx - padding)
        miny = max(0, miny - padding)
        maxx = min(width  - 1, maxx + padding)
        maxy = min(height - 1, maxy + padding)

        cropped = img.crop((minx, miny, maxx + 1, maxy + 1))
        cw, ch  = cropped.size

        # Make square, keep transparency
        size   = max(cw, ch)
        square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        square.paste(cropped, ((size - cw) // 2, (size - ch) // 2))
        square.save(output_path)

        reduction = round((1 - (size / max(width, height))) * 100)
        content_w = maxx - minx
        content_h = maxy - miny
        center_x  = (minx + maxx) // 2
        center_y  = (miny + maxy) // 2
        offset_x  = center_x - width  // 2
        offset_y  = center_y - height // 2
        print(f"  Transparent PNG — content bbox: {content_w}x{content_h}")
        print(f"  Content center offset: ({offset_x:+d}, {offset_y:+d})")
        print(f"  Output: {output_path}  ({size}x{size})  [{reduction}% border removed]")
        return

    # ── Solid-background PNG: crop by color radius ────────────────────
    pixels = img.load()
    content_start, content_end, cx, cy, bg_color = find_content_radius(
        pixels, width, height, threshold=20
    )

    if content_end == 0:
        print("  No content detected — using original image.")
        img.save(output_path)
        return

    left   = max(0, cx - content_end - padding)
    right  = min(width,  cx + content_end + padding)
    top    = max(0, cy - content_end - padding)
    bottom = min(height, cy + content_end + padding)

    cropped = img.crop((left, top, right, bottom))
    cw, ch  = cropped.size

    size   = max(cw, ch)
    square = Image.new("RGBA", (size, size), bg_color + (255,))
    # Use alpha_composite to preserve transparency correctly
    layer  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer.paste(cropped, ((size - cw) // 2, (size - ch) // 2))
    result = Image.alpha_composite(square, layer)
    result.save(output_path)

    reduction = round((1 - (size / max(width, height))) * 100)
    print(f"  Content radius: {content_end}px  (background: #{bg_color[0]:02x}{bg_color[1]:02x}{bg_color[2]:02x})")
    print(f"  Output: {output_path}  ({size}x{size})  [{reduction}% border removed]")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: py tools/process_logo.py <input> <output>")
        sys.exit(1)
    process_logo(sys.argv[1], sys.argv[2])
