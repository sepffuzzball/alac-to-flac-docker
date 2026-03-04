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


def get_env(name: str) -> Optional[str]:
    return os.getenv(name) or os.getenv(name.upper())


APP_VERSION = get_env("APP_VERSION") or "0.1.0"
DEFAULT_POLL_INTERVAL_SECONDS = 2.0


def env_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_poll_interval_seconds() -> float:
    raw = get_env("POLL_INTERVAL_SECONDS")
    if raw is None or raw.strip() == "":
        return DEFAULT_POLL_INTERVAL_SECONDS

    try:
        value = float(raw)
    except ValueError:
        raise SystemExit("POLL_INTERVAL_SECONDS must be a positive number")

    if value <= 0:
        raise SystemExit("POLL_INTERVAL_SECONDS must be greater than 0")

    return value


def parse_id_env(name: str) -> Optional[int]:
    raw = get_env(name)
    if raw is None or raw.strip() == "":
        return None

    value = raw.strip()
    if not value.isdigit():
        raise SystemExit(f"{name} must be a non-negative integer")

    return int(value)


def apply_timezone() -> None:
    timezone = get_env("TZ")
    if timezone is None or timezone.strip() == "":
        return

    os.environ["TZ"] = timezone.strip()
    if hasattr(time, "tzset"):
        try:
            time.tzset()
        except OSError as exc:
            raise SystemExit(f"Failed to apply TZ={timezone!r}: {exc}")


def apply_runtime_identity() -> None:
    target_uid = parse_id_env("PUID")
    target_gid = parse_id_env("PGID")

    if target_uid is None and target_gid is None:
        return

    current_uid = os.getuid()
    current_gid = os.getgid()

    if target_gid is not None and target_gid != current_gid:
        try:
            os.setgid(target_gid)
        except PermissionError as exc:
            raise SystemExit(
                f"Unable to switch to PGID={target_gid}. Run container as root or use --user. ({exc})"
            )

    if target_uid is not None and target_uid != current_uid:
        try:
            os.setuid(target_uid)
        except PermissionError as exc:
            raise SystemExit(
                f"Unable to switch to PUID={target_uid}. Run container as root or use --user. ({exc})"
            )

    logger.info(
        "Running with uid=%s gid=%s (requested PUID=%s PGID=%s)",
        os.getuid(),
        os.getgid(),
        target_uid,
        target_gid,
    )


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


def watch_for_changes(root_path: Path, include_subfolders: bool, poll_interval_seconds: float) -> None:
    seen_states: dict[Path, float] = {}

    logger.info(
        "Watching %s (subfolders=%s, poll_interval_seconds=%s)",
        root_path,
        include_subfolders,
        poll_interval_seconds,
    )
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
                time.sleep(poll_interval_seconds)
                if file_path.exists():
                    convert_m4a_to_flac(file_path)

        for file_path in list(seen_states.keys()):
            if file_path not in current_set:
                seen_states.pop(file_path, None)

        time.sleep(poll_interval_seconds)


def main() -> None:
    apply_timezone()
    apply_runtime_identity()

    path_value = get_env("path")
    if not path_value:
        raise SystemExit("Missing required environment variable: path")

    include_subfolders = env_bool(get_env("subfolder") or "false")
    poll_interval_seconds = get_poll_interval_seconds()

    root_path = Path(path_value).expanduser().resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise SystemExit(f"Configured path is not a directory: {root_path}")

    logger.info("Starting alac-to-flac-docker version %s", APP_VERSION)
    logger.info("Processing existing .m4a files in %s", root_path)
    process_existing_files(root_path, include_subfolders)
    watch_for_changes(root_path, include_subfolders, poll_interval_seconds)


if __name__ == "__main__":
    main()
