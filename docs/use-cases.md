# Praxia Use Cases — Industry & Workflow Catalog

> 🌐 **日本語版はこちら**: [use-cases.ja.md](use-cases.ja.md)
>
> **What this document is**: a catalog of concrete "use case × Before/After impact" examples for evangelism and sales conversations. Figures are ranges based on industry benchmarks and early PoC assumptions; actual numbers should be re-validated per deployment.

---

## 1. Investment (`InvestmentSkill`)

### 1-A. Seed-stage investment decisions

**Scenario**: a VC junior associate reads 5–10 pitch decks per week and prepares one-page summaries for the investment committee.

| Dimension | Before | After (Praxia) | Effect |
|---|---|---|---|
| Time per deal | 4–6 hours (read pitch + competitive scan + financial model) | **45–60 min** | **~80% reduction** |
| Competitive scan breadth | Top 3–5 players | Top 5 + adjacent 10–15 | **3× breadth** |
| Bull/bear balance | Skews per associate | Always balanced + falsifiability checks | **Standardized judgment** |
| Deals processed per week | 5–10 | **20–30** | **3× deal flow** |

**Personal → org memory cycle**:
- A senior GP's hard-won "SaaS Burn Multiple evaluation logic" accumulates in personal memory over years.
- When 3 different associates independently apply the same lens, the Sleep-time Consolidator detects the pattern.
- The rubric is auto-promoted to org memory — every new associate inherits the senior's instincts on day one.

### 1-B. Quarterly portfolio rebalancing (public equities)

**Scenario**: a family-office IFA rebalances a 30-stock portfolio every quarter.

| Dimension | Before | After |
|---|---|---|
| Time per stock | 30–60 min | **5–10 min** |
| 30-stock total | 15–30 hours (3–4 business days) | **2.5–5 hours (half day)** |
| FX & macro factors weighted | 1–2 dominant factors | 5–7 factors evaluated consistently |
| Quality of client-facing report | Varies by analyst | Same baseline + per-client tailoring |

**Pitch angles**:
- "Rebalance frequency moves from quarterly to monthly" → active-management differentiator.
- "Compliance language auto-appended" → reduces advisory-license risk.

### 1-C. M&A due diligence — financial quick-screening

**Scenario**: a corporate development team narrows a long list of 20 M&A targets down to 5 for further analysis.

| Dimension | Before | After |
|---|---|---|
| Initial analysis of 20 targets | 2 weeks (3 fiscal years × 20 companies) | **2–3 business days** |
| Risk of missing red flags | Depends on analyst experience | 30 anomaly-detection rules applied uniformly |
| Investment-committee deck | Next Monday at earliest | **Same day** |

---

## 2. Sales (`SalesSkill`, `SalesAgentFlow`)

### 2-A. New-account pre-meeting research + meeting storyboard

**Scenario**: a B2B SaaS account executive prepares for the first meeting with a major new prospect.

| Dimension | Before | After |
|---|---|---|
| Research time | 4–8 hours (IR filings + press + industry reports) | **30–60 min** |
| Meeting storyboard | Another 2–3 hours separately | **Generated in the same flow** |
| Hypothesis quality | 1–2 primary hypotheses | Top 3 + supporting evidence + counter-evidence |
| FAQ prep | ~5 likely questions, verbal review | **5 questions in a table (question / recommended answer / public source)** |

**Typical Before failure**:
> "Skimmed IR filings, walked in, and the CFO opened with 'will your product cover that 30B yen CapEx we announced three months ago?' I froze."

**After**:
> Praxia merges IR with the last 6 months of press releases, extracts "of the 30B yen CapEx, 12B yen is electronics-related," and surfaces it as FAQ #1. The AE leads with it.

**Estimated impact (PoC modeling)**:
- Proposal-acceptance rate: **+15–20pt**
- Prep time per meeting: **6 hours → 1 hour**
- Meetings per AE per week: **3 → 6–8**

### 2-B. RFP response drafting

**Scenario**: a systems integrator drafts a 50–100 page response to a government or enterprise RFP.

| Dimension | Before | After |
|---|---|---|
| Draft time | 2 weeks (2 AEs + 3 SEs) | **3–5 business days** |
| Reuse rate from prior bids | 30–50% (relies on memory) | **70–85%** (auto-quoted from personal memory) |
| Missed items | 5–10 (requiring clarification rounds) | **1–2** |
| Win rate | Baseline | **+5–10pt** (driven by quality) |

