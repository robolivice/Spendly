from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

SIZE = 1024
ASSETS = Path(__file__).resolve().parent

ICO_SIZES = [16, 32, 48, 64, 128, 256]
COMPACT_MAX = 48

TILE_TOP = (10, 12, 18, 255)
TILE_BOTTOM = (21, 27, 43, 255)
INDIGO = (124, 156, 255, 255)
VIOLET = (154, 108, 255, 255)
ARROW = (240, 244, 255, 255)
DIAG = 0.70710678


def vertical_gradient(size: tuple[int, int], top, bottom) -> Image.Image:
    strip = Image.new("RGBA", (1, size[1]))
    for y in range(size[1]):
        t = y / max(size[1] - 1, 1)
        strip.putpixel(
            (0, y),
            tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(4)),
        )
    return strip.resize(size, Image.Resampling.BILINEAR)


def horizontal_gradient(size: tuple[int, int], left, right) -> Image.Image:
    strip = Image.new("RGBA", (size[0], 1))
    for x in range(size[0]):
        t = x / max(size[0] - 1, 1)
        strip.putpixel(
            (x, 0),
            tuple(round(left[i] + (right[i] - left[i]) * t) for i in range(4)),
        )
    return strip.resize(size, Image.Resampling.BILINEAR)


def radial_glow(size: int, center: tuple[int, int], radius: int, color, peak: int) -> Image.Image:
    diameter = radius * 2
    ramp = ImageOps.invert(Image.radial_gradient("L").resize((diameter, diameter)))
    ramp = ramp.filter(ImageFilter.GaussianBlur(diameter // 22))
    ramp = ramp.point(lambda value: int((value / 255) ** 2.1 * peak))

    layer = Image.new("L", (size, size), 0)
    layer.paste(ramp, (center[0] - radius, center[1] - radius))
    glow = Image.new("RGBA", (size, size), color)
    glow.putalpha(layer)
    return glow


def rounded_line(draw: ImageDraw.ImageDraw, start, end, width: int, fill) -> None:
    draw.line([start, end], fill=fill, width=width)
    radius = width // 2
    for point in (start, end):
        draw.ellipse(
            [point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius],
            fill=fill,
        )


def build_icon(compact: bool = False) -> Image.Image:
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

    tile_mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(tile_mask).rounded_rectangle(
        [8, 8, SIZE - 9, SIZE - 9], radius=228, fill=255
    )
    tile = vertical_gradient((SIZE, SIZE), TILE_TOP, TILE_BOTTOM)
    canvas.paste(tile, (0, 0), tile_mask)

    canvas.alpha_composite(radial_glow(SIZE, (318, 240), 640, INDIGO, 110))
    canvas.alpha_composite(radial_glow(SIZE, (742, 812), 560, VIOLET, 64))

    center = (512, 512)
    ring_radius = 318 if compact else 296
    ring_width = 152 if compact else 108
    ring_mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(ring_mask).ellipse(
        [
            center[0] - ring_radius,
            center[1] - ring_radius,
            center[0] + ring_radius,
            center[1] + ring_radius,
        ],
        outline=255,
        width=ring_width,
    )
    ring = horizontal_gradient((SIZE, SIZE), INDIGO, VIOLET)
    canvas.paste(ring, (0, 0), ring_mask)

    if not compact:
        hairline = Image.new("L", (SIZE, SIZE), 0)
        ImageDraw.Draw(hairline).ellipse(
            [
                center[0] - ring_radius + ring_width // 2,
                center[1] - ring_radius + ring_width // 2,
                center[0] + ring_radius - ring_width // 2,
                center[1] + ring_radius - ring_width // 2,
            ],
            outline=60,
            width=6,
        )
        canvas.paste(
            Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255)), (0, 0), hairline
        )

    arrow_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(arrow_layer)

    if compact:
        tip = (676, 360)
        shaft_start = (382, 654)
        head_length = 215
        half = 132
        shaft_width = 128
    else:
        tip = (690, 346)
        shaft_start = (366, 670)
        head_length = 210
        half = 116
        shaft_width = 96

    base = (tip[0] - DIAG * head_length, tip[1] + DIAG * head_length)
    point_a = (base[0] + half * DIAG, base[1] + half * DIAG)
    point_b = (base[0] - half * DIAG, base[1] - half * DIAG)

    rounded_line(draw, shaft_start, base, shaft_width, ARROW)
    draw.polygon([tip, point_a, point_b], fill=ARROW)

    arrow_alpha = arrow_layer.getchannel("A").filter(ImageFilter.GaussianBlur(0.6))
    arrow_layer.putalpha(arrow_alpha)
    canvas.alpha_composite(arrow_layer)

    return canvas


def write_ico(path: Path, frames: list[tuple[int, Image.Image]]) -> None:
    blobs: list[tuple[int, bytes]] = []
    for size, frame in frames:
        buffer = io.BytesIO()
        frame.save(buffer, format="PNG", optimize=True)
        blobs.append((size, buffer.getvalue()))

    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries = b""
    payload = b""
    for size, blob in blobs:
        dimension = 0 if size >= 256 else size
        entries += struct.pack(
            "<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(blob), offset
        )
        offset += len(blob)
        payload += blob

    path.write_bytes(header + entries + payload)


def main() -> None:
    detailed = build_icon(compact=False)
    compact = build_icon(compact=True)

    master = ASSETS / "Spendly-1024.png"
    detailed.save(master, format="PNG")

    frames: list[tuple[int, Image.Image]] = []
    for size in ICO_SIZES:
        source = compact if size <= COMPACT_MAX else detailed
        frames.append((size, source.resize((size, size), Image.Resampling.LANCZOS)))

    ico_path = ASSETS / "Spendly.ico"
    write_ico(ico_path, frames)

    print(f"Wrote {master}")
    print(f"Wrote {ico_path} ({', '.join(str(s) for s in ICO_SIZES)})")


if __name__ == "__main__":
    main()
