# NOTICE — Third-Party Licenses

Praxia is licensed under [Apache License 2.0](LICENSE).

**Praxia copyright**: © 2026 GENARCH (sole proprietor: Genki Watanabe) and Praxia Contributors. All rights reserved.

This product includes software developed by the third parties listed below.
Each dependency retains its own license. By using Praxia, you accept the
terms of the bundled licenses for the dependencies you choose to install.

The optional `[graph]`, `[ui]`, `[qwen-local]`, and `[hindsight]` extras pull
additional dependencies — only the licenses for the ones you install apply
to your build.

For a machine-readable inventory, run:

```bash
pip install pip-licenses
pip-licenses --format=markdown > THIRD-PARTY-LICENSES.md
```

---

## Required dependencies (always installed)

| Package | License | Source | Notes |
|---|---|---|---|
| **litellm** | MIT | https://github.com/BerriAI/litellm | Multi-provider LLM abstraction |
| **mem0ai** | Apache 2.0 | https://github.com/mem0ai/mem0 | Optional LTM backend (used by `mem0` backend) |
| **chromadb** | Apache 2.0 | https://github.com/chroma-core/chroma | Vector store (transitive via Mem0 / direct use) |
| **pydantic** | MIT | https://github.com/pydantic/pydantic | Data validation |
| **typer** | MIT | https://github.com/tiangolo/typer | CLI framework |
| **rich** | MIT | https://github.com/Textualize/rich | Terminal formatting |
| **python-frontmatter** | MIT | https://github.com/eyeseast/python-frontmatter | Markdown frontmatter parsing |
| **PyYAML** | MIT | https://github.com/yaml/pyyaml | YAML config parsing |

## Optional `[ui]` extra

| Package | License | Source |
|---|---|---|
| **streamlit** | Apache 2.0 | https://github.com/streamlit/streamlit |
| **plotly** | MIT | https://github.com/plotly/plotly.py |

## Optional `[graph]` extra

| Package | License | Source | Notes |
|---|---|---|---|
| **neo4j** (Python driver) | Apache 2.0 | https://github.com/neo4j/neo4j-python-driver | Graph DB driver |
| **graphiti-core** | Apache 2.0 | https://github.com/getzep/graphiti | Temporal KG (Layer 5 backend) |

## Optional `[qwen-local]` extra

| Package | License | Source |
|---|---|---|
| **ollama** (Python client) | MIT | https://github.com/ollama/ollama-python |

## Optional `[hindsight]` extra

| Package | License | Source |
|---|---|---|
| **hindsight** | (see upstream) | https://github.com/vectorize-io/hindsight |

> Verify the upstream license at the time you install — open-source licenses can change between versions.

## Optional LTM backends pulled on demand

These are imported lazily by `praxia.memory.backends.*_backend` modules. Install only what you use.

| Package | License | Source | Used by |
|---|---|---|---|
| **langmem** | MIT | https://github.com/langchain-ai/langmem | `langmem` backend |
| **letta-client** | Apache 2.0 | https://github.com/letta-ai/letta | `letta` backend |
| **zep-python** | Apache 2.0 | https://github.com/getzep/zep-python | `zep` backend |

## Development dependencies (`[dev]` extra)

Not redistributed. Listed for transparency.

| Package | License | Source |
|---|---|---|
| **pytest** | MIT | https://github.com/pytest-dev/pytest |
| **pytest-asyncio** | Apache 2.0 | https://github.com/pytest-dev/pytest-asyncio |
| **ruff** | MIT | https://github.com/astral-sh/ruff |
| **mypy** | MIT | https://github.com/python/mypy |

---

## Inspirations & references (no code redistributed)

| Project | License | Source |
|---|---|---|
| Letta (Shared Blocks concept) | Apache 2.0 | https://github.com/letta-ai/letta |
| LinkedIn Cognitive Memory Agent | n/a (research blog) | linkedin.com/blog/engineering/ai |
| Anthropic Claude Skills format | (Anthropic spec) | https://docs.claude.com |
| Model Context Protocol | MIT | https://modelcontextprotocol.io |
| Mem0 paper | arXiv | https://arxiv.org/abs/2504.19413 |

---

## How license obligations are honored

Apache 2.0 components: NOTICE files (where present) are reproduced or referenced.

MIT components: The full MIT text is reproduced in this NOTICE for completeness:

> MIT License — Copyright (c) [respective copyright holders]
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in
> all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
> THE SOFTWARE.

For Apache 2.0 dependencies, see the upstream LICENSE files at the URLs above.

---

## Reporting license issues

If you spot a missing or incorrect attribution, please open an issue at
https://github.com/your-org/praxia/issues with the `license` label.
