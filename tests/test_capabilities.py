"""Capability loader: parsing, validation and context assembly.

No network here — _fetch() is the only part that talks to git, and these cover
everything after it against a repository laid out on disk.
"""

import pytest

from jellyclaw.agents.base import Agent
from jellyclaw.capabilities import (
    Capability,
    CapabilityError,
    _parse,
    _read_documents,
    teach,
)

META = """\
schema: heepx.capability/v1
id: demo
version: 1.2.3
capability: Does one thing well.
improves:
  - a thing
does_not_improve:
  - another thing
license: MIT
evaluation:
  suite: eval/tasks.jsonl
  scorer: eval/score.py
  run: python3 eval/score.py
load_order:
  - path: spec/core.md
    cost: small
    sufficient_alone: true
  - path: spec/SPEC.md
    cost: medium
"""


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec" / "core.md").write_text("CORE CONTENT")
    (tmp_path / "spec" / "SPEC.md").write_text("FULL SPEC")
    (tmp_path / "CAPABILITY.yaml").write_text(META)
    return tmp_path


def test_parses_a_conforming_descriptor(repo):
    meta = _parse(repo)
    assert meta["id"] == "demo"
    assert meta["version"] == "1.2.3"


def test_missing_descriptor_names_the_standard(repo):
    (repo / "CAPABILITY.yaml").unlink()
    with pytest.raises(CapabilityError) as exc:
        _parse(repo)
    assert "not a HeepX capability repository" in str(exc.value)


def test_missing_required_key_is_reported(repo):
    (repo / "CAPABILITY.yaml").write_text(META.replace("license: MIT\n", ""))
    with pytest.raises(CapabilityError) as exc:
        _parse(repo)
    assert "license" in str(exc.value)  # says which key, not just "invalid"


def test_unknown_schema_version_is_refused(repo):
    (repo / "CAPABILITY.yaml").write_text(
        META.replace("heepx.capability/v1", "heepx.capability/v99")
    )
    with pytest.raises(CapabilityError) as exc:
        _parse(repo)
    assert "v99" in str(exc.value)


def test_load_order_is_read_in_order(repo):
    docs = _read_documents(repo, _parse(repo), minimal=False)
    assert [d.path for d in docs] == ["spec/core.md", "spec/SPEC.md"]
    assert docs[0].text == "CORE CONTENT"


def test_minimal_loads_only_the_sufficient_file(repo):
    docs = _read_documents(repo, _parse(repo), minimal=True)
    assert [d.path for d in docs] == ["spec/core.md"]


def test_unresolvable_load_order_path_fails_loudly(repo):
    (repo / "spec" / "SPEC.md").unlink()
    with pytest.raises(CapabilityError) as exc:
        _read_documents(repo, _parse(repo), minimal=False)
    assert "spec/SPEC.md" in str(exc.value)


def _capability(repo):
    meta = _parse(repo)
    return Capability(
        id=meta["id"],
        version=meta["version"],
        summary_line=meta["capability"],
        spec="XYZ-1",
        does_not_improve=meta["does_not_improve"],
        ref="v1.2.3",
        commit="abc1234def",
        source="https://github.com/HeepX/demo",
        documents=_read_documents(repo, meta, minimal=False),
    )


def test_context_carries_provenance_and_content(repo):
    text = _capability(repo).context()
    assert "demo 1.2.3 (XYZ-1)" in text
    assert "@v1.2.3 [abc1234]" in text     # pinned ref and commit, auditable
    assert "CORE CONTENT" in text
    assert "another thing" in text          # negative scope reaches the model


def test_audit_line_names_version_and_documents(repo):
    line = _capability(repo).audit()
    assert "demo 1.2.3" in line and "abc1234" in line
    assert "spec/core.md" in line


def test_teach_prepends_without_losing_the_role_prompt(repo):
    agent = Agent("CEO", "llama3", None, "You are the CEO.")
    teach(agent, _capability(repo))
    assert "You are the CEO." in agent.system_prompt
    assert "CORE CONTENT" in agent.system_prompt
    assert agent.system_prompt.index("CORE CONTENT") < agent.system_prompt.index(
        "You are the CEO."
    )


def test_teach_with_no_capabilities_is_a_no_op(repo):
    agent = Agent("CEO", "llama3", None, "You are the CEO.")
    teach(agent)
    assert agent.system_prompt == "You are the CEO."
