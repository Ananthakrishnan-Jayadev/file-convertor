"""Audio and video. Sample files are generated with FFmpeg itself, so these skip without it."""

import pytest
from PIL import Image

from app import tools
from app.compress import shrink
from app.converters import media

from .conftest import needs_ffmpeg

pytestmark = [needs_ffmpeg, pytest.mark.slow]
KB = 1024


def generate(path, *args):
    code, output = tools.run([tools.ffmpeg(), "-hide_banner", "-y", *args, str(path)], timeout=120)
    assert code == 0, output
    return path


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    tone = ["-f", "lavfi", "-i", "sine=frequency=440:duration=6"]
    # testsrc2 has moving detail, so it compresses like real footage rather than a still frame.
    picture = ["-f", "lavfi", "-i", "testsrc2=duration=6:size=640x360:rate=25"]
    return {
        "wav": generate(d / "tone.wav", *tone, "-ac", "2"),
        "mp3": generate(d / "tone.mp3", *tone, "-ac", "2", "-b:a", "192k"),
        "mp4": generate(d / "clip.mp4", *picture, *tone, "-c:v", "libx264", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"),
        "silent": generate(d / "silent.mp4", *picture, "-c:v", "libx264", "-pix_fmt", "yuv420p"),
    }


@pytest.fixture
def copy_of(samples, tmp_path):
    def make(name):
        src = samples[name]
        dst = tmp_path / src.name
        dst.write_bytes(src.read_bytes())
        return dst
    return make


@pytest.mark.parametrize("fmt", sorted(media.AUDIO - {"wav"}))
def test_wav_to_every_audio_format(samples, out_dir, fmt):
    dst = media.convert_audio(samples["wav"], out_dir, fmt)
    assert dst.suffix == f".{fmt}"
    assert media.duration(dst) == pytest.approx(6, abs=0.3)


@pytest.mark.parametrize("fmt", sorted(media.VIDEO - {"mp4"}))
def test_mp4_to_other_video_formats(samples, out_dir, fmt):
    dst = media.convert_video(samples["mp4"], out_dir, fmt)
    assert media.duration(dst) == pytest.approx(6, abs=0.5)


@pytest.mark.parametrize("fmt", ["mp3", "m4a", "wav"])
def test_extract_sound_from_video(samples, out_dir, fmt):
    dst = media.convert_video(samples["mp4"], out_dir, fmt)
    assert media.duration(dst) == pytest.approx(6, abs=0.3)


def test_silent_video_has_no_sound_to_extract(samples, out_dir):
    with pytest.raises(RuntimeError, match="no sound"):
        media.convert_video(samples["silent"], out_dir, "mp3")


def test_video_to_animated_gif(samples, out_dir):
    dst = media.convert_video(samples["mp4"], out_dir, "gif")
    with Image.open(dst) as im:
        assert im.n_frames > 10
        assert im.width <= 640


def test_video_size_limit(copy_of):
    src = copy_of("mp4")
    target = 150 * KB
    assert src.stat().st_size > target
    result = shrink(src, target)
    assert result.met, result.note
    assert result.path.stat().st_size <= target
    assert media.duration(result.path) == pytest.approx(6, abs=0.5)


def test_audio_size_limit(copy_of):
    src = copy_of("mp3")
    target = 40 * KB
    result = shrink(src, target)
    assert result.met, result.note
    assert result.path.stat().st_size <= target


def test_lossless_audio_explains_itself(copy_of):
    result = shrink(copy_of("wav"), 20 * KB)
    assert not result.met
    assert "Convert it to MP3" in result.note


def test_impossibly_small_video_limit(copy_of):
    result = shrink(copy_of("mp4"), 10 * KB)
    assert not result.met
    assert "too long" in result.note