**Personal → org memory cycle**:
- A senior SE accumulates "RFP-response patterns for the financial-services vertical" over a decade.
- When 3+ different SEs reuse the same phrasing, it's promoted to the shared block.
- A pending retiree's expertise survives as organizational standard (the knowledge-handover scenario).

### 2-C. Inside-sales lead prioritization

**Scenario**: an inside-sales team at a SaaS startup processes 50–100 inbound inquiries per day.

| Dimension | Before | After |
|---|---|---|
| Lead-triage time | 5 min per lead (SDR judgment) | **30 sec (AI first-pass + SDR confirm)** |
| Hot-lead miss rate | 10–15% | **3–5%** |
| Daily throughput | 50–80 leads | **150–200** |
| Meeting-booking rate | Baseline | **+8–12pt** |

---

## 3. Design / Architecture (`DesignSkill`)

### 3-A. Early review of requirements documents

**Scenario**: a senior architect at a systems integrator reviews 3–5 requirements documents per week written by junior PMs.

| Dimension | Before | After |
|---|---|---|
| Review time per doc | 2–4 hours | **20–40 min** |
| Senior's reviewing load | 12–20 hrs/week | **3–4 hrs/week (focused on substantive issues)** |
| NFR coverage | Top 5–7 dimensions | **All 6 DRAGON axes systematically** |
| PM ramp time | 12–18 months | **6–9 months** |

**Typical Before failure**:
> "Monitoring, incident response, and operational handover were missed in the requirements phase. Pre-release, this created 200 hours of unplanned engineering work."

**After**:
> Praxia's DesignSkill flags "operational design coverage missing in NFR section" during requirements review — caught before design phase begins.

### 3-B. Architecture-selection decisions

**Scenario**: a new project debates Monolith vs. Microservices vs. Modular Monolith.

| Dimension | Before | After |
|---|---|---|
| Comparison deck | 3–5 business days | **Half a day** |
| Evaluation dimensions | 5–10 primary | **15–20 (Conway / NFR / ops load / hiring viability)** |
| Comparison to prior projects | Relies on memory | **Auto-surfaces analogous past projects from org memory** |

**Personal → org memory cycle**:
- "In the 2025 A-corp project we leaned hard into Microservices; operational load collapsed" — that painful lesson lands in personal memory.
- A year later a different team is debating a similar choice. Praxia surfaces the prior case. The same mistake is avoided.
- **"The organization actually learns from failure"** — this is the mechanism that makes it work.

### 3-C. Non-functional assessment of legacy systems

**Scenario**: a 20-year-old core system needs a non-functional inventory to inform a refactoring decision.

| Dimension | Before | After |
|---|---|---|
| Assessment duration | 3–6 months (2 dedicated FTE) | **3–4 weeks** |
| Coverage | 30% sampling | **All modules, comprehensive** |
| ROI estimate accuracy | ±50% | **±15%** |

---

## 4. Procurement (`PurchasingSkill`)

### 4-A. Initial evaluation of new supplier candidates

**Scenario**: a manufacturer's procurement team narrows 30 candidate raw-materials suppliers down to 5.

| Dimension | Before | After |
|---|---|---|
| 30-supplier initial eval | 3–4 weeks (3 procurement FTE) | **3–5 business days** |
| QCD+S coverage | Q and C lead, S is ad hoc | **All QCDS + ESG + geopolitics + carbon** |
| Early loss-risk detection | Surfaces after contract signed | **Caught at initial evaluation** |

**Typical Before failure**:
> "Selected on price; later it emerged the supplier was on a child-labor watchlist. Western customers triggered audits. We exited single-source with 200M yen of switching cost."

**After**:
> PurchasingSkill weights ESG risk on par with QCD — flagged at initial screening, excluded before contract.

### 4-B. RFQ response TCO comparison

**Scenario**: an RFQ for a 500M yen capital investment goes to 5–8 vendors.

| Dimension | Before | After |
|---|---|---|
| TCO modeling | 1–2 weeks | **2–3 business days** |
| Hidden costs included | Direct cost + logistics | **Direct + logistics + duties + carrying + defect rate + FX** |
| Vendor lock-in evaluation | Analyst gut feel | **Quantified risk score** |
| Executive-ready deck | Another week | **Generated in the same pass** |

