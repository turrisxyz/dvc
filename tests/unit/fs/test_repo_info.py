import os

import pytest

from dvc.fs.repo import RepoFileSystem
from tests.unit.fs.test_repo import make_subrepo


@pytest.fixture
def repo_fs(tmp_dir, dvc, scm):
    fs_structure = {
        "models": {  # mixed dvc + git directory
            "train.py": "train dot py",
            "test.py": "test dot py",
        },
        "README.md": "my little project",  # file
        "src": {  # repo-only directory
            "utils": {
                "__init__.py": "",
                "serve_model.py": "# this will serve a model `soon`",
            }
        },
    }
    dvc_structure = {
        "data": {  # dvc only directory
            "raw": {
                "raw-1.csv": "one, dot, csv",
                "raw-2.csv": "two, dot, csv",
            },
            "processed": {
                "processed-1.csv": "1, dot, csv",
                "processed-2.csv": "2, dot, csv",
            },
        },
        os.path.join("models", "transform.pickle"): "model model",  # file
    }

    tmp_dir.scm_gen(fs_structure, commit="repo init")
    tmp_dir.dvc_gen(dvc_structure, commit="use dvc")

    yield RepoFileSystem(repo=dvc, subrepos=True)


def test_info_not_existing(repo_fs):
    with pytest.raises(FileNotFoundError):
        repo_fs.info("path/that/does/not/exist")


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "models/train.py",
        "models/test.py",
        "src/utils/__init__.py",
        "src/utils/serve_model.py",
    ],
)
def test_info_git_tracked_file(repo_fs, path):
    info = repo_fs.info(path)

    assert info["repo"].root_dir == repo_fs.repo.root_dir
    assert "dvc_info" not in info
    assert info["type"] == "file"
    assert not info["isexec"]


@pytest.mark.parametrize(
    "path",
    [
        "data/raw/raw-1.csv",
        "data/raw/raw-2.csv",
        "data/processed/processed-1.csv",
        "data/processed/processed-2.csv",
        "models/transform.pickle",
    ],
)
def test_info_dvc_tracked_file(repo_fs, path):
    info = repo_fs.info(path)

    assert info["repo"].root_dir == repo_fs.repo.root_dir
    assert info["dvc_info"]["isdvc"]
    assert info["type"] == "file"
    assert not info["isexec"]


@pytest.mark.parametrize("path", ["src", "src/utils"])
def test_info_git_only_dirs(repo_fs, path):
    info = repo_fs.info(path)

    assert info["repo"].root_dir == repo_fs.repo.root_dir
    assert "dvc_info" not in info
    assert info["type"] == "directory"
    assert not info["isexec"]


@pytest.mark.parametrize("path", [".", "models"])
def test_info_git_dvc_mixed_dirs(repo_fs, path):
    info = repo_fs.info(path)

    assert info["repo"].root_dir == repo_fs.repo.root_dir
    assert not info["dvc_info"]["isdvc"]
    assert info["type"] == "directory"
    assert not info["isexec"]


@pytest.mark.parametrize(
    "path",
    [
        "data",
        "data/raw",
        "data/processed",
    ],
)
def test_info_dvc_only_dirs(repo_fs, path):
    info = repo_fs.info(path)

    assert info["repo"].root_dir == repo_fs.repo.root_dir
    assert info["dvc_info"]["isdvc"]
    assert info["type"] == "directory"
    assert not info["isexec"]


def test_info_on_subrepos(make_tmp_dir, tmp_dir, dvc, scm, repo_fs):
    subrepo = tmp_dir / "subrepo"
    make_subrepo(subrepo, scm)
    with subrepo.chdir():
        subrepo.scm_gen("foo", "foo", commit="add foo on subrepo")
        subrepo.dvc_gen("foobar", "foobar", commit="add foobar on subrepo")

    for path in [
        "subrepo",
        "subrepo/foo",
        "subrepo/foobar",
    ]:
        info = repo_fs.info(path)
        assert info["repo"].root_dir == str(
            subrepo
        ), f"repo root didn't match for {path}"

    # supports external outputs on top-level DVC repo
    external_dir = make_tmp_dir("external-output")
    external_dir.gen("bar", "bar")
    dvc.add(str(external_dir / "bar"), external=True)
    info = repo_fs.info((external_dir / "bar").fs_path)
    assert info["repo"].root_dir == str(tmp_dir)
