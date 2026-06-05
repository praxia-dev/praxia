# Verification findings — what shapes `CommandedAgent`'s defaults

Praxia's `CommandedAgent` defaults are calibrated against an in-house
multi-hop RAG / external-verification harness (LangGraph + Azure
OpenAI `gpt-4o`, BM25+dense hybrid retrieval). Results below were
reproduced on:

- **SQuAD v2** — answerable + unanswerable questions, single-hop.
- **HotpotQA distractor** — 2-hop questions with passages attached
  so retrieval is genuinely possible.
- **JEMHopQA** — Japanese multi-hop QA (derivation-triple corpus).
- An internal manual-QA set (proprietary).

The seven principles below feed directly into the knobs exposed on
`CommandedAgent`, `LLMGroundingVerifier`, `LLMQueryDecomposer`,
`default_task_classifier`, and `PromotionEngine`.

---

## K1. Single-hop × strong-model → external verification adds nothing

On SQuAD v2 and the internal manual set, `gpt-4o` bare already gets ~100%
on the answerable side with near-zero hallucination — turning the
verifier on without tuning **hurts** through over-rejection.

> Praxia default: thresholds are calibrated so an answerable +
> well-retrieved question is accepted on round 1. `LLMQueryDecomposer`
> heuristically skips decomposition for obvious single-hop inputs so
> easy questions don't pay an LLM round trip.

---

## K2. Multi-hop wins via query decomposition — `+12pt` on HotpotQA

Critic alone (`C4`) actually **lost** 3pt on HotpotQA 2-hop because of
over-rejection. The decisive lever was splitting the question into
sub-questions and retrieving per hop:

| Condition | HotpotQA 20q | HotpotQA 40q |
|---|---|---|
| C0 (bare) | 80% | 70% |
| H (Hermes — self-eval loops, no critic) | 80% | 72% |
| C4 (critic only) | 75% | 72% |
| **C4M (critic + decomposition)** | **90%** | **82%** |

JEMHopQA 30q shows `+3pt` only (`C4M=93% vs C0=90%`). Why: gpt-4o
already knows most Japanese Wikipedia facts, and the derivation
corpus is easy to retrieve from (Recall@k=100%). The effect is real
but proportional to how much `bare` fails — strong model × known
facts × easy retrieval = small uplift.

> Praxia: ship `praxia.agent.decomposer.LLMQueryDecomposer` and wire
> it into `DefaultMemoryRetriever`. Single-hop inputs short-circuit
> on a regex-free heuristic.

---

## K3. External grounding gate suppresses unanswerable-question hallucination 3-4×

SQuAD v2's 12 unanswerable questions:

| Condition | Correct refusals |
|---|---|
| C0 / H | 1/12 (8%) |
| C4 | 3-4/12 (25-33%) |

Answerable accuracy stayed at 100% with 0% over-rejection. But even
the strict configuration still answered 8/12 — **a raw LLM
grounding self-check is insufficient against adversarially-plausible
unanswerables.** Production deployments should pair the default
verifier with a dedicated grounding detector (Vectara HHEM, Patronus
Lynx, AWS Bedrock contextual grounding, an NLI model, etc.).

> Praxia: `Verifier` is a protocol — swap in HHEM/Lynx/NLI when the
> deployment risk warrants it.

---

## K4. Self-evaluation alone cannot decide when to stop

`Hermes`-style loops (LLM self-judges its own draft, no external
critic, no stopping rule) burned to the safety cap (8 iterations / 9
calls) on hard / unanswerable questions while landing at `bare`-equal
quality.

LLMs cannot reliably grade themselves (OpenAI 2025 *"Why Language
Models Hallucinate"*, DeepMind ICLR 2024 *"LLMs Cannot Self-Correct
Reasoning Yet"*, self-preference bias arXiv:2410.21819).

> Praxia:
> - `CommandedAgent.min_groundedness_improvement` (default 0.05) —
>   abort to `abstain` when a redraft fails to lift `Verdict.groundedness`
>   by at least the threshold over the previous round.
>   `stopped_reason="no_improvement"` identifies that path.
> - `PromotionEngine` defaults reweighted to
>   `0.5·freq + 0.4·outcome + 0.1·self_eval`. Even self_eval=1.0 with
>   no outcome signal can no longer carry an auto-promote decision.

---

## K5. Grounding threshold is a calibration lever, not a tuning constant

Strict thresholds buy you fewer hallucinations and more over-rejection;
lenient thresholds buy the opposite. There is no single setting that
wins everywhere — pick the operating point by use-case risk.

In our internal manual QA we calibrated `C4` over-rejection from
**19% → 0%** while keeping the unanswerable-side gain on SQuAD.

> Praxia exposes `LLMGroundingVerifier.accept_threshold` /
> `abstain_threshold` / `claim_pass_threshold` so each deployment can
> set its own operating point.

---

## K6. "Does the environment self-verify the answer?" decides the strategy

| Task class | Verification | Praxia path |
|---|---|---|
| Code / shell / tool calls — tests/exit codes are the answer key | environment | `AutonomousAgent` (bare); `CommandedAgent` routes here when `task_kind == "action"` |
| Private-knowledge QA / SOP / compliance — no automatic answer key | external verifier + grounding gate | `CommandedAgent` knowledge path |

> Praxia: `default_task_classifier` recognises imperative coding /
> tool / git / npm / pip vocabulary (EN + JA) and bypasses the
> verifier. Custom classifiers via the `task_classifier=` kwarg.

---

## K7. Three things scale doesn't fix

1. **Private knowledge** isn't in the model — it's a retrieval problem,
   not an IQ problem.
2. **Hallucination is structural** — OpenAI 2025; o3 / o4-mini hallucination
   rates went **up** (16% → 33% → 48%), not down.
3. **Audit requires provenance** — "smart guesses" don't satisfy
   compliance review; cited sources do. This is an *architecture*
   requirement, not a model-quality threshold.

> Praxia: the verifier + decomposer + abstain + task router is a thin,
> model-independent safety layer. Stronger base models lower how often
> it has to abstain, but never replace it.

---

## Measuring it for yourself

Track these on your own corpus before deciding whether to flip a knob:

- **answerable accuracy** (human-graded — LLM judges have bias)
- **hallucination rate** (wrong but not refused)
- **over-rejection rate** (refused but answerable)
- **mis-retrieval rescue rate** (bare wrong → wrapped right)
- **iteration count avg / max** — runaway detector
- **LLM calls per question / latency** — verification cost

See `docs/EVALUATION.md` for the harness recipe Praxia ships with.
