from pathlib import Path

import pytest

from hermes_forge.paths import ensure_under


def test_ensure_under_blocks_escape(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("x")
    with pytest.raises(ValueError):
        ensure_under(outside, root)
