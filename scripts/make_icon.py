"""Draws the app icon (a stack of photos with a check mark) and writes AppIcon.icns."""
import os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter

S = 1024
out = sys.argv[1]
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

# background squircle with a blue-to-teal gradient
grad = Image.new("RGBA", (S, S))
px = grad.load()
for y in range(S):
    for x in range(S):
        t = (x + y) / (2 * S)
        px[x, y] = (int(36 + 20 * t), int(110 + 110 * t), int(235 - 50 * t), 255)
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((100, 100, S - 100, S - 100), radius=185, fill=255)
img.paste(grad, (0, 0), mask)

def card(angle, fill, shade):
    c = Image.new("RGBA", (520, 400), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((0, 0, 519, 399), radius=34, fill=(255, 255, 255, 255))
    d.rounded_rectangle((26, 26, 493, 373), radius=18, fill=fill)
    d.polygon([(26, 373), (190, 190), (290, 300), (350, 240), (493, 373)], fill=shade)
    d.ellipse((350, 60, 420, 130), fill=(255, 255, 255, 235))
    c = c.rotate(angle, expand=True, resample=Image.BICUBIC)
    sh = Image.new("RGBA", c.size, (0, 0, 0, 0))
    sh.paste((0, 0, 40, 110), mask=c.split()[3].filter(ImageFilter.GaussianBlur(14)))
    return c, sh

for angle, fill, shade, cx, cy in [(-9, (255, 170, 120, 255), (225, 110, 90, 255), 470, 470),
                                   (7, (120, 205, 170, 255), (60, 150, 120, 255), 560, 540)]:
    c, sh = card(angle, fill, shade)
    img.alpha_composite(sh, (cx - c.width // 2, cy - c.height // 2 + 16))
    img.alpha_composite(c, (cx - c.width // 2, cy - c.height // 2))

# green check badge
badge = Image.new("RGBA", (330, 330), (0, 0, 0, 0))
d = ImageDraw.Draw(badge)
d.ellipse((0, 0, 329, 329), fill=(255, 255, 255, 255))
d.ellipse((18, 18, 311, 311), fill=(38, 190, 100, 255))
d.line([(88, 170), (143, 225), (246, 112)], fill=(255, 255, 255, 255), width=34, joint="curve")
for p in [(88, 170), (143, 225), (246, 112)]:
    d.ellipse((p[0] - 17, p[1] - 17, p[0] + 17, p[1] + 17), fill=(255, 255, 255, 255))
img.alpha_composite(badge, (560, 560))

iconset = out + ".iconset"
os.makedirs(iconset, exist_ok=True)
for sz in (16, 32, 128, 256, 512):
    img.resize((sz, sz), Image.LANCZOS).save(f"{iconset}/icon_{sz}x{sz}.png")
    img.resize((sz * 2, sz * 2), Image.LANCZOS).save(f"{iconset}/icon_{sz}x{sz}@2x.png")
subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out], check=True)
img.save(out.replace(".icns", ".png"))
