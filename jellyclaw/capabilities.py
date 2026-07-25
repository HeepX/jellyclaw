"""Capability loader: fetch a HeepX capability repository and hand its content
to an agent as context.

    import jellyclaw
    cap = jellyclaw.learn("warrant")
    agent.system_prompt += cap.context()

A capability repository is text plus an evaluation suite that makes a model
better at one thing — `warrant` (justify a claim before asserting it),
`reasoning` (structure work as a commitment graph). They are described by a
CAPABILITY.yaml conforming to the HeepX standard:

    https://github.com/HeepX/standard

Loading one = clone or fetch into ~/.jellyclaw/capabilities, check out a
release tag, parse CAPABILITY.yaml, and read the files its `load_order` names.
Nothing else in JellyClaw changes.

Tags, not branches. HXS-SEC-02 in the standard is explicit that these
repositories are loaded into a model's context by design, which makes their
text a supply chain for behaviour, and that consumers must pin a reviewed
commit rather than track a moving branch. So the default ref is the newest
release tag, and the exact commit is recorded on every load.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from jellyclaw.storage.db import state_dir

log = logging.getLogger(__name__)

CAPABILITY_ORG = "HeepX"

# HXS-META: keys a conforming CAPABILITY.yaml must carry. Mirrors the
# `required` list in standard/schema/capability.schema.json.
REQUIRED_KEYS = (
    "schema", "id", "version", "capability", "improves",
    "does_not_improve", "evaluation", "load_order", "license",
)
SUPPORTED_SCHEMA = "heepx.capability/v1"


class CapabilityError(RuntimeError):
    """A capability could not be fetched, parsed, or validated."""


@dataclass
class Document:
    path: str
    cost: str
    text: str
    role: str = ""


@dataclass
class Capability:
    id: str
    version: str
    summary_line: str
    ref: str
    commit: str
    source: str
    spec: str = ""
    improves: list = field(default_factory=list)
    does_not_improve: list = field(default_factory=list)
    documents: list = field(default_factory=list)

    def context(self) -> str:
        """The capability as a block suitable for prepending to a system prompt.

        Provenance is included on purpose: a model reading this should be able
        to say which capability, which version, and which commit shaped it.
        """
        head = [
            f"# Capability: {self.id} {self.version}"
            + (f" ({self.spec})" if self.spec else ""),
            f"# Source: {self.source}@{self.ref} [{self.commit[:7]}]",
            "",
            self.summary_line.strip(),
        ]
        if self.does_not_improve:
            head += ["", "This capability does NOT cover:"]
            head += [f"- {item}" for item in self.does_not_improve]
        body = [
            f"\n--- {doc.path} ---\n{doc.text.strip()}" for doc in self.documents
        ]
        return "\n".join(head) + "\n" + "\n".join(body) + "\n"

    def audit(self) -> str:
        """One line naming exactly what was loaded. Never load silently."""
        size = sum(len(d.text) for d in self.documents)
        docs = ", ".join(d.path for d in self.documents) or "none"
        return (
            f"{self.id} {self.version}"
            + (f" ({self.spec})" if self.spec else "")
            + f" from {self.source}@{self.ref} [{self.commit[:7]}] "
            f"— {len(self.documents)} document(s), {size:,} chars: {docs}"
        )


def cache_dir() -> Path:
    """~/.jellyclaw/capabilities (honours JELLYCLAW_HOME, like the database)."""
    d = state_dir() / "capabilities"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise CapabilityError(
            f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def _fetch(name: str, ref: str | None) -> tuple[Path, str, str, str]:
    """Clone or update the repository, check out `ref`, return its location.

    Uses the machine's existing git configuration and credentials; nothing here
    handles tokens.
    """
    url = f"https://github.com/{CAPABILITY_ORG}/{name}"
    repo = cache_dir() / name

    if not (repo / ".git").is_dir():
        _git("clone", "--quiet", url, str(repo))
    else:
        _git("fetch", "--quiet", "--tags", "--prune", "origin", cwd=repo)

    if ref is None:
        ref = _latest_tag(repo)
    _git("checkout", "--quiet", ref, cwd=repo)
    return repo, ref, _git("rev-parse", "HEAD", cwd=repo), url


def _latest_tag(repo: Path) -> str:
    """Newest release tag, or the default branch when a repository has none.

    An untagged capability is usable but unpinned, so it is worth a warning:
    the whole point of a tag here is that the text cannot change under you.
    """
    tags = _git("tag", "--sort=-v:refname", cwd=repo).splitlines()
    if tags:
        return tags[0].strip()
    head = _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=repo)
    log.warning(
        "%s has no release tags; tracking %s unpinned (see HXS-SEC-02)",
        repo.name, head,
    )
    return head


def _parse(repo: Path) -> dict:
    path = repo / "CAPABILITY.yaml"
    if not path.is_file():
        raise CapabilityError(
            f"{path} not found — not a HeepX capability repository "
            f"(see https://github.com/{CAPABILITY_ORG}/standard)"
        )
    meta = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise CapabilityError(f"{path} is not a YAML mapping")

    missing = [k for k in REQUIRED_KEYS if k not in meta]
    if missing:
        raise CapabilityError(
            f"{path} is missing required key(s): {', '.join(missing)}"
        )
    if meta["schema"] != SUPPORTED_SCHEMA:
        raise CapabilityError(
            f"{path} declares schema {meta['schema']!r}; "
            f"this loader understands {SUPPORTED_SCHEMA!r}"
        )
    return meta


def _read_documents(repo: Path, meta: dict, minimal: bool) -> list:
    """Read the files `load_order` names, in the order it names them.

    `minimal=True` loads only the entry the repository marks
    `sufficient_alone` — the smallest file that still delivers most of the
    value, which is what that field exists to identify.
    """
    entries = meta.get("load_order") or []
    if not isinstance(entries, list) or not entries:
        raise CapabilityError("CAPABILITY.yaml has an empty load_order")

    if minimal:
        chosen = [e for e in entries if e.get("sufficient_alone")] or entries[:1]
    else:
        chosen = entries

    documents = []
    for entry in chosen:
        rel = entry.get("path")
        if not rel:
            raise CapabilityError(f"load_order entry has no path: {entry!r}")
        target = repo / rel
        if not target.is_file():
            raise CapabilityError(f"load_order path does not resolve: {rel}")
        documents.append(
            Document(
                path=rel,
                cost=entry.get("cost", "unknown"),
                role=entry.get("role", ""),
                text=target.read_text(encoding="utf-8"),
            )
        )
    return documents


def _record(cap: Capability) -> None:
    line = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "id": cap.id,
        "version": cap.version,
        "ref": cap.ref,
        "commit": cap.commit,
        "documents": [d.path for d in cap.documents],
    }
    with (cache_dir() / "audit.log").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")


def learn(name: str, *, ref: str | None = None, minimal: bool = False) -> Capability:
    """Fetch a HeepX capability and return it ready to hand to an agent.

        cap = learn("warrant")
        cap = learn("reasoning", minimal=True)   # smallest useful load
        cap = learn("warrant", ref="v1.2.0")     # pin an exact release

    Defaults to the newest release tag. Raises CapabilityError if the
    repository cannot be fetched or does not conform to the HeepX standard.
    """
    repo, resolved_ref, commit, url = _fetch(name, ref)
    meta = _parse(repo)

    if meta["id"] != name:
        # HXS-META-03 wants descriptor id and repository name to match. Warn
        # rather than fail: the clone URL is built from `name`, so the wrong
        # repository cannot be fetched, and a pre-rename tag legitimately
        # carries the old id (warrant@v1.0.0 says "epistemic-discipline").
        log.warning(
            "%s@%s declares id %r (HXS-META-03 expects %r)",
            name, resolved_ref, meta["id"], name,
        )

    cap = Capability(
        id=meta["id"],
        version=str(meta["version"]),
        summary_line=str(meta["capability"]),
        spec=str(meta.get("spec", "")),
        improves=list(meta.get("improves") or []),
        does_not_improve=list(meta.get("does_not_improve") or []),
        ref=resolved_ref,
        commit=commit,
        source=url,
        documents=_read_documents(repo, meta, minimal),
    )
    _record(cap)
    log.info("learned %s", cap.audit())
    return cap


def teach(agent, *capabilities: Capability) -> None:
    """Prepend capabilities to a live agent's system prompt.

    Deliberately additive: the agent keeps the role prompt it was built with,
    and the capability text goes above it.
    """
    if not capabilities:
        return
    block = "\n".join(cap.context() for cap in capabilities)
    agent.system_prompt = f"{block}\n{agent.system_prompt}"
