"""Generate deterministic cover + logo artwork for every Startup.

Renders abstract branded art (two-tone gradient, serif monogram, industry
label, name plate) with Pillow.  Images are deterministic per slug, so
re-running the command never churns files that already exist unless
--force is passed.

Output: static/img/startups/{slug}-cover.jpg  (1200x675)
        static/img/startups/{slug}-logo.png   (320x320)

Usage:
    python3 manage.py generate_startup_art
    python3 manage.py generate_startup_art --force
    python3 manage.py generate_startup_art --limit 2
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from staff.models import Startup

OUT_DIR = "static/img/startups"
COVER_W, COVER_H = 1200, 675
LOGO_SIZE = 320

# (dark, mid) tone pairs; all mids stay dark enough for white text.
PALETTE = [
    ((0x0F, 0x2A, 0x4A), (0x33, 0x66, 0x9E)),
    ((0x12, 0x3B, 0x2E), (0x2E, 0x7D, 0x5B)),
    ((0x33, 0x1A, 0x38), (0x6E, 0x42, 0x80)),
    ((0x45, 0x1F, 0x10), (0x9E, 0x5A, 0x34)),
    ((0x0E, 0x3A, 0x45), (0x2E, 0x7A, 0x8C)),
    ((0x3B, 0x0F, 0x1A), (0x94, 0x36, 0x4E)),
    ((0x1C, 0x1C, 0x40), (0x4C, 0x4C, 0x96)),
    ((0x0B, 0x3B, 0x7A), (0x3B, 0x7F, 0xD4)),
    ((0x3E, 0x2E, 0x08), (0x8C, 0x6E, 0x2A)),
    ((0x15, 0x33, 0x3F), (0x3E, 0x7C, 0x8C)),
    ((0x2A, 0x21, 0x18), (0x7A, 0x62, 0x48)),
    ((0x0E, 0x24, 0x18), (0x2F, 0x6B, 0x4F)),
]

GOLD = (0xC6, 0xA2, 0x4E)
WHITE = (0xFF, 0xFF, 0xFF)

_SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
_SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _hash_int(seed: str, mod: int) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % mod


def monogram(name: str) -> str:
    """First letters of the first two alphanumeric words, e.g. 'Aim Firms' -> 'AF'."""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name or "") if w]
    if not words:
        return "ST"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _tracked_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    tracking: int = 5,
) -> None:
    """Draw text with manual letter-spacing (PIL has no tracking support)."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), ch, font=font)
        x += (bbox[2] - bbox[0]) + tracking


