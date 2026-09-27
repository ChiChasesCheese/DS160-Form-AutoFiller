"""DS-160 photo: convert, crop to the State Department composition rules, encode under the size cap, verify.

Rules (travel.state.gov "Photo Requirements", digital image for the DS-160):
  - square, 600x600 .. 1200x1200 px, JPEG, <= 240 kB, colour, plain white/off-white background
  - head height (top of hair to bottom of chin) = 50%..69% of the image height
  - eye line = 56%..69% of the image height measured from the BOTTOM

Landmarks (hair top, eye line, chin — y pixel rows in the source image) come from a person or an agent
looking at the photo; the crop itself is pure geometry, so it is deterministic and testable.
"""

from __future__ import annotations

import io
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

MIN_PX, MAX_PX, MAX_BYTES = 600, 1200, 240 * 1024
HEAD_RANGE, EYES_FROM_BOTTOM = (0.50, 0.69), (0.56, 0.69)
TARGET_HEAD, TARGET_EYES = 0.60, 0.62  # centre of the allowed bands


@dataclass(frozen=True)
class Crop:
    left: int
    top: int
    side: int

    def ratios(self, hair: float, eyes: float, chin: float) -> tuple[float, float]:
        head = (chin - hair) / self.side
        eyes_from_bottom = (self.top + self.side - eyes) / self.side
        return head, eyes_from_bottom


def plan_crop(width: int, height: int, hair: float, eyes: float, chin: float, face_x: float | None = None) -> Crop:
    """Largest-resolution square crop that puts head size and eye line inside the allowed bands."""
    head_px = chin - hair
    if head_px <= 0 or not hair < eyes < chin:
        raise ValueError("landmarks must satisfy hair < eyes < chin")
    side = min(int(head_px / TARGET_HEAD), width, height)
    lo, hi = head_px / HEAD_RANGE[1], head_px / HEAD_RANGE[0]  # side must keep head within 50..69%
    if side < lo:
        raise ValueError(f"image too small/tight: need side >= {lo:.0f}px to keep head <= 69%")
    side = int(min(max(side, lo), hi, width, height))
    top = round(eyes - (1 - TARGET_EYES) * side)  # eye line at TARGET_EYES from the bottom
    top = max(0, min(top, height - side))
    cx = face_x if face_x is not None else width / 2
    left = max(0, min(round(cx - side / 2), width - side))
    return Crop(left, top, side)


def to_jpeg_source(src: Path, workdir: Path) -> Path:
    """HEIC/HEIF -> JPEG (macOS `sips`, else pillow-heif); other formats pass through."""
    if src.suffix.lower() not in {".heic", ".heif"}:
        return src
    out = workdir / (src.stem + ".jpg")
    if shutil.which("sips"):
        subprocess.run(["sips", "-s", "format", "jpeg", str(src), "--out", str(out)], check=True, capture_output=True)
        return out
    from PIL import Image
    from pillow_heif import register_heif_opener  # optional dependency

    register_heif_opener()
    Image.open(src).convert("RGB").save(out, quality=95)
    return out


def render(src: Path, crop: Crop, out: Path, size: int = MAX_PX) -> dict:
    """Crop, resize to `size`, encode at the highest JPEG quality that fits under 240 kB."""
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    img = img.crop((crop.left, crop.top, crop.left + crop.side, crop.top + crop.side))
    img = img.resize((size, size), Image.LANCZOS)
    for q in range(95, 40, -5):
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=q, optimize=True)
        if buf.tell() <= MAX_BYTES:
            out.write_bytes(buf.getvalue())
            return {"quality": q, "bytes": buf.tell(), "size": size}
    raise ValueError("cannot encode under 240 kB")


def check(path: Path, hair: float, eyes: float, chin: float, crop: Crop) -> list[str]:
    """Return a list of rule violations (empty = compliant)."""
    from PIL import Image

    problems = []
    img = Image.open(path)
    w, h = img.size
    if w != h:
        problems.append(f"not square: {w}x{h}")
    if not MIN_PX <= w <= MAX_PX:
        problems.append(f"size {w}px outside {MIN_PX}..{MAX_PX}")
    if img.format != "JPEG":
        problems.append(f"format {img.format}, need JPEG")
    if img.mode != "RGB":
        problems.append(f"mode {img.mode}, need colour RGB")
    if path.stat().st_size > MAX_BYTES:
        problems.append(f"{path.stat().st_size} bytes > 240 kB")
    head, eyes_b = crop.ratios(hair, eyes, chin)
    if not HEAD_RANGE[0] <= head <= HEAD_RANGE[1]:
        problems.append(f"head {head:.0%} outside 50-69%")
    if not EYES_FROM_BOTTOM[0] <= eyes_b <= EYES_FROM_BOTTOM[1]:
        problems.append(f"eyes {eyes_b:.0%} from bottom outside 56-69%")
    return problems
