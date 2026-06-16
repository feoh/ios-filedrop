from __future__ import annotations

from pathlib import Path

import pytest

from ios_filedrop.cli import (  # pyright: ignore[reportMissingImports]
    DEFAULT_FOLDER,
    IosFiledropError,
    choose_non_conflicting_filename,
    default_config_path,
    remote_path,
    validate_destination_name,
)


def test_default_config_path_uses_xdg_state_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    assert default_config_path() == tmp_path / "ios-filedrop" / "rclone.conf"


def test_remote_path_without_parts() -> None:
    assert remote_path("icloud") == "icloud:"


def test_remote_path_with_default_folder_and_file() -> None:
    assert remote_path("icloud", DEFAULT_FOLDER, "paper.pdf") == "icloud:FromLinux/paper.pdf"


def test_remote_path_strips_extra_slashes() -> None:
    assert remote_path("icloud", "/FromLinux/Papers/", "/paper.pdf") == (
        "icloud:FromLinux/Papers/paper.pdf"
    )


def test_choose_non_conflicting_filename_returns_original_when_available() -> None:
    assert choose_non_conflicting_filename("paper.pdf", {"other.pdf"}) == "paper.pdf"


def test_choose_non_conflicting_filename_adds_suffix_before_extension() -> None:
    assert choose_non_conflicting_filename("paper.pdf", {"paper.pdf"}) == "paper-1.pdf"


def test_choose_non_conflicting_filename_skips_existing_suffixes() -> None:
    assert (
        choose_non_conflicting_filename(
            "paper.pdf",
            {"paper.pdf", "paper-1.pdf", "paper-2.pdf"},
        )
        == "paper-3.pdf"
    )


def test_choose_non_conflicting_filename_handles_multi_suffix_names() -> None:
    assert choose_non_conflicting_filename("archive.tar.gz", {"archive.tar.gz"}) == (
        "archive.tar-1.gz"
    )


def test_validate_destination_name_rejects_path_separators() -> None:
    with pytest.raises(IosFiledropError):
        validate_destination_name("nested/paper.pdf")

    with pytest.raises(IosFiledropError):
        validate_destination_name(r"nested\\paper.pdf")


def test_validate_destination_name_rejects_empty_and_dot_names() -> None:
    for name in ["", ".", ".."]:
        with pytest.raises(IosFiledropError):
            validate_destination_name(name)
