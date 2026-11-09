"""Audio and video through FFmpeg."""

from pathlib import Path

from .. import tools
from ..registry import register

AUDIO = {"mp3", "wav", "aac", "m4a", "ogg", "flac", "opus"}
VIDEO = {"mp4", "mov", "webm", "mkv", "avi"}
LOSSLESS_AUDIO = {"wav", "flac"}
TIMEOUT = 60 * 60
GIF_MAX_SECONDS = 30
GIF_FILTER = "fps=12,scale='min(640,iw)':-2:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"
EVEN_SIZE = "scale=trunc(iw/2)*2:trunc(ih/2)*2"  # H.264 needs even width and height

AUDIO_CODECS = {
    "mp3": ["-c:a", "libmp3lame"],
    "wav": ["-c:a", "pcm_s16le"],
    "aac": ["-c:a", "aac"],
    "m4a": ["-c:a", "aac"],
    "ogg": ["-c:a", "libvorbis"],
    "flac": ["-c:a", "flac"],
    "opus": ["-c:a", "libopus"],
}
# Default quality settings for a normal conversion (the size limit uses bitrates instead).
AUDIO_QUALITY = {
    "mp3": ["-q:a", "2"], "aac": ["-b:a", "192k"], "m4a": ["-b:a", "192k"],
    "ogg": ["-q:a", "5"], "opus": ["-b:a", "128k"],
}
# (video codec, audio codec) per container.
VIDEO_CODECS = {
    "mp4": ("libx264", "aac"),
    "mov": ("libx264", "aac"),
    "mkv": ("libx264", "aac"),
    "webm": ("libvpx-vp9", "libopus"),
    "avi": ("mpeg4", "libmp3lame"),
}
VIDEO_QUALITY = {
    "libx264": ["-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", "-vf", EVEN_SIZE],
    "libvpx-vp9": ["-crf", "32", "-b:v", "0", "-row-mt", "1"],
    "mpeg4": ["-q:v", "5"],
}


def ffmpeg(args: list[str], cwd: Path | None = None) -> None:
    exe = tools.ffmpeg()
    if exe is None:
        raise RuntimeError("Audio and video need FFmpeg, which isn't installed on the server.")
    code, output = tools.run([exe, "-hide_banner", "-nostdin", "-y", *args], timeout=TIMEOUT, cwd=cwd)
    if code != 0:
        if "does not contain any stream" in output or "matches no streams" in output:
            raise RuntimeError("This file has no sound to extract.")
        detail = output.strip().splitlines()[-1] if output.strip() else ""
        raise RuntimeError(f"FFmpeg couldn't convert this file. {detail}".strip())


def duration(path: Path) -> float | None:
    """Length in seconds, or None when ffprobe isn't available or can't tell."""
    exe = tools.ffprobe()
    if exe is None:
        return None
    code, output = tools.run([exe, "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=noprint_wrappers=1:nokey=1", str(path)], timeout=60)
    try:
        return float(output.strip().splitlines()[0]) if code == 0 else None
    except (ValueError, IndexError):
        return None


def audio_args(fmt: str) -> list[str]:
    return [*AUDIO_CODECS[fmt], *AUDIO_QUALITY.get(fmt, [])]


def video_args(fmt: str) -> list[str]:
    vcodec, acodec = VIDEO_CODECS[fmt]
    args = ["-c:v", vcodec, *VIDEO_QUALITY[vcodec], "-c:a", acodec]
    if fmt == "mp4":
        args += ["-movflags", "+faststart"]  # lets browsers start playing before the download ends
    return args


@register("audio", AUDIO, AUDIO)
def convert_audio(src: Path, out_dir: Path, fmt: str) -> Path:
    dst = out_dir / f"{src.stem}.{fmt}"
    ffmpeg(["-i", str(src), "-vn", "-map_metadata", "0", *audio_args(fmt), str(dst)])
    return dst


@register("video", VIDEO, VIDEO | AUDIO | {"gif"})
def convert_video(src: Path, out_dir: Path, fmt: str) -> Path:
    dst = out_dir / f"{src.stem}.{fmt}"
    if fmt in AUDIO:
        args = ["-i", str(src), "-vn", *audio_args(fmt)]
    elif fmt == "gif":
        # GIFs get huge fast, so only the first part of a video is used.
        args = ["-t", str(GIF_MAX_SECONDS), "-i", str(src), "-filter_complex", GIF_FILTER, "-loop", "0"]
    else:
        args = ["-i", str(src), *video_args(fmt)]
    ffmpeg([*args, str(dst)])
    return dst
