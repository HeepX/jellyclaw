# jellyclaw

The runtime HeepX capability repositories run on.

---

## What this is

HeepX capability repositories — `warrant`, `verify`, and everything that
follows — teach a single reusable skill. They don't run themselves.

`jellyclaw` is the multi-agent runtime that loads a capability repository,
executes it against a given model or agent, and reports the result back
in the same conformant shape `standard` expects.

Any OS. Any AI. One runtime.

---

## What this is not

- Not a product.
- Not an agent framework you build a startup on.
- Not a prompt library.

It is the thing that makes `agent.learn("warrant")` an actual command
instead of a slogan in a README.

---

## How it fits the ecosystem
capability repo (e.g. warrant)
│
▼
jellyclaw runtime
│
▼
your AI agent
(Claude Code, GPT, Antigravity, or any other)
`jellyclaw` doesn't care which model is on the other end. It cares that
the capability was loaded correctly and the result is verifiable.

---

## Usage

Load a capability. This clones the real repository, pins its newest release
tag, parses `CAPABILITY.yaml` against the `standard` schema, and reads the
files its `load_order` names:

```bash
jellyclaw learn warrant
```

```
Learned warrant 1.2.1 (EDP-1) from https://github.com/HeepX/warrant@v1.2.1 [a931731]
  — 5 document(s), 28,834 chars: spec/decision-procedure.md, spec/SPEC.md,
    spec/anti-patterns.md, examples/worked-examples.md, eval/protocol.md
  + hallucination rate on claims requiring unavailable evidence
  + abstention on unresolvable questions
  - does not improve: reasoning depth, planning, or search
```

From Python, handing it to a running agent:

```python
import jellyclaw

cap = jellyclaw.learn("warrant")     # newest release tag
cap = jellyclaw.learn("reasoning")   # RDP-1
cap.version, cap.ref, cap.commit     # ('1.2.1', 'v1.2.1', 'a931731...')

jellyclaw.teach(agent, cap)          # prepends to the agent's system prompt
```

Options:

```bash
jellyclaw learn reasoning --minimal      # only the sufficient_alone file
jellyclaw learn warrant --ref v1.2.0     # pin an exact release
jellyclaw learn warrant --show           # print the assembled context
```

Capabilities are cached in `~/.jellyclaw/capabilities` (honours
`JELLYCLAW_HOME`), and every load appends a line to `audit.log` recording the
version, ref and commit — loading is never silent.

**Tags, not branches.** `HXS-SEC-02` is explicit that capability text is
loaded into a model's context by design, which makes it a supply chain for
behaviour, so the loader pins the newest release tag rather than tracking
`main`. Pass `--ref` to pin something else.

---

## Status

Early. Built alongside `standard` and `warrant`, evolving with the same
conformance discipline — no exceptions for the runtime just because it's
the runtime.

---

## License

MIT
