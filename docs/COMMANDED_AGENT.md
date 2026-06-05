# CommandedAgent — autonomous agent with an external grounding commander

The bare [`AutonomousAgent`](../praxia/agent/autonomous.py) is a free-running
tool-use loop: it picks a tool, runs it, looks at the result, decides the
next step, and eventually emits a `final_answer`. That's the right shape
when the environment itself answers the question — coding agents whose
tests either pass or fail, DevOps agents whose commands either succeed or
exit non-zero, automation that can see a file appear on disk.

`CommandedAgent` is for the cases where the **environment does not give
you a free answer key** — private-corpus fact QA, compliance / SOP
questions, customer support over manuals, technical-knowledge transfer
across specialists. In those domains, "it ran" doesn't tell you "it's
right." You need an explicit verification step against the actual source
material before you trust the answer.

## What it adds

```
┌──────────────────────────────────────────────────────────────┐
│ CommandedAgent.run(user_input)                               │
│                                                              │
│  ┌──────────────────────────────────────────────┐            │
│  │ 1. Pre-retrieval                             │            │
│  │    Retriever(query) → list[Source]           │            │
│  │    Default: PersonalMemory + SharedMemory    │            │
│  │             + MarkdownStore                  │            │
│  └──────────────────────────────────────────────┘            │
│              │                                               │
│              ▼                                               │
│  ┌──────────────────────────────────────────────┐            │
│  │ 2. Draft                                     │            │
│  │    AutonomousAgent.run(user + sources)       │            │
│  │    → draft answer                            │            │
│  └──────────────────────────────────────────────┘            │
│              │                                               │
│              ▼                                               │
│  ┌──────────────────────────────────────────────┐            │
│  │ 3. Verify                                    │            │
│  │    Verifier.verify(draft, sources)           │            │
│  │    → Verdict(groundedness, per_claim,        │            │
│  │              decision, citations)            │            │
│  └──────────────────────────────────────────────┘            │
│              │                                               │
│   ┌──────────┼──────────┬──────────────┐                     │
│   ▼          ▼          ▼              ▼                     │
│  accept   redraft     abstain      max_rounds                │
│  (cite)   (loop ≤ N)  (refuse)     (configurable end-state)  │
└──────────────────────────────────────────────────────────────┘
```

Three guarantees the inner agent alone cannot provide:

1. **Every accepted claim is traceable to a source.** The verifier scores
   each atomic claim against the retrieved evidence; the final answer
   carries `[L1#0, L3#2, …]` citations the auditor can follow.
2. **The agent refuses instead of guessing.** When the sources don't
   support a confident answer, the commander returns an explicit
   abstention — *not* a plausible-sounding hallucination.
3. **Every iteration is recorded.** `result.rounds` contains the full
   draft + verdict for each round, and every round is also written to the
   audit log via `commander.run.start` / `commander.round` /
   `commander.run.end` actions.

## When to use it (and when not to)

| Use case | Inner agent alone | CommandedAgent |
|---|---|---|
| Coding agent: tests are the verifier | ✅ | overkill |
| DevOps agent: exit codes are the verifier | ✅ | overkill |
| Personal automation, low blast radius | ✅ | overkill |
| Maintenance / runbook QA over manuals | risky | **✅** |
| Compliance / SOP / regulatory QA | risky | **✅** |
| Customer support over product docs | risky | **✅** |
| Sales support — proposal grounding | risky | **✅** |
| Technical-knowledge transfer (private vocab) | risky | **✅** |

The rule of thumb: **if a wrong answer costs you something — a stoppage,
a regulatory finding, a missed compliance check, a customer escalation —
the verification round earns its cost.**

## Quick start

```python
from praxia.agent import AutonomousAgent, CommandedAgent
from praxia.core.llm import LLM

inner = AutonomousAgent(
    user_id="alice",
    role="operator",
    org_id="acme",
    llm=LLM("claude"),
    memory_dir=".praxia",
    max_steps=8,
)

agent = CommandedAgent(
    inner,
    max_verify_rounds=3,         # at most 3 verification rounds
    require_citations=True,      # append a [source_ids] footer to accepted answers
)

result = agent.run(
    "How do we handle Customer X's stamping-press alarm code E-204?"
)

print(result.answer)
print("Decision:", result.verdict.decision)
print("Groundedness:", result.verdict.groundedness)
print("Cited:", result.citations)
for r in result.rounds:
    print(f"  round {r.round}: {r.verdict.decision} "
          f"(g={r.verdict.groundedness:.2f}, "
          f"unsupported={len(r.verdict.unsupported_claims)})")
```

