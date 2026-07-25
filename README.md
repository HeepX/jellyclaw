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

## Status

Early. Built alongside `standard` and `warrant`, evolving with the same
conformance discipline — no exceptions for the runtime just because it's
the runtime.

---

## License

MIT
