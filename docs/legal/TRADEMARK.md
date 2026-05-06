# Praxia Trademark Policy

> 🇯🇵 日本語版: [TRADEMARK.ja.md](TRADEMARK.ja.md)
> Status: **policy v1.0 — application pending; this document binds use of the Praxia name regardless of registration status.**

---

## 1. The mark and its owner

**"Praxia"** (the word mark) and the Praxia visual mark (▣) are owned by
**GenArch**, the sole proprietor publishing this OSS project.

Trademark applications are pending in:
- Japan (JPO) — class 9, 42
- United States (USPTO) — class 9, 42
- European Union (EUIPO) — class 9, 42

Until registration completes, GenArch asserts unregistered (common-law)
trademark rights through continuous use of the mark since 2026.

---

## 2. Why a trademark policy on an Apache 2.0 project

The Apache License, Version 2.0, **does not grant trademark rights**.
[Section 6](https://www.apache.org/licenses/LICENSE-2.0#trademarks) of the
license is explicit:

> "This License does not grant permission to use the trade names, trademarks,
> service marks, or product names of the Licensor."

This policy fills that gap. It tells you what you can and cannot do with the
"Praxia" name even though you are free to use, modify, and redistribute
the code.

---

## 3. Permitted uses (no permission required)

You may use the "Praxia" name in the following ways without asking:

### 3.1 Nominative fair use

Referring to Praxia by name to describe what your software does or how it
relates to Praxia:

- "MyApp uses Praxia for memory cycling."
- "Compatible with Praxia 1.0+"
- "An adapter for Praxia"
- "I gave a talk about Praxia at PyCon."

### 3.2 Unmodified redistribution

If you redistribute Praxia exactly as published (binary or source) under the
Apache 2.0 license, with the NOTICE file intact, you may keep the "Praxia"
name on the package. **Do not** add new functionality that materially
diverges from upstream and continue calling that distribution "Praxia."

### 3.3 Plugins and extensions

A package that **extends** Praxia may use the name in a clearly compound,
descriptive form:

- ✅ `praxia-connector-notion`
- ✅ `praxia-skill-hr-recruiting`
- ✅ "Notion connector for Praxia"
- ❌ `praxia-pro` (suggests an official tier)
- ❌ `praxia-enterprise` (same)
- ❌ `praxia-cloud` (same)

The format `praxia-<noun>-<service>` is recommended for connectors,
backends, parsers, exporters, OAuth providers, and skills. See
[CUSTOM_CONNECTORS.md](../CUSTOM_CONNECTORS.md).

### 3.4 Books, articles, courses, conference talks

You may use the Praxia name in titles and content of educational material:

- ✅ "Building agents with Praxia: a hands-on tutorial"
- ✅ A YouTube series called "Praxia in 30 minutes"
- ✅ A Coursera course "Memory architectures with Praxia"

We appreciate (but do not require) a courtesy email to `hello@praxia.dev`
so we can amplify your work.

### 3.5 The Praxia logo (▣)

The mark `▣` may be used:
- ✅ In documentation that references Praxia
- ✅ In a "Powered by Praxia" badge on your service
- ❌ As your own product logo
- ❌ Modified (recolored, rotated, combined with other marks) without permission

---

## 4. Forbidden uses (require explicit permission)

You **may not** do the following without prior written permission from
GenArch:

### 4.1 Renaming a fork to "Praxia X"

If you fork Praxia, modify it materially, and redistribute it, you **must**
rename the fork to a name that does not include "Praxia":

- ❌ `Praxia Plus`, `Praxia Enterprise`, `Praxia 2`, `MyCorp Praxia`
- ✅ `MemoryAgent`, `WorkflowOrchestratorX`, `Acme AI` — pick a new name

You may say in the fork's documentation: "Forked from Praxia." That is
nominative fair use and is permitted.

### 4.2 SaaS / hosted service named "Praxia"

You may not run a hosted service that uses "Praxia" in its product name:

- ❌ `praxia.acme-corp.com` (where Acme Corp is not GenArch)
- ❌ "Praxia by Acme" (selling a hosted Praxia under that name)
- ❌ A Slack app called "Praxia for Slack" (where the app is not from GenArch)
- ✅ "Acme AI (built on Praxia)" — refers to Praxia, doesn't claim the name

### 4.3 Domain names

You may not register a domain that:
- Uses "praxia" as the second-level domain in a TLD where we have a presence
  (e.g., `praxia.com`, `praxia.io`, `praxia.ai` are reserved by GenArch
  intent even if they are not yet registered)
- Uses a confusingly similar variant: `praxia-ai.com`, `praxiahq.com`,
  `getpraxia.com`

If you have already registered such a domain, please contact us before
launching anything publicly under that name; we typically work out a
courtesy transfer or coexistence depending on context.

### 4.4 Merchandise

T-shirts, stickers, and swag bearing the Praxia name or logo, sold for
profit, require a written license. Free distribution at meetups (small
batches, ≤200 units) is permitted as long as the design follows our
visual guidelines.

### 4.5 Misleading affiliation

You may not:
- Claim to be "officially partnered with" / "endorsed by" / "approved by"
  Praxia or GenArch
- Use "Praxia Certified" / "Praxia Authorized" — those are reserved for
  partners with a written agreement
- Imply that GenArch is responsible for your fork's behavior

---

## 5. How to request permission

Email `trademark@praxia.dev` (or open a GitHub issue with the `trademark`
label if you prefer public discussion) with:

1. Who you are and what you want to call your project / service
2. How "Praxia" appears in the name + visual context (mockup if relevant)
3. The relationship between your work and upstream Praxia
4. Any concerns about confusion in your target market

Common requests we routinely approve:
- Translation organizations using "Praxia 中文社区" / "Praxia Japan" for
  community efforts (with disclosure that they are unofficial)
- Conference workshops named "Praxia hands-on"
- Book / publisher use cases

Common requests we routinely decline:
- Hosted services renaming to "X-Praxia"
- Forks materially diverging from upstream that keep "Praxia" in their name

We try to respond within 14 days.

---

## 6. Reporting trademark misuse

If you see "Praxia" being used in a way that appears to violate this policy:

- For clear cut-and-paste forks renaming to "Praxia X": email
  `trademark@praxia.dev`
- For domain squatters: same address
- For typosquatting ("praxxia", "praxiaa") or impersonation: same address

We act on reports in good-faith order — most cases are resolved by a
polite email asking the operator to choose a different name.

---

## 7. Coexistence and grandfathering

Some projects may have used "Praxia" or similar names before this OSS
launched in 2026:

- **Praxia** is a Latin / philosophical term meaning "habituated practice";
  small academic uses (research papers, philosophical blogs) generally do
  not conflict with software trademark scope (class 9, 42).
- If you have a pre-existing software project named "Praxia" or similar,
  please contact us. We will work out a coexistence agreement that respects
  your prior use while protecting our distinct mark.

---

## 8. Changes to this policy

This policy may evolve. The current version is committed in
[`docs/legal/TRADEMARK.md`](TRADEMARK.md) on the `main` branch; tagged
versions are anchored to repository tags. We will not retroactively
restrict uses that were permitted at the time you started them.

---

## 9. Contact

| Topic | Contact |
|---|---|
| Permission request | trademark@praxia.dev |
| Misuse report | trademark@praxia.dev |
| General questions | hello@praxia.dev |
| Public discussion | GitHub issue with `trademark` label |

---

## 10. Final note

The Apache 2.0 license guarantees that **the code is yours to fork, modify,
and ship**. The trademark policy guarantees that **the name remains a
reliable signal of origin**. Both are designed to make the OSS sustainable.

Thank you for respecting the boundary.
