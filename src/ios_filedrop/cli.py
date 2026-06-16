"""Command-line interface for ios-filedrop."""

from __future__ import annotations

import os
import posixpath
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

import cyclopts

APP_NAME = "ios-filedrop"
DEFAULT_REMOTE = "icloud"
DEFAULT_FOLDER = "FromLinux"
MAX_COLLISION_ATTEMPTS = 10_000

app = cyclopts.App(
    name="ios-filedrop",
    help="Send files from Linux to iCloud Drive for easy access in iOS Files.",
    version="0.1.0",
)


class IosFiledropError(RuntimeError):
    """A user-facing ios-filedrop error."""


def default_config_path() -> Path:
    """Return the isolated rclone config path used by default."""
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / APP_NAME / "rclone.conf"


DEFAULT_CONFIG_PATH = default_config_path()


def rclone_env(config_path: Path) -> dict[str, str]:
    """Return an environment that points rclone at the isolated config file."""
    env = os.environ.copy()
    env["RCLONE_CONFIG"] = str(config_path)
    return env


def ensure_private_config_location(config_path: Path) -> None:
    """Create and permission the private rclone config directory/file if present."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.parent.chmod(0o700)
    if config_path.exists():
        config_path.chmod(0o600)


def require_rclone() -> str:
    """Return the rclone executable path or raise a user-facing error."""
    rclone = shutil.which("rclone")
    if rclone is None:
        raise IosFiledropError(
            "rclone is not installed or is not on PATH. Install rclone, then run "
            "`ios-filedrop setup`."
        )
    return rclone


def run_rclone(
    args: list[str],
    *,
    config_path: Path,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run rclone with the configured isolated config file."""
    rclone = require_rclone()
    ensure_private_config_location(config_path)
    return subprocess.run(  # noqa: S603 - command is intentionally rclone with list args.
        [rclone, *args],
        check=True,
        env=rclone_env(config_path),
        text=True,
        capture_output=capture_output,
    )


def remote_path(remote: str, *parts: str) -> str:
    """Build an rclone remote path from a remote name and POSIX-style path parts."""
    cleaned_parts = [part.strip("/") for part in parts if part and part.strip("/")]
    if not cleaned_parts:
        return f"{remote}:"
    return f"{remote}:{posixpath.join(*cleaned_parts)}"


def validate_destination_name(name: str) -> str:
    """Validate and return a single destination filename."""
    if not name or name in {".", ".."}:
        raise IosFiledropError("Destination filename must not be empty, '.' or '..'.")
    if "/" in name or "\\" in name:
        raise IosFiledropError("Destination filename must not contain path separators.")
    return name


def choose_non_conflicting_filename(desired_name: str, existing_names: set[str]) -> str:
    """Return desired_name or a readable suffixed variant that does not exist."""
    validate_destination_name(desired_name)
    if desired_name not in existing_names:
        return desired_name

    path = Path(desired_name)
    stem = path.stem
    suffix = path.suffix

    for index in range(1, MAX_COLLISION_ATTEMPTS + 1):
        candidate = f"{stem}-{index}{suffix}"
        if candidate not in existing_names:
            return candidate

    raise IosFiledropError(
        f"Could not find a non-conflicting filename for {desired_name!r} after "
        f"{MAX_COLLISION_ATTEMPTS} attempts."
    )


def list_remote_files(*, remote: str, folder: str, config_path: Path) -> set[str]:
    """List files directly in the destination folder."""
    result = run_rclone(
        ["lsf", "--files-only", remote_path(remote, folder)],
        config_path=config_path,
        capture_output=True,
    )
    return {line.strip().rstrip("/") for line in result.stdout.splitlines() if line.strip()}


def fail(message: str) -> NoReturn:
    """Exit with a CLI-friendly error message."""
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


@app.command
def setup(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> None:
    """Run interactive rclone setup using ios-filedrop's private config path."""
    rclone = require_rclone()
    ensure_private_config_location(config_path)
    print(f"Using isolated rclone config: {config_path}")
    print()
    print("In rclone's prompts, create a remote with these recommended values:")
    print(f"  name: {DEFAULT_REMOTE}")
    print("  backend/type: iclouddrive")
    print("  service: drive")
    print()
    print("Your Apple credentials/session will be stored in that config file, not ~/.config.")
    result = subprocess.run(  # noqa: S603 - intentionally runs rclone for interactive config.
        [rclone, "config"],
        check=False,
        env=rclone_env(config_path),
    )
    if config_path.exists():
        config_path.chmod(0o600)
    if result.returncode != 0:
        fail(
            "rclone setup did not complete successfully. See the rclone output above. "
            "If this happened during Apple two-factor authentication, try running "
            "`ios-filedrop setup` again and request an SMS code by entering `sms` "
            "at rclone's 2FA prompt."
        )


@app.command
def check(
    *,
    remote: str = DEFAULT_REMOTE,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> None:
    """Check rclone, the isolated config file, and the configured remote."""
    rclone = require_rclone()
    print(f"rclone: {rclone}")
    print(f"config: {config_path}")

    if not config_path.exists():
        fail(f"Config file does not exist yet. Run `ios-filedrop setup` to create {config_path}.")

    ensure_private_config_location(config_path)
    remotes = run_rclone(["listremotes"], config_path=config_path, capture_output=True)
    remote_names = {line.removesuffix(":") for line in remotes.stdout.splitlines()}
    if remote not in remote_names:
        fail(f"Remote {remote!r} was not found in {config_path}. Run `ios-filedrop setup`.")

    run_rclone(
        ["lsf", "--max-depth", "1", remote_path(remote)],
        config_path=config_path,
        capture_output=True,
    )
    print(f"remote: {remote} OK")


@app.default
def upload(
    file: Path,
    *,
    folder: str = DEFAULT_FOLDER,
    name: str | None = None,
    remote: str = DEFAULT_REMOTE,
    config_path: Path = DEFAULT_CONFIG_PATH,
    dry_run: bool = False,
) -> None:
    """Upload FILE to the configured Files-visible destination."""
    try:
        if not file.exists():
            raise IosFiledropError(f"Local file does not exist: {file}")
        if not file.is_file():
            raise IosFiledropError(f"Local path is not a regular file: {file}")

        desired_name = validate_destination_name(name or file.name)
        folder = folder.strip("/") or DEFAULT_FOLDER

        if dry_run:
            destination = remote_path(remote, folder, desired_name)
            print("Dry run: no files uploaded and no remote collision check performed.")
            print(f"RCLONE_CONFIG={config_path}")
            print(f"rclone mkdir {remote_path(remote, folder)}")
            print(f"rclone copyto {file} {destination}")
            return

        run_rclone(["mkdir", remote_path(remote, folder)], config_path=config_path)
        existing_names = list_remote_files(
            remote=remote,
            folder=folder,
            config_path=config_path,
        )
        chosen_name = choose_non_conflicting_filename(desired_name, existing_names)
        destination = remote_path(remote, folder, chosen_name)
        run_rclone(["copyto", str(file), destination], config_path=config_path)
        print(f"Uploaded {file} to {destination}")
        if chosen_name != desired_name:
            print(f"Destination name changed to avoid a collision: {chosen_name}")
    except (IosFiledropError, subprocess.CalledProcessError) as error:
        fail(str(error))


def main() -> None:
    """Run the ios-filedrop CLI."""
    app()
