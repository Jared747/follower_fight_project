from __future__ import annotations

import base64
import io
from functools import lru_cache

from PIL import Image, ImageDraw


def _mask_key(name: str) -> str:
    low = (name or "").lower()
    if "cowboy" in low:
        return "cowboy"
    return "spartan"


def _draw_spartan(base_size: int = 200) -> Image.Image:
    size = max(60, base_size)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    w = float(size)

    crest_color = (196, 42, 46, 240)
    crest_shadow = (120, 20, 24, 235)
    crest_points = [
        (0.5 * w, 0.02 * w),
        (0.86 * w, 0.18 * w),
        (0.82 * w, 0.3 * w),
        (0.5 * w, 0.2 * w),
        (0.18 * w, 0.3 * w),
        (0.14 * w, 0.18 * w),
    ]
    draw.polygon(crest_points, fill=crest_color, outline=crest_shadow)
    draw.rectangle([0.36 * w, 0.18 * w, 0.64 * w, 0.32 * w], fill=crest_color, outline=crest_shadow)

    helmet_color = (224, 207, 164, 255)
    helmet_shadow = (122, 82, 38, 235)
    helmet_points = [
        (0.5 * w, 0.18 * w),
        (0.84 * w, 0.3 * w),
        (0.92 * w, 0.62 * w),
        (0.76 * w, 0.96 * w),
        (0.5 * w, 0.84 * w),
        (0.24 * w, 0.96 * w),
        (0.08 * w, 0.62 * w),
        (0.16 * w, 0.3 * w),
    ]
    draw.polygon(helmet_points, fill=helmet_color, outline=helmet_shadow)
    draw.line([(0.5 * w, 0.24 * w), (0.5 * w, 0.72 * w)], fill=helmet_shadow, width=max(2, int(w * 0.02)))

    draw.polygon(
        [(0.22 * w, 0.32 * w), (0.4 * w, 0.32 * w), (0.42 * w, 0.78 * w), (0.26 * w, 0.88 * w)],
        fill=(255, 239, 210, 90),
    )

    open_color = (28, 28, 32, 235)
    eye_top = 0.46 * w
    eye_bottom = eye_top + 0.12 * w
    draw.rounded_rectangle(
        [0.24 * w, eye_top, 0.76 * w, eye_bottom], radius=int(0.05 * w), fill=open_color, outline=None
    )
    draw.polygon(
        [
            (0.46 * w, eye_bottom - 0.02 * w),
            (0.54 * w, eye_bottom - 0.02 * w),
            (0.54 * w, 0.88 * w),
            (0.46 * w, 0.88 * w),
            (0.5 * w, 0.94 * w),
        ],
        fill=open_color,
    )
    draw.line(
        [(0.33 * w, eye_bottom - 0.03 * w), (0.42 * w, eye_top + 0.01 * w)],
        fill=(255, 232, 190, 120),
        width=max(1, int(w * 0.01)),
    )
    draw.line(
        [(0.58 * w, eye_top + 0.01 * w), (0.67 * w, eye_bottom - 0.03 * w)],
        fill=helmet_shadow,
        width=max(1, int(w * 0.01)),
    )
    return img


def _draw_cowboy(base_size: int = 200) -> Image.Image:
    size = max(60, base_size)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    w = float(size)

    brim_color = (170, 110, 60, 245)
    brim_shadow = (118, 76, 42, 230)
    crown_color = (191, 133, 76, 245)
    brim_points = [
        (0.08 * w, 0.55 * w),
        (0.22 * w, 0.45 * w),
        (0.38 * w, 0.53 * w),
        (0.62 * w, 0.53 * w),
        (0.78 * w, 0.45 * w),
        (0.92 * w, 0.55 * w),
        (0.78 * w, 0.63 * w),
        (0.22 * w, 0.63 * w),
    ]
    draw.polygon(brim_points, fill=brim_color, outline=brim_shadow)

    crown_points = [
        (0.32 * w, 0.22 * w),
        (0.68 * w, 0.22 * w),
        (0.62 * w, 0.5 * w),
        (0.38 * w, 0.5 * w),
    ]
    draw.polygon(crown_points, fill=crown_color, outline=brim_shadow)
    band_color = (74, 45, 24, 220)
    draw.rectangle([0.34 * w, 0.4 * w, 0.66 * w, 0.48 * w], fill=band_color, outline=None)

    draw.line(
        [(0.42 * w, 0.28 * w), (0.5 * w, 0.24 * w), (0.58 * w, 0.28 * w)],
        fill=brim_shadow,
        width=max(2, int(w * 0.015)),
    )
    draw.polygon(
        [(0.58 * w, 0.26 * w), (0.66 * w, 0.3 * w), (0.64 * w, 0.44 * w), (0.56 * w, 0.42 * w)],
        fill=(244, 210, 168, 90),
    )
    return img


@lru_cache(maxsize=4)
def _base_mask_icon(key: str) -> Image.Image:
    if key == "cowboy":
        return _draw_cowboy()
    return _draw_spartan()


@lru_cache(maxsize=32)
def mask_icon_image(mask_name: str, size: int = 80) -> Image.Image:
    key = _mask_key(mask_name)
    base = _base_mask_icon(key)
    target_w = max(20, int(size))
    aspect = base.size[1] / base.size[0]
    target_h = int(target_w * aspect)
    if base.size == (target_w, target_h):
        return base.copy()
    return base.resize((target_w, target_h), Image.LANCZOS)


def mask_icon_bytes(mask_name: str, size: int = 80) -> bytes:
    icon = mask_icon_image(mask_name, size=size)
    buf = io.BytesIO()
    icon.save(buf, format="PNG")
    return buf.getvalue()


def mask_data_uri(mask_name: str, size: int = 80) -> str:
    data = mask_icon_bytes(mask_name, size=size)
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def apply_mask_to_avatar(avatar: Image.Image, mask_name: str) -> Image.Image:
    if not mask_name:
        return avatar
    base = avatar.convert("RGBA")
    mask_width = int(base.size[0] * 0.72)
    mask = mask_icon_image(mask_name, size=mask_width)
    offset_x = (base.size[0] - mask.width) // 2
    offset_y = -max(2, int(base.size[0] * 0.08))
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.paste(mask, (offset_x, offset_y), mask)
    return Image.alpha_composite(base, layer)
