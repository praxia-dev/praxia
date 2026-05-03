"""AgentLoom CLI.

Usage:
    agentloom init
    agentloom run <flow> --customer "Acme" --product "BizFlow"
    agentloom skill <skill_name> "<input>"
    agentloom list flows
    agentloom list skills
    agentloom list models
    agentloom consolidate
    agentloom ui
"""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentloom import AgentLoom, LLM
from agentloom.flows import ALL_FLOWS, LogicCheckerFlow, RAGOptimizationFlow, SalesAgentFlow
from agentloom.skills import BUSINESS_SKILLS

app = typer.Typer(help="AgentLoom — multi-agent orchestrator with cyclic memory.")
console = Console()

FLOW_REGISTRY: dict[str, type] = {
    "sales": SalesAgentFlow,
    "sales-agent": SalesAgentFlow,
    "logic": LogicCheckerFlow,
    "logic-checker": LogicCheckerFlow,
    "rag": RAGOptimizationFlow,
    "rag-optimizer": RAGOptimizationFlow,
}

SKILL_REGISTRY: dict[str, type] = {s.manifest.name: s for s in BUSINESS_SKILLS}
SKILL_REGISTRY.update({s.manifest.domain: s for s in BUSINESS_SKILLS})


@app.command()
def init(
    user_id: str = typer.Option("default-user", help="ユーザID (個人メモリの namespace)"),
    org_id: str = typer.Option("default-org", help="組織ID (共有メモリの namespace)"),
    backend: str = typer.Option("json", help="LTM バックエンド: json|mem0|langmem|letta|zep"),
    model: str = typer.Option("auto", help="LLM モデル: auto|claude|chatgpt|gemini|qwen|qwen-local"),
) -> None:
    """初期化: メモリディレクトリ・既定スキルレジストリを作成"""
    loom = AgentLoom(user_id=user_id, org_id=org_id, default_model=model)
    if loom.skill_registry:
        for skill_cls in BUSINESS_SKILLS:
            skill = skill_cls(llm=loom.llm)
            loom.skill_registry.register_org(skill)
    console.print(
        Panel.fit(
            f"✅ AgentLoom 初期化完了\n"
            f"  user_id: [bold]{user_id}[/bold]\n"
            f"  org_id:  [bold]{org_id}[/bold]\n"
            f"  backend: [bold]{backend}[/bold]\n"
            f"  model:   [bold]{loom.llm.model}[/bold]\n"
            f"  storage: [bold]{loom.config.memory_dir}[/bold]\n\n"
            f"組み込みビジネススキル {len(BUSINESS_SKILLS)} 件を組織レジストリに登録しました。",
            title="AgentLoom",
            border_style="cyan",
        )
    )


@app.command()
def run(
    flow: str = typer.Argument(..., help=f"フロー名: {', '.join(FLOW_REGISTRY)}"),
    user_id: str = typer.Option("default-user"),
    model: str = typer.Option("auto"),
    customer_name: str = typer.Option("", help="(sales) 顧客名"),
    product: str = typer.Option("", help="(sales) 製品名"),
    additional_context: str = typer.Option("", help="(sales) 追加コンテキスト"),
    document: str = typer.Option("", help="(logic) 文書本文 または ファイルパス"),
    question: str = typer.Option("", help="(rag) 質問"),
) -> None:
    """フローを実行"""
    if flow not in FLOW_REGISTRY:
        console.print(f"[red]Unknown flow: {flow}[/red]")
        console.print("利用可能: " + ", ".join(FLOW_REGISTRY))
        raise typer.Exit(1)

    flow_cls = FLOW_REGISTRY[flow]
    loom = AgentLoom(user_id=user_id, default_model=model)

    # gather inputs based on flow type
    inputs: dict = {}
    if flow_cls is SalesAgentFlow:
        if not customer_name:
            console.print("[red]--customer-name is required for sales flow[/red]")
            raise typer.Exit(1)
        inputs = {
            "customer_name": customer_name,
            "product": product,
            "additional_context": additional_context,
        }
    elif flow_cls is LogicCheckerFlow:
        body = document
        if document and Path(document).is_file():
            body = Path(document).read_text(encoding="utf-8")
        inputs = {"document": body}
    elif flow_cls is RAGOptimizationFlow:
        inputs = {"question": question, "retriever": None}

    console.print(f"▶ Running [bold]{flow_cls.name}[/bold] with model [bold]{loom.llm.model}[/bold]…")
    result = loom.run(flow_cls, inputs=inputs)
    console.print(Panel(result.final_output, title="Final Output", border_style="green"))
    console.print(
        f"[dim]usage: in={result.total_usage['input_tokens']}, "
        f"out={result.total_usage['output_tokens']}[/dim]"
    )


