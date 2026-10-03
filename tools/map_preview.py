"""Render data/build/map.json to a PNG for quick visual review (colors = clusters)."""
import colorsys
import json
import sys

from PIL import Image, ImageDraw

m = json.load(open("data/build/map.json", encoding="utf-8"))
out = sys.argv[1]
W = 1800
img = Image.new("RGB", (W, W), "#070b18")
d = ImageDraw.Draw(img)
s = lambda v: (v + 1400) / 2800 * W
nodes = m["nodes"]
ncl = max(nd[5] for nd in nodes) + 1


def color(k):
    if k < 0:
        return (90, 100, 130)
    r, g, b = colorsys.hls_to_rgb((k * 0.618034) % 1.0, 0.62, 0.75)
    return int(r * 255), int(g * 255), int(b * 255)


for nd in nodes:
    x, y = s(nd[3]), s(nd[4])
    d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=color(nd[5]))
for c in m["constellations"]:
    d.text((s(c["x"]), s(c["y"])), c["name"], fill="#94a3b8", anchor="mm")
for c in m["regions"]:
    d.text((s(c["x"]), s(c["y"]) - 14), c["name"].upper(), fill="white", anchor="mm")
img.save(out)
print("saved", out)
