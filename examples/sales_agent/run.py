"""Minimal Sales-Agent-Flow demo.

    cd examples/sales_agent && python run.py

Pre-req: an API key for any one of Anthropic / OpenAI / Gemini / DashScope is
set in the environment, OR Ollama is running locally with a Qwen model.
"""
from __future__ import annotations

from praxia import Praxia
from praxia.flows import SalesAgentFlow


def main() -> None:
    loom = Praxia(user_id="alice", default_model="auto")
    print(f"Using model: {loom.llm.model}")

    result = loom.run(
        SalesAgentFlow,
        inputs={
            "customer_name": "株式会社 Acme",
            "product": "Praxia Cloud",
            "additional_context": "製造業向け SaaS。直近の中期経営計画でDX投資を300億円計上。",
        },
    )

    print("\n=== FINAL OUTPUT ===\n")
    print(result.final_output)
    print("\n=== STEP OUTPUTS ===")
    for name, step in result.step_outputs.items():
        print(f"\n--- {name} ---")
        print(step.output[:400] + ("…" if len(step.output) > 400 else ""))
    print(f"\nTokens: in={result.total_usage['input_tokens']}, out={result.total_usage['output_tokens']}")


if __name__ == "__main__":
    main()
