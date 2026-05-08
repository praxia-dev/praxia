# Contributing to Praxia

Thanks for your interest! Praxia aims to be a community-driven library of **industry recipes** — operational know-how distilled into runnable agents.

## Contributions we accept

### 1. New workflow flows (`praxia/flows/`)
Multi-agent flows tailored to a specific business process (purchasing approval / incident response / code review / …). Add as a `Flow` subclass.

### 2. New business skills (`praxia/skills/business/`)
Agents with expertise in a specific domain. Add as a `Skill` subclass — see the existing six (investment / sales / design / purchasing / patent / legal) as references.

### 3. Industry recipes (`docs/recipes/`)
Markdown writeups of `industry × scenario` pairs (e.g. "manufacturing / electronic components / issue extraction") covering prompt patterns, pipeline composition, and expected impact.

### 4. LTM backends (`praxia/memory/backends/`)
Adapters for new long-term-memory products (Pinecone / Weaviate / vector DBs / …).

### 5. Bug reports & doc improvements
Open a GitHub issue.

## Development setup

```bash
git clone https://github.com/your-org/praxia.git
cd praxia
pip install -e ".[all]"
pytest                       # run the test suite
ruff check . && mypy praxia  # static analysis
```

## Pull-request checklist

- [ ] `ruff check .` passes
- [ ] `mypy praxia` passes
- [ ] Tests added (`tests/`)
- [ ] Docs updated (`docs/` or the relevant module's docstring)
- [ ] Significant design decisions captured as ADRs (`docs/adr/`)

## Code of conduct

- Constructive discussion only — no personal attacks
- Keep contribution opportunities open to everyone
- Strip PII / confidential data from industry recipes before submission

## License

Contributions are distributed under the **Apache License 2.0**.

---

## Developer Certificate of Origin (DCO) — required

Praxia uses the **DCO** approach (same as the Linux kernel and Docker). No individual CLA signing is needed, but every commit must carry a `Signed-off-by:` line.

### What the DCO is

Adding `Signed-off-by:` means you agree to the [Developer Certificate of Origin v1.1](https://developercertificate.org/). In short:

1. The contribution is **your own work**, or you have the right to contribute it under an appropriate license.
2. You understand the contribution will be **distributed under an open-source license**.
3. You understand the contribution will be **persisted in a public record**.
4. The information you submit (name / email) will be **public**.

### How to sign off

```bash
# Per-commit
git commit -s -m "feat: my contribution"

# Rewrite an existing commit with a sign-off
git commit --amend -s

# Rewrite multiple commits at once
git rebase -i HEAD~N --signoff
```

The `-s` flag automatically appends:

```
Signed-off-by: Your Name <your@email.com>
```

Make sure `git config user.name` / `user.email` resolve to a **verifiable name + email** (anonymous or pseudonymous sign-offs are not valid).

### CI verification

CI checks every commit in a PR for `Signed-off-by:`. PRs with un-signed commits are blocked from merging.

### Why DCO instead of a CLA

| Aspect | DCO | CLA |
|---|---|---|
| Contributor friction | Just `-s` per commit | Sign a separate CLA document |
| Legal clarity | Established in industry (Linux, Docker, Node.js, Kubernetes, …) | Comparable or more detailed |
| Copyright ownership | Stays with the contributor | Typically assigned to the project, or granted under broad license |
| Future relicensing flexibility | Requires consent from all contributors (no issue while we stay on Apache 2.0) | Project owner can relicense unilaterally |
| Contributor trust | High (contributors retain rights) | Lower (rights assignment requested) |

Praxia commits to **keeping the core Apache 2.0 in perpetuity**, so DCO is sufficient. If we eventually adopt an open-core model (premium enterprise features under a separate license), the Apache 2.0 core remains untouched.

### Signed commit example

```
feat(memory): add CompositeBackend for multi-LTM fusion

CompositeBackend fans out queries across N backends in parallel and
merges results via Reciprocal Rank Fusion. One backend failing is
non-fatal.

Signed-off-by: Jane Smith <jane@example.com>
```

---

## Trademarks

The "Praxia" name and logo are trademarks of GenArch. Plugin naming conventions (`praxia-connector-<name>` etc.) and rules around fork renaming are documented in [`docs/legal/TRADEMARK.md`](docs/legal/TRADEMARK.md). Free fork / modification / redistribution of the code itself remains guaranteed by Apache 2.0.

## Privacy

If your PR involves data that may contain personal information, consult [`docs/legal/GDPR_NOTES.md`](docs/legal/GDPR_NOTES.md). Do **not** include real personal data (real emails, real customer names, etc.) in test fixtures — follow the fictitious-data conventions used in `tests/evaluation/`.
