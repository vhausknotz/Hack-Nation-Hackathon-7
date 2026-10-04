import subprocess

import pytest

from atlas_mcp.publication_inputs import BUILD_INPUTS, publication_fingerprint


def git(root, *args):
    return subprocess.check_output(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                                    "-c", "commit.gpgSign=false", *args], cwd=root, stderr=subprocess.DEVNULL)


def repository(root):
    git(root, "init")
    (root / "app").mkdir()
    (root / "app/runtime.ts").write_text("original")
    (root / "HANDOFF.md").write_text("checkpoint")
    git(root, "add", ".")
    git(root, "commit", "-m", "initial")
    (root / "data/build").mkdir(parents=True)
    for name in BUILD_INPUTS:
        (root / "data/build" / name).write_text("original")
    (root / "data/sources_manifest.json").write_text("{}")


def test_documentation_commit_does_not_repeat_publication_but_runtime_change_does(tmp_path):
    repository(tmp_path)
    first = publication_fingerprint(tmp_path)
    (tmp_path / "HANDOFF.md").write_text("new checkpoint")
    git(tmp_path, "add", "HANDOFF.md")
    git(tmp_path, "commit", "-m", "docs")
    assert publication_fingerprint(tmp_path) == first
    (tmp_path / "app/runtime.ts").write_text("changed")
    git(tmp_path, "add", "app")
    git(tmp_path, "commit", "-m", "runtime")
    assert publication_fingerprint(tmp_path) != first


def test_generated_data_changes_invalidate_revision_even_without_git_commit(tmp_path):
    repository(tmp_path)
    first = publication_fingerprint(tmp_path)
    path = tmp_path / "data/build/map.json"
    path.write_text("changed!")
    assert publication_fingerprint(tmp_path) != first
    path.write_text("original")
    assert publication_fingerprint(tmp_path) == first
    (tmp_path / "data/build/plain.jsonl").write_text("")
    assert publication_fingerprint(tmp_path) != first  # absent and present differ


def test_missing_required_graph_input_stops_publication(tmp_path):
    repository(tmp_path)
    (tmp_path / "data/build/conditions.jsonl").unlink()
    with pytest.raises(FileNotFoundError, match="conditions.jsonl"):
        publication_fingerprint(tmp_path)


def test_cloud_only_publication_does_not_require_the_website_build(tmp_path):
    repository(tmp_path)
    first = publication_fingerprint(tmp_path, website=False)
    (tmp_path / "data/build/map.json").unlink()
    assert publication_fingerprint(tmp_path, website=False) == first
    (tmp_path / "data/build/conditions.jsonl").write_text("new conditions")
    assert publication_fingerprint(tmp_path, website=False) != first