def _ellipsize(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


def _pick(slug: str) -> tuple[tuple[int, ...], tuple[int, ...]]:
    return PALETTE[_hash_int(slug, len(PALETTE))]


def _vertical_gradient(dark: tuple[int, ...], light: tuple[int, ...]) -> Image.Image:
    mask = Image.linear_gradient("L").resize((COVER_W, COVER_H))
    top = Image.new("RGB", (COVER_W, COVER_H), dark)
    bottom = Image.new("RGB", (COVER_W, COVER_H), light)
    return Image.composite(bottom, top, mask)


def _bottom_scrim(img: Image.Image) -> Image.Image:
    """Darken the lower band so white name/monogram stay legible."""
    ramp = Image.new("L", (1, COVER_H))
    ramp.putdata(
        [0 if y < int(COVER_H * 0.5) else int((y - COVER_H * 0.5) / (COVER_H * 0.5) * 130)
         for y in range(COVER_H)]
    )
    overlay = Image.new("RGBA", (COVER_W, COVER_H), (0, 0, 0, 0))
    overlay.putalpha(ramp.resize((COVER_W, COVER_H)))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _glow(img: Image.Image, seed: str) -> Image.Image:
    """Smooth soft light spot; centre position varies per slug."""
    try:
        rg = Image.radial_gradient("L").resize((1024, 1024))  # 0 centre -> 255 edge
    except Exception:
        return img
    cx = int(COVER_W * (0.25 + 0.45 * _hash_int(seed + ":gx", 100) / 100))
    cy = int(COVER_H * (0.08 + 0.30 * _hash_int(seed + ":gy", 100) / 100))
    canvas = Image.new("L", (COVER_W, COVER_H), 255)
    canvas.paste(rg, (cx - 512, cy - 512))
    alpha = canvas.point(lambda v: max(0, int((1 - v / 255) * 34)))
    overlay = Image.new("RGBA", (COVER_W, COVER_H), (255, 255, 255, 0))
    overlay.putalpha(alpha)
    return Image.alpha_composite(img, overlay)


def _vignette(img: Image.Image) -> Image.Image:
    try:
        rg = Image.radial_gradient("L").resize((COVER_W, COVER_H))
    except Exception:
        return img
    mask = rg.point(lambda v: int(v * 0.35))
    overlay = Image.new("RGBA", (COVER_W, COVER_H), (0, 0, 0, 0))
    overlay.putalpha(mask)
    return Image.alpha_composite(img, overlay)


def render_cover(name: str, industry: str, slug: str) -> Image.Image:
    dark, light = _pick(slug)
    img = _vertical_gradient(dark, light).convert("RGBA")
    img = _bottom_scrim(img)
    img = _glow(img, slug)
    img = _vignette(img)

    draw = ImageDraw.Draw(img)
    label = (industry or "STARTUP").upper()[:28]
    _tracked_text(draw, (48, 44), label, _font(_SANS, 22), (255, 255, 255, 205), tracking=6)

    draw.rectangle((48, COVER_H - 156, 96, COVER_H - 150), fill=GOLD + (255,))

    name_font = _font(_SANS_BOLD, 36)
    display = _ellipsize(name, 34)
    draw.text((48, COVER_H - 108), display, font=name_font, fill=(255, 255, 255, 250),
              anchor="ls")

    mono_font = _font(_SERIF_BOLD, 210)
    draw.text(
        (COVER_W - 60, COVER_H - 42),
        monogram(name),
        font=mono_font,
        fill=(255, 255, 255, 238),
        anchor="rs",
    )
    return img.convert("RGB")


def render_logo(name: str, slug: str) -> Image.Image:
    dark, light = _pick(slug)
    img = Image.new("RGB", (LOGO_SIZE, LOGO_SIZE), dark)
    draw = ImageDraw.Draw(img)
    for y in range(LOGO_SIZE):
        t = y / LOGO_SIZE
        draw.line(
            (0, y, LOGO_SIZE, y),
            fill=tuple(int(dark[i] + (light[i] - dark[i]) * t * 0.35) for i in range(3)),
        )
    font = _font(_SERIF_BOLD, 132)
    draw.text(
        (LOGO_SIZE / 2, LOGO_SIZE / 2),
        monogram(name),
        font=font,
        fill=WHITE,
        anchor="mm",
    )
    draw.ellipse(
        (LOGO_SIZE // 2 - 7, LOGO_SIZE - 34, LOGO_SIZE // 2 + 7, LOGO_SIZE - 20),
        fill=GOLD,
    )
    return img


class Command(BaseCommand):
    help = "Generate deterministic cover/logo artwork for every startup."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
        parser.add_argument("--limit", type=int, default=0, help="Only first N startups.")

    def handle(self, *args, **options):
        out = Path(OUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        force = options["force"]
        qs = Startup.objects.all().order_by("slug")
        if options["limit"]:
            qs = qs[: options["limit"]]

        created = kept = 0
        for s in qs:
            if not s.slug:
                continue
            targets = (
                (out / f"{s.slug}-cover.jpg", lambda: render_cover(s.name, s.industry, s.slug),
                 {"format": "JPEG", "quality": 84, "optimize": True}),
                (out / f"{s.slug}-logo.png", lambda: render_logo(s.name, s.slug),
                 {"format": "PNG", "optimize": True}),
            )
            for path, factory, save_kwargs in targets:
                if force or not path.exists():
                    factory().save(path, **save_kwargs)
                    created += 1
                else:
                    kept += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"covers+logos in {OUT_DIR}: {created} generated, {kept} kept."
            )
        )