**Pitch angle**:
- "TCO view reveals real cost 30% higher than headline quotes" → ammunition for executive conversations.

### 4-C. BCP-driven supply-chain inventory

**Scenario**: post-pandemic + Ukraine + Taiwan-strait risks, a full inventory of 500 suppliers across the firm.

| Dimension | Before | After |
|---|---|---|
| 500-supplier evaluation | 6 months (5 dedicated FTE) | **6–8 weeks** |
| Single-source detection rate | 70–80% | **95%+** |
| Risk-matrix granularity | Country level | **Prefecture / city level + supplier-specific** |
| Time to executive report | 6–12 months | **2 months** |

---

## 5. Intellectual Property (`PatentSkill`)

### 5-A. Prior-art search + non-obviousness analysis

**Scenario**: an R&D group at a manufacturer evaluates 10–20 inventions per month for "patent or trade secret?"

| Dimension | Before | After |
|---|---|---|
| Search time per invention | 1–2 business days (attorney + researcher) | **2–4 hours** |
| Search-query design | Depends on attorney experience | **Synonym expansion + IPC / FI / F-term coverage, systematic** |
| Non-obviousness reasoning | "In my experience…" | **Element-by-element comparison table + secondary considerations / commercial success** |
| Attorney fees | 300–500K yen per invention | **100–150K yen (first-pass insourced)** |

**Personal → org memory cycle**:
- An IP veteran's "semiconductor-domain search templates" accumulate in personal memory.
- Researchers in unrelated fields access them via Praxia — cross-domain prior art surfaces.
- **"IP knowledge compounds across the organization"** → filing strategy gets sharper.

### 5-B. First-draft claim writing

**Scenario**: a startup wants to keep attorney costs low without sacrificing claim quality.

| Dimension | Before | After |
|---|---|---|
| Initial draft turnaround | Hand to attorney → 2 weeks | **Praxia first draft → attorney review: 3 business days** |
| Attorney fees | 500–800K yen | **150–250K yen (review only)** |
| Strategic claim structuring | Outsourced | **Independent-claim breadth / dependent-claim narrowing pre-analyzed** |

### 5-C. Competitive patent landscape mapping

**Scenario**: pre-launch patent-infringement risk assessment for a new product.

| Dimension | Before | After |
|---|---|---|
| Analysis of 50–100 competitor patents | 1 month (2 IP FTE) | **1 week** |
| Infringement-risk quantification | 3-level severity (subjective) | **Element-level mapping matrix** |
| Design-around proposals | Another month | **Generated in the same pass (3 alternative claim sets)** |

---

## 6. Legal (`LegalSkill`)

### 6-A. Contract review (NDA / MSA / SaaS terms)

**Scenario**: a mid-market legal team handles 50–100 contract reviews per month with 2–3 lawyers.

| Dimension | Before | After |
|---|---|---|
| Review time per contract | 60–90 min | **10–15 min (first pass)** |
| Monthly throughput | 50–80 contracts (capacity ceiling) | **200–300** |
| Critical-risk miss rate | 5–10% | **1–2%** |
| Lawyer overtime | 60–80 hrs/month | **20–30 hrs/month** |

**Typical Before failure**:
> "Damages-cap clause was left at 'unlimited.' Surfaced later as a 500M yen exposure when something went wrong."

**After**:
> LegalSkill flags it in the RACE framework's R (Risk) column with 🔴 Critical — must be negotiated before signature.

### 6-B. M&A legal due diligence

**Scenario**: a mid-market legal team reviews 200–500 contracts across 3 acquisition targets.

| Dimension | Before | After |
|---|---|---|
| Full contract review | 4–8 weeks (incl. outside counsel, 15–30M yen) | **2–3 weeks (outside counsel 6–12M yen)** |
| Change-of-control detection | 80–90% | **99%** |
| Contingent-liability discovery | Depends on reviewer | **Systematic enumeration across all contracts** |

**Pitch angle**:
- "Outside-counsel costs cut ~50%" → ~10M yen savings per deal.

### 6-C. Cross-border governing-law and jurisdiction review

**Scenario**: negotiating governing law, arbitration venue, and jurisdiction clauses with overseas counterparties.

| Dimension | Before | After |
|---|---|---|
| Country-by-country risk evaluation | Major jurisdictions only (US / China / EU) | **20+ jurisdictions covered (case-law trends + venue characteristics)** |
| Negotiation strategy | Engage outside counsel per deal | **Org-memory-backed compromise ranges per scenario** |
| Time to signature | 3–6 months | **6–10 weeks** |

