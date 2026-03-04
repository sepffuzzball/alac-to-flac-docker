import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2


def env_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_env(name: str) -> Optional[str]:
    return os.getenv(name) or os.getenv(name.upper())


def ffprobe_stream_info(file_path: Path) -> tuple[Optional[int], Optional[int]]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate,bits_per_raw_sample",
        "-of",
        "default=noprint_wrappers=1:nokey=0",
        str(file_path),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        logger.warning("ffprobe failed for %s: %s", file_path, exc.stderr.strip())
        return None, None

    sample_rate: Optional[int] = None
    bits_per_raw_sample: Optional[int] = None
    for line in result.stdout.splitlines():
        if line.startswith("sample_rate="):
            value = line.split("=", maxsplit=1)[1].strip()
            sample_rate = int(value) if value.isdigit() else None
        elif line.startswith("bits_per_raw_sample="):
            value = line.split("=", maxsplit=1)[1].strip()
            bits_per_raw_sample = int(value) if value.isdigit() else None

    return sample_rate, bits_per_raw_sample


def convert_m4a_to_flac(source_file: Path) -> bool:
    target_file = source_file.with_suffix(".flac")
    temp_output = target_file.with_suffix(".flac.part")

    if temp_output.exists():
        temp_output.unlink()

    sample_rate, bits_per_raw_sample = ffprobe_stream_info(source_file)

    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(source_file),
        "-map",
        "0:a:0",
        "-c:a",
        "flac",
        "-compression_level",
        "12",
    ]

    if sample_rate is not None:
        cmd.extend(["-ar", str(sample_rate)])
    if bits_per_raw_sample is not None:
        cmd.extend(["-bits_per_raw_sample", str(bits_per_raw_sample)])

    cmd.append(str(temp_output))

    logger.info("Converting %s -> %s", source_file, target_file)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        logger.exception("Conversion failed for %s", source_file)
        if temp_output.exists():
            temp_output.unlink()
        return False

    temp_output.replace(target_file)
    source_file.unlink()
    logger.info("Converted and replaced %s", source_file)
    return True


def find_m4a_files(root_path: Path, include_subfolders: bool) -> list[Path]:
    pattern = "**/*.m4a" if include_subfolders else "*.m4a"
    return [path for path in sorted(root_path.glob(pattern)) if path.is_file()]


def process_existing_files(root_path: Path, include_subfolders: bool) -> None:
    for file_path in find_m4a_files(root_path, include_subfolders):
        convert_m4a_to_flac(file_path)


def watch_for_changes(root_path: Path, include_subfolders: bool) -> None:
    seen_states: dict[Path, float] = {}

    logger.info("Watching %s (subfolders=%s)", root_path, include_subfolders)
    while True:
        candidates = find_m4a_files(root_path, include_subfolders)
        current_set = set(candidates)

        for file_path in candidates:
            try:
                mtime = file_path.stat().st_mtime
            except FileNotFoundError:
                continue

            previous = seen_states.get(file_path)
            if previous is None or mtime > previous:
                seen_states[file_path] = mtime
                # wait one polling cycle to reduce chance of converting partial write
                time.sleep(POLL_INTERVAL_SECONDS)
                if file_path.exists():
                    convert_m4a_to_flac(file_path)

        for file_path in list(seen_states.keys()):
            if file_path not in current_set:
                seen_states.pop(file_path, None)

        time.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    path_value = get_env("path")
    if not path_value:
        raise SystemExit("Missing required environment variable: path")

    include_subfolders = env_bool(get_env("subfolder") or "false")

    root_path = Path(path_value).expanduser().resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise SystemExit(f"Configured path is not a directory: {root_path}")

    logger.info("Processing existing .m4a files in %s", root_path)
    process_existing_files(root_path, include_subfolders)
    watch_for_changes(root_path, include_subfolders)


if __name__ == "__main__":
    main()