@app.command()
def skill(
    name: str = typer.Argument(..., help="スキル名 (例: investment, sales, design, ...)"),
    user_input: str = typer.Argument(..., help="エージェントへの入力"),
    model: str = typer.Option("auto"),
) -> None:
    """単一のビジネススキルを呼び出し"""
    if name not in SKILL_REGISTRY:
        console.print(f"[red]Unknown skill: {name}[/red]")
        console.print("利用可能: " + ", ".join(SKILL_REGISTRY))
        raise typer.Exit(1)
    skill_cls = SKILL_REGISTRY[name]
    llm = LLM(LLM.auto_detect() if model == "auto" else model)
    skill_obj = skill_cls(llm=llm)
    console.print(f"▶ Running skill [bold]{skill_obj.manifest.name}[/bold] on [bold]{llm.model}[/bold]…")
    output = skill_obj.run(user_input)
    console.print(Panel(output, title=skill_obj.manifest.name, border_style="magenta"))


@app.command(name="list")
def list_(
    target: str = typer.Argument("flows", help="flows | skills | models | backends")
) -> None:
    """利用可能なリソース一覧"""
    if target == "flows":
        table = Table(title="Available Flows")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        for cls in ALL_FLOWS:
            table.add_row(cls.name, cls.description)
        console.print(table)
    elif target == "skills":
        table = Table(title="Default Business Skills")
        table.add_column("Name", style="cyan")
        table.add_column("Domain", style="yellow")
        table.add_column("Description")
        for cls in BUSINESS_SKILLS:
            m = cls.manifest
            table.add_row(m.name, m.domain, m.description)
        console.print(table)
    elif target == "models":
        table = Table(title="Supported LLM Providers")
        table.add_column("Alias", style="cyan")
        table.add_column("Resolves to")
        from agentloom.core.llm import DEFAULT_ALIASES
        for alias, model in DEFAULT_ALIASES.items():
            table.add_row(alias, model)
        console.print(table)
        console.print(
            "[dim]Any LiteLLM-supported provider works — pass `--model <provider>/<model>`.[/dim]"
        )
    elif target == "backends":
        table = Table(title="Memory Backends")
        table.add_column("Name", style="cyan")
        table.add_column("Notes")
        table.add_row("json", "Default — zero deps, JSONL on disk")
        table.add_row("mem0", "Mem0 OSS — entity linking + hybrid search (recommended)")
        table.add_row("langmem", "LangChain LangMem SDK")
        table.add_row("letta", "Letta shared blocks")
        table.add_row("zep", "Zep / Graphiti — temporal KG (Layer 5)")
        console.print(table)
    else:
        console.print(f"[red]Unknown target: {target}[/red]")
        raise typer.Exit(1)


@app.command()
def consolidate(
    user_id: str = typer.Option("default-user"),
    threshold: float = typer.Option(0.75, help="自動昇格の閾値 (0..1)"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """個人メモリ → 組織メモリへの蒸留 (Sleep-time Consolidation)"""
    loom = AgentLoom(user_id=user_id)
    loom.config.consolidation_threshold = threshold
    report = loom.consolidate(dry_run=dry_run)
    console.print(Panel.fit(str(report), title="Consolidation Report", border_style="blue"))


@app.command()
def ui(
    port: int = typer.Option(8501),
    user_id: str = typer.Option("default-user"),
) -> None:
    """デフォルト UI (Streamlit) を起動"""
    import subprocess
    import sys

    from agentloom.ui import launcher

    ui_path = Path(launcher.__file__).parent / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(ui_path), "--server.port", str(port)]
    console.print(f"Launching UI at [bold]http://localhost:{port}[/bold] (user_id={user_id})…")
    subprocess.run(cmd, env={**__import__("os").environ, "AGENTLOOM_USER_ID": user_id}, check=False)


if __name__ == "__main__":
    app()
