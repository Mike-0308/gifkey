# -*- coding: utf-8 -*-
"""抠像核心：色键（chroma key）逐帧去背景 + 输出编码（含体积优化）。"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

# 体积优化档位：统一调色板色数 / 是否降帧
# 实测（800×1076、300 帧素材）：原画质 7.07MB → 标准 6.59MB → 强力 4.9MB → 极限 3.0MB
TIERS = {
    "original": {"colors": None, "thin": False},   # 逐帧独立 256 色，与旧版一致
    "standard": {"colors": 255, "thin": False},    # 全片共用一套调色板
    "strong": {"colors": 96, "thin": False},       # 再降到 96 色
    "max": {"colors": 64, "thin": True},           # 64 色 + 帧率减半
}
TIER_LABELS = {
    "original": "原画质", "standard": "标准", "strong": "强力", "max": "极限",
}
WEBP_QUALITY = {"original": 95, "standard": 88, "strong": 80, "max": 70}


def hex_to_rgb(s: str) -> tuple[int, int, int]:
    s = (s or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError("颜色格式不对，需要 #RRGGBB")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(c) for c in rgb[:3])


def key_frame(
    frame: Image.Image,
    key_rgb: tuple[int, int, int],
    tolerance: float = 45,
    softness: float = 20,
    despill: bool = True,
    shrink: bool = False,
) -> Image.Image:
    """把接近 key_rgb 的像素变透明，返回 RGBA 图。"""
    rgba = frame.convert("RGBA")
    arr = np.asarray(rgba).astype(np.float32)
    rgb = arr[..., :3]
    base_alpha = arr[..., 3] / 255.0

    key = np.array(key_rgb, dtype=np.float32)
    dist = np.sqrt(((rgb - key) ** 2).sum(axis=-1))

    inner = float(max(0, tolerance))
    outer = inner + max(1.0, float(softness))
    alpha = np.clip((dist - inner) / (outer - inner), 0.0, 1.0)
    alpha *= base_alpha

    # 去反光：被背景色「染」到的边缘像素，把主导通道压到其他通道的水平
    if despill:
        dom = int(np.argmax(key))
        if key[dom] > 90:  # 只有背景色本身够鲜艳时才处理
            others = [i for i in range(3) if i != dom]
            ref = np.maximum(rgb[..., others[0]], rgb[..., others[1]])
            near_key = (dist < max(outer * 2.0, outer + 60)) | (alpha < 0.99)
            over = rgb[..., dom] > ref
            rgb[..., dom] = np.where(near_key & over, ref, rgb[..., dom])

    out = np.empty(arr.shape, dtype=np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255)
    out[..., 3] = np.clip(alpha * 255.0, 0, 255)
    res = Image.fromarray(out, "RGBA")

    # 收缩 1 像素，把残留的彩色描边一起切掉
    if shrink:
        a = res.getchannel("A").filter(ImageFilter.MinFilter(3))
        res.putalpha(a)
    return res


def flatten_for_gif(rgba: Image.Image, backdrop: tuple[int, int, int] | None = None) -> Image.Image:
    """把 RGBA 合到背景上（backdrop=None 时保留 1 位透明，用于 GIF）。"""
    if backdrop is None:
        return rgba
    bg = Image.new("RGBA", rgba.size, backdrop + (255,))
    return Image.alpha_composite(bg, rgba)


def build_palette(frames: list[Image.Image], colors: int = 255) -> Image.Image | None:
    """给整段动画算一套统一的调色板（跨帧一致，重复颜色不再每帧重存）。"""
    if not frames:
        return None
    colors = max(8, min(255, int(colors)))  # 索引 255 留给透明
    thumbs = []
    for f in frames:
        w = max(1, f.width // 8)
        h = max(1, f.height // 8)
        thumbs.append(f.convert("RGB").resize((w, h)))
    width = max(1, sum(t.width for t in thumbs))
    height = max(1, max(t.height for t in thumbs))
    canvas = Image.new("RGB", (width, height))
    x = 0
    for t in thumbs:
        canvas.paste(t, (x, 0))
        x += t.width
    return canvas.quantize(colors=colors, method=Image.Quantize.MEDIANCUT,
                           dither=Image.Dither.NONE)


def to_p_with_transparency(rgba: Image.Image, alpha_cut: int = 128,
                           palette: Image.Image | None = None) -> Image.Image:
    """转成调色板图，索引 255 留作透明。

    palette 不为空时用它统一量化（体积更小、编码更快）；为空则逐帧 256 色。
    """
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")
    if palette is not None:
        pal_img = rgb.quantize(palette=palette, dither=Image.Dither.NONE)
    else:
        pal_img = rgb.quantize(colors=255, method=Image.Quantize.MEDIANCUT,
                               dither=Image.Dither.NONE)
    mask = alpha.point(lambda a: 255 if a < alpha_cut else 0)
    pal_img.paste(255, mask=mask)
    pal = pal_img.getpalette() or []
    if len(pal) < 768:
        pal = pal + [0] * (768 - len(pal))
    pal_img.putpalette(pal)
    return pal_img


def merge_duplicate_frames(frames: list[Image.Image], durations: list[int]):
    """相邻重复帧合并时长，能明显压小体积。"""
    out_f: list[Image.Image] = []
    out_d: list[int] = []
    prev_bytes = None
    for f, d in zip(frames, durations):
        raw = f.tobytes()
        if prev_bytes is not None and raw == prev_bytes:
            out_d[-1] += d
            continue
        out_f.append(f)
        out_d.append(d)
        prev_bytes = raw
    return out_f, out_d


def thin_frames(frames: list[Image.Image], durations: list[int], step: int = 2):
    """隔帧取样并把时长累加，总时长不变（30fps → 15fps）。"""
    if step <= 1 or len(frames) < 2:
        return frames, durations
    out_f: list[Image.Image] = []
    out_d: list[int] = []
    for i in range(0, len(frames), step):
        out_f.append(frames[i])
        out_d.append(sum(durations[i:i + step]))
    return out_f, out_d


def scale_frames(frames: list[Image.Image], factor: float) -> list[Image.Image]:
    """整体缩放（在抠像前调用更快）。"""
    if not factor or abs(factor - 1.0) < 1e-6:
        return frames
    out = []
    for f in frames:
        w = max(1, int(round(f.width * factor)))
        h = max(1, int(round(f.height * factor)))
        out.append(f.resize((w, h), Image.LANCZOS))
    return out


def save_gif(frames: list[Image.Image], path: str, durations: list[int], loop: int = 0,
             tier: str = "original") -> int:
    """写出 GIF，返回实际写入的帧数（极限档会降帧，比输入帧数少）。"""
    cfg = TIERS.get(tier) or TIERS["original"]
    frames, durations = merge_duplicate_frames(frames, durations)
    if cfg["thin"]:
        frames, durations = thin_frames(frames, durations, 2)
    palette = build_palette(frames, cfg["colors"]) if cfg["colors"] else None
    indexed = [to_p_with_transparency(f, 128, palette) for f in frames]
    durations = [max(20, int(d)) for d in durations]
    # 注意：这里不能用 optimize=True，它会重排调色板，把预留的透明索引换掉，
    # 导致透明区变成实色、主体丢失。
    indexed[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=indexed[1:],
        duration=durations,
        loop=loop,
        transparency=255,
        disposal=2,
        optimize=False,
    )
    return len(indexed)


def save_webp(frames: list[Image.Image], path: str, durations: list[int], loop: int = 0,
              tier: str = "original") -> int:
    """写出动画 WebP，返回实际写入的帧数。"""
    cfg = TIERS.get(tier) or TIERS["original"]
    if cfg["thin"]:
        frames, durations = thin_frames(frames, durations, 2)
    durations = [max(20, int(d)) for d in durations]
    quality = WEBP_QUALITY.get(tier, 90)
    frames[0].save(
        path,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=loop,
        quality=quality,
        # method=6 体积只小 8%，编码却慢 15 倍（60 帧要 117 秒），不值得
        method=4,
        lossless=False,
    )
    return len(frames)
