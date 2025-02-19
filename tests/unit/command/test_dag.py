import networkx as nx
import pytest

from dvc.cli import main, parse_args
from dvc.commands.dag import (
    CmdDAG,
    _build,
    _show_ascii,
    _show_dot,
    _show_mermaid,
)


@pytest.mark.parametrize(
    "fmt, formatter",
    [
        (None, "_show_ascii"),
        ("--dot", "_show_dot"),
        ("--mermaid", "_show_mermaid"),
        ("--md", "_show_mermaid"),
    ],
)
def test_dag(tmp_dir, dvc, mocker, fmt, formatter):
    from dvc.commands import dag

    tmp_dir.dvc_gen("foo", "foo")

    args = ["dag", "--full", "foo.dvc"]
    if fmt:
        args.append(fmt)
    cli_args = parse_args(args)
    assert cli_args.func == CmdDAG

    fmt_func = mocker.spy(dag, formatter)

    cmd = cli_args.func(cli_args)

    mocker.patch("dvc.commands.dag._build", return_value=dvc.index.graph)

    assert cmd.run() == 0

    assert fmt_func.called


@pytest.fixture
def repo(tmp_dir, dvc):
    tmp_dir.dvc_gen("a", "a")
    tmp_dir.dvc_gen("b", "b")

    dvc.run(
        no_exec=True, deps=["a", "c"], outs=["d", "e"], cmd="cmd1", name="1"
    )
    dvc.run(
        no_exec=True, deps=["b", "c"], outs=["f", "g"], cmd="cmd2", name="2"
    )
    dvc.run(
        no_exec=True,
        deps=["a", "b", "c"],
        outs=["h", "i"],
        cmd="cmd3",
        name="3",
    )
    dvc.run(no_exec=True, deps=["a", "h"], outs=["j"], cmd="cmd4", name="4")

    return dvc


def test_build(repo):
    assert nx.is_isomorphic(_build(repo), repo.index.graph)


def test_build_target(repo):
    G = _build(repo, target="3")
    assert set(G.nodes()) == {"3", "b.dvc", "a.dvc"}
    assert set(G.edges()) == {("3", "a.dvc"), ("3", "b.dvc")}


def test_build_target_with_outs(repo):
    G = _build(repo, target="3", outs=True)
    assert set(G.nodes()) == {"a", "b", "h", "i"}
    assert set(G.edges()) == {("i", "a"), ("i", "b"), ("h", "a"), ("h", "b")}


def test_build_granular_target_with_outs(repo):
    G = _build(repo, target="h", outs=True)
    assert set(G.nodes()) == {"a", "b", "h"}
    assert set(G.edges()) == {("h", "a"), ("h", "b")}


def test_build_full(repo):
    G = _build(repo, target="3", full=True)
    assert nx.is_isomorphic(G, repo.index.graph)


# NOTE: granular or not, full outs DAG should be the same
@pytest.mark.parametrize("granular", [True, False])
def test_build_full_outs(repo, granular):
    target = "h" if granular else "3"
    G = _build(repo, target=target, outs=True, full=True)
    assert set(G.nodes()) == {"j", "i", "d", "b", "g", "f", "e", "a", "h"}
    assert set(G.edges()) == {
        ("d", "a"),
        ("e", "a"),
        ("f", "b"),
        ("g", "b"),
        ("h", "a"),
        ("h", "b"),
        ("i", "a"),
        ("i", "b"),
        ("j", "a"),
        ("j", "h"),
    }


def test_show_ascii(repo):
    assert [
        line.rstrip() for line in _show_ascii(repo.index.graph).splitlines()
    ] == [
        "                        +----------------+                          +----------------+",  # noqa: E501
        "                        | stage: 'a.dvc' |                          | stage: 'b.dvc' |",  # noqa: E501
        "                       *+----------------+****                      +----------------+",  # noqa: E501
        "                  *****           *           *****                  ***           ***",  # noqa: E501
        "              ****                *                *****           **                 **",  # noqa: E501
        "           ***                     *                    ***      **                     **",  # noqa: E501
        "+------------+                     **                   +------------+              +------------+",  # noqa: E501
        "| stage: '1' |                       **                 | stage: '3' |              | stage: '2' |",  # noqa: E501
        "+------------+                         ***              +------------+              +------------+",  # noqa: E501
        "                                          **           ***",
        "                                            **       **",
        "                                              **   **",
        "                                          +------------+",
        "                                          | stage: '4' |",
        "                                          +------------+",
    ]


def test_show_dot(repo):
    assert _show_dot(repo.index.graph) == (
        "strict digraph  {\n"
        "stage;\n"
        "stage;\n"
        "stage;\n"
        "stage;\n"
        "stage;\n"
        "stage;\n"
        "\"stage: '1'\" -> \"stage: 'a.dvc'\";\n"
        "\"stage: '2'\" -> \"stage: 'b.dvc'\";\n"
        "\"stage: '3'\" -> \"stage: 'a.dvc'\";\n"
        "\"stage: '3'\" -> \"stage: 'b.dvc'\";\n"
        "\"stage: '4'\" -> \"stage: 'a.dvc'\";\n"
        "\"stage: '4'\" -> \"stage: '3'\";\n"
        "}\n"
    )


def test_show_mermaid(repo):
    assert [
        line.rstrip() for line in _show_mermaid(repo.index.graph).splitlines()
    ] == [
        "flowchart TD",
        "\tnode1[stage: '1']",
        "\tnode2[stage: '2']",
        "\tnode3[stage: '3']",
        "\tnode4[stage: '4']",
        "\tnode5[stage: 'a.dvc']",
        "\tnode6[stage: 'b.dvc']",
        "\tnode3-->node4",
        "\tnode5-->node1",
        "\tnode5-->node3",
        "\tnode5-->node4",
        "\tnode6-->node2",
        "\tnode6-->node3",
    ]


def test_show_mermaid_markdown(repo, dvc, capsys, mocker):
    mocker.patch("dvc.commands.dag._build", return_value=dvc.index.graph)

    capsys.readouterr()
    assert main(["dag", "--md"]) == 0
    assert [
        line.rstrip() for line in capsys.readouterr().out.splitlines()
    ] == [
        "```mermaid",
        "flowchart TD",
        "\tnode1[stage: '1']",
        "\tnode2[stage: '2']",
        "\tnode3[stage: '3']",
        "\tnode4[stage: '4']",
        "\tnode5[stage: 'a.dvc']",
        "\tnode6[stage: 'b.dvc']",
        "\tnode3-->node4",
        "\tnode5-->node1",
        "\tnode5-->node3",
        "\tnode5-->node4",
        "\tnode6-->node2",
        "\tnode6-->node3",
        "```",
    ]
