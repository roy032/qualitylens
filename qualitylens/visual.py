"""Visual regression: compare a screenshot with an approved baseline image.

Screenshots only match across machines when the browser, fonts and renderer are identical, so the
visual suite runs inside the pinned Playwright Docker image (see `make visual`). Baselines are kept
per Gitea version in tests/visual/baseline/<version>/, because an upgrade is expected to change
the look of most screens.

Two pixels count as "different" when any colour channel differs by more than `CHANNEL_TOLERANCE`,
which absorbs anti-aliasing noise. A screen fails when more than `MAX_DIFF_RATIO` of its pixels
differ, or when its size changed.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops

BASELINE_ROOT = Path(__file__).resolve().parents[1] / "tests" / "visual" / "baseline"
CHANNEL_TOLERANCE = 16      # out of 255
MAX_DIFF_RATIO = 0.002      # 0.2 % of the pixels
HIGHLIGHT = (255, 0, 255)   # magenta marks changed pixels in the diff image


@dataclass(frozen=True)
class Comparison:
    size_matches: bool
    diff_pixels: int
    total_pixels: int
    diff_image: bytes | None = None   # PNG: baseline faded, changed pixels in magenta

    @property
    def ratio(self) -> float:
        return self.diff_pixels / self.total_pixels if self.total_pixels else 0.0

    def passed(self, max_ratio: float = MAX_DIFF_RATIO) -> bool:
        return self.size_matches and self.ratio <= max_ratio

    def describe(self) -> str:
        if not self.size_matches:
            return "image size changed"
        return f"{self.diff_pixels} of {self.total_pixels} pixels differ ({self.ratio:.3%})"


def _load(png: bytes | Path) -> Image.Image:
    data = png.read_bytes() if isinstance(png, Path) else png
    return Image.open(io.BytesIO(data)).convert("RGB")


def compare(actual: bytes | Path, baseline: bytes | Path, tolerance: int = CHANNEL_TOLERANCE) -> Comparison:
    a, b = _load(actual), _load(baseline)
    if a.size != b.size:
        return Comparison(False, a.width * a.height, a.width * a.height)
    # A pixel is changed when its largest channel difference exceeds the tolerance.
    delta = ImageChops.difference(a, b)
    mask = Image.eval(ImageChops.lighter(ImageChops.lighter(*delta.split()[:2]), delta.split()[2]),
                      lambda v: 255 if v > tolerance else 0)
    changed = mask.histogram()[255]
    diff_image = None
    if changed:
        faded = Image.blend(b, Image.new("RGB", b.size, "white"), 0.7)
        faded.paste(Image.new("RGB", b.size, HIGHLIGHT), mask=mask)
        buf = io.BytesIO()
        faded.save(buf, format="PNG")
        diff_image = buf.getvalue()
    return Comparison(True, changed, a.width * a.height, diff_image)


def baseline_path(version: str, name: str, root: Path = BASELINE_ROOT) -> Path:
    return root / version / f"{name}.png"