The default retriever pulls from L1 PersonalMemory, L3 SharedMemory, and
L4 MarkdownStore. Anything found gets a stable id (`L1#0`, `L3#2`, …) so
the verifier can attribute claims unambiguously, and the agent is
instructed in the prompt to use only those labelled sources.

## Pluggable verifier

`Verifier` is a `Protocol` — the default `LLMGroundingVerifier` extracts
and scores atomic claims in a single LLM call, but anyone can replace it.

```python
from praxia.agent import CommandedAgent, Verdict, Source

class EmbeddingOverlapVerifier:
    """Score draft↔source overlap via embedding cosine."""
    def __init__(self, embedder, accept_threshold=0.7):
        self.embedder = embedder
        self.accept_threshold = accept_threshold

    def verify(self, draft: str, sources: list[Source]) -> Verdict:
        # ... compute cosine similarity, build Verdict
        ...

agent = CommandedAgent(inner, verifier=EmbeddingOverlapVerifier(my_embedder))
```

Anything satisfying `verify(draft, sources) -> Verdict` works.

## Pluggable retriever

The `retriever` parameter is just a callable `(query: str) -> list[Source]`.
This is where you wire in your own retrieval — TiDB Vector, pgvector, a
hybrid BM25+ANN setup, GraphRAG, or a connector pull from SharePoint /
Box / Confluence. The commander doesn't care; it just consumes
`list[Source]`.

```python
def my_retriever(query: str) -> list[Source]:
    rows = my_vector_db.search(query, limit=10)
    return [Source(id=str(r["id"]), text=r["text"], kind="custom")
            for r in rows]

agent = CommandedAgent(inner, retriever=my_retriever)
```

## Configuration reference

| Parameter | Default | What it controls |
|---|---|---|
| `verifier` | `LLMGroundingVerifier(llm=inner.llm)` | How drafts are scored |
| `retriever` | `DefaultMemoryRetriever` (L1+L3+L4) | Pre-draft evidence collection |
| `max_verify_rounds` | `3` | Hard cap on redrafts |
| `abstain_on_max_rounds` | `True` | If budget exhausts mid-redraft, abstain rather than emit the last unsupported draft |
| `abstain_message` | `"I don't have enough grounded information…"` | What the commander says when it abstains |
| `require_citations` | `True` | Append `[source_id, …]` footer to accepted answers |
| `per_layer_limit` | `5` | When the default retriever is used, how many results per memory layer |

`LLMGroundingVerifier` thresholds are configurable separately:

| Parameter | Default | What it controls |
|---|---|---|
| `accept_threshold` | `0.75` | Aggregate groundedness at-or-above → `accept` |
| `abstain_threshold` | `0.35` | Aggregate groundedness at-or-below → `abstain` |
| `claim_pass_threshold` | `0.5` | Per-claim score at-or-above counts as supported |

## Audit trail

Every commander run produces three audit actions:

- `commander.run.start` — input length, source count, max_rounds
- `commander.round` (one per round) — round index, decision, groundedness, unsupported count
- `commander.run.end` — stopped_reason, total rounds, final groundedness, citation count

These layer on top of the inner agent's `agent.run.start` / `agent.run.end` actions, so a single user question can be replayed end-to-end from the JSONL audit log.

## Failure modes worth knowing about

- **Pre-retrieval returned nothing.** The commander aborts to `abstain`
  immediately rather than letting the inner agent invent. This is
  deliberate — better to surface "I have no sources" than to silently
  ground against thin air.
- **Verifier picked phantom source ids.** Any source id the verifier
  returns that doesn't match a real `Source.id` is dropped from
  `cited_source_ids`. Hallucinated citations are silently filtered.
- **`max_verify_rounds` exhausted.** Default policy is to abstain. Flip
  `abstain_on_max_rounds=False` to forward the last draft instead, but
  the `stopped_reason` will say `max_rounds` so callers can route those
  to a human reviewer.

## Composition with the rest of Praxia

`CommandedAgent` doesn't change anything about the inner stack. The same
SSO + RBAC + ACL + KMS + audit chain you get with `AutonomousAgent` still
applies — the commander just adds two more audit actions and forces the
inner agent to ground itself before returning. Memory, skills,
connectors, and the 7 extension points work exactly as documented in
[PLUGINS.md](PLUGINS.md).
