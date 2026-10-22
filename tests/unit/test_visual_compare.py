"""Offline checks of the screenshot comparison used by the visual regression suite."""
import io

import pytest
from PIL import Image, ImageDraw

from qualitylens import visual

pytestmark = pytest.mark.unit


def png(size=(100, 50), color=(255, 255, 255), box=None, box_color=(0, 0, 0)) -> bytes:
    img = Image.new("RGB", size, color)
    if box:
        ImageDraw.Draw(img).rectangle(box, fill=box_color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_identical_images_pass():
    result = visual.compare(png(), png())
    assert (result.diff_pixels, result.total_pixels, result.diff_image) == (0, 5000, None)
    assert result.passed() and result.ratio == 0


def test_noise_within_the_channel_tolerance_is_ignored():
    assert visual.compare(png(color=(250, 250, 250)), png()).diff_pixels == 0
    assert visual.compare(png(color=(255 - visual.CHANNEL_TOLERANCE,) * 3), png()).diff_pixels == 0
    assert visual.compare(png(color=(255 - visual.CHANNEL_TOLERANCE - 1,) * 3), png()).diff_pixels == 5000


def test_a_change_in_one_channel_counts():
    assert visual.compare(png(color=(255, 255, 200)), png()).diff_pixels == 5000


def test_changed_region_is_counted_and_highlighted():
    result = visual.compare(png(box=(10, 10, 19, 19)), png())
    assert result.diff_pixels == 100
    assert result.ratio == pytest.approx(0.02)
    assert not result.passed()
    assert result.describe() == "100 of 5000 pixels differ (2.000%)"
    diff = Image.open(io.BytesIO(result.diff_image))
    assert diff.format == "PNG" and diff.mode == "RGB"
    assert diff.getpixel((15, 15)) == visual.HIGHLIGHT
    # Unchanged pixels are the baseline faded 70 % towards white, so the change stands out.
    assert diff.getpixel((50, 40)) == (255, 255, 255)
    faded = visual.compare(png(color=(0, 0, 0), box=(0, 0, 0, 0), box_color=(255, 0, 0)), png(color=(0, 0, 0)))
    assert Image.open(io.BytesIO(faded.diff_image)).getpixel((50, 40)) == (178, 178, 178)


def test_the_ratio_threshold_is_inclusive():
    result = visual.compare(png(box=(0, 0, 9, 9)), png())   # 100 px = 2 %
    assert result.passed(max_ratio=0.02)
    assert not result.passed(max_ratio=0.0199)


def test_a_size_change_always_fails():
    result = visual.compare(png(size=(100, 51)), png())
    assert result == visual.Comparison(False, 5100, 5100)
    assert not result.passed(max_ratio=1.0)
    assert result.describe() == "image size changed"


def test_transparency_and_greyscale_are_compared_as_rgb():
    buf = io.BytesIO()
    Image.new("RGBA", (100, 50), (255, 255, 255, 0)).save(buf, format="PNG")
    assert visual.compare(buf.getvalue(), png()).passed()
    buf = io.BytesIO()
    Image.new("L", (100, 50), 255).save(buf, format="PNG")
    assert visual.compare(buf.getvalue(), png()).diff_pixels == 0


def test_paths_and_bytes_are_both_accepted(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(png())
    assert visual.compare(path, png()).passed()


def test_baselines_are_kept_per_gitea_version(tmp_path):
    assert visual.baseline_path("1.22.6", "login", root=tmp_path) == tmp_path / "1.22.6" / "login.png"


def test_committed_baselines_are_real_screenshots():
    shots = sorted(visual.BASELINE_ROOT.glob("*/*.png"))
    assert shots, "no visual baselines committed"
    for shot in shots:
        assert Image.open(shot).width == 1280, shot.name