---

## 7. Cross-cutting: the personal → organizational memory cycle

Praxia's **true differentiator** isn't the per-task speedup — it's that **organizational knowledge grows as a side effect of individuals using it normally**. Long-term effects compound:

| KPI | Before | After (Year 1) | After (Year 3) |
|---|---|---|---|
| New-hire ramp time | 6–12 months | 4–6 months | **2–3 months** |
| Knowledge loss when seniors leave | Several incidents/year | Halved | **Zero** |
| Within-team output variance | 2–3× spread between people | 50% narrowing | **Within 20%** |
| Cross-team best-practice flow | Essentially none | 5–10 / month | **30+ / month** |
| AI utilization (top-individual vs. org average) | Average is 30–50% of top | 60–70% | **80%+** |

### Concrete "knowledge-fermentation" scenarios

**Scenario A: sales best-practice diffusion**
1. **Month 6** — one senior AE refines a "manufacturing-vertical pain-discovery prompt v1," gaining +20pt win rate.
2. **Month 12** — 5 other AEs in the same team independently arrive at similar prompts.
3. **Month 13** — Sleep-time Consolidator detects the convergence → auto-promotes to shared organizational prompt.
4. **Month 18** — new hires start their first day with the same toolkit.

**Scenario B: cross-team pollination**
1. The IP team's "patent-search-query templates" get promoted to org memory.
2. R&D researchers access them via Praxia.
3. Non-domain expertise reaches the right humans → filing strategy sharpens, duplicate research avoided.
4. **"Siloed knowledge flows across the organization"** — a state previously hard to engineer.

**Scenario C: knowledge handover at retirement**
1. A 30-year procurement veteran is 3 months from retirement.
2. They use Praxia intensively for those 3 months — tacit knowledge accumulates in personal memory.
3. They opt into "donate to org memory" mode — knowledge is anonymized, abstracted, and promoted.
4. The successor inherits 30 years of experience on day one.
5. **Generational knowledge transfer — historically impossible — becomes routine.**

---

## 8. Pitch & talk-track templates

Short templates for evangelism conversations.

### 30-second pitch
> "Praxia is open-source software that turns the senior expert's tacit knowledge into organizational knowledge using AI. Across 6 workflow domains — sales, procurement, legal, IP, design, investment — agents cut routine work by 50–80%, and as people just use them normally, the prompts that work get auto-promoted as best practices for the whole team. **Apache 2.0; works with Claude, ChatGPT, Gemini, or Qwen.**"

### Vertical-specific one-liners
| Vertical | Key phrase |
|---|---|
| Investment / finance | "Junior associates operate with senior-level instincts on day one." |
| Sales / SaaS | "Put the senior AE's playbook in the new hire's hand." |
| Systems integration | "Senior architects' review time cut 75% while quality goes up, not down." |
| Manufacturing / procurement | "Supply-chain risk caught early — 10M yen losses prevented per incident." |
| IP / R&D | "Attorney fees cut 50–70% while filing-strategy precision improves." |
| Legal | "M&A outside-counsel costs cut in half." |

---

## 9. Adoption checklist

Decision criteria for organizations considering Praxia.

- [ ] **Target workflow**: routine knowledge work (research / review / comparison / analysis) consumes 10+ hours/week
- [ ] **Key-person risk**: concern about knowledge loss when seniors leave
- [ ] **Quality variance**: 2× or more output-quality spread across the team
- [ ] **LLM access**: at least one of Claude / ChatGPT / Gemini / Qwen available
- [ ] **Data residency**: can decide where personal / org memory lives (on-prem / cloud / hybrid)
- [ ] **PoC capacity**: can dedicate 3–10 pilot users for 2–3 months

3 or more ✅ — Praxia is likely a strong fit.

---

## 10. Next steps

1. **Try it in 5 minutes**: `pip install "praxia[ui]" && praxia ui`
2. **Pilot on one workflow**: pick the single most time-consuming task in your team and try it
3. **Measure at 3 months**: time saved, quality lift, and number of items promoted to org memory
4. **Decide on org-wide rollout**: use pilot data to choose org-wide vs. team-scoped deployment

[GitHub](https://github.com/praxia-dev/praxia) | [Quickstart](quickstart.md) | [Architecture](architecture.md)
