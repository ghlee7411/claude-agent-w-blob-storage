#!/usr/bin/env python3
"""
Knowledge Base CLI - File-based Knowledge Management with Claude Agent

A CLI tool for managing a file-based knowledge base using Claude as the AI backbone.
Supports two main modes:
- ingest: Add documents to the knowledge base
- analysis: Query the knowledge base
"""

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.markdown import Markdown

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from agents import IngestAgent, AnalysisAgent
from storage import FileSystemStorage
from tools.kb_tools import KnowledgeBaseTools

# Initialize Typer app and Rich console
app = typer.Typer(
    name="kb",
    help="Knowledge Base CLI - Manage file-based knowledge with Claude Agent",
    add_completion=False
)
console = Console()

# Default paths
DEFAULT_KB_PATH = "./knowledge_base"


def get_storage(kb_path: str = DEFAULT_KB_PATH) -> FileSystemStorage:
    """Get storage instance."""
    return FileSystemStorage(kb_path)


def get_kb_tools(kb_path: str = DEFAULT_KB_PATH) -> KnowledgeBaseTools:
    """Get knowledge base tools instance."""
    return KnowledgeBaseTools(get_storage(kb_path))


def run_async(coro):
    """Run async function synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# =============================================================================
# Ingest Commands
# =============================================================================

@app.command()
def ingest(
    file_path: str = typer.Argument(..., help="Path to document file to ingest"),
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", "-m", help="Claude model to use")
):
    """
    Ingest a document into the knowledge base.

    The agent will read the document, analyze its content, and integrate
    the information into the knowledge base with proper citations.

    Supported formats: .txt, .html, .md
    """
    path = Path(file_path)

    if not path.exists():
        console.print(f"[red]Error:[/red] File not found: {file_path}")
        raise typer.Exit(1)

    if path.suffix.lower() not in {".txt", ".html", ".htm", ".md", ".markdown"}:
        console.print(f"[red]Error:[/red] Unsupported file format: {path.suffix}")
        console.print("Supported formats: .txt, .html, .md")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold blue]Ingesting Document[/bold blue]\n\n"
        f"File: {file_path}\n"
        f"Knowledge Base: {kb_path}",
        title="KB Ingest"
    ))

    try:
        agent = IngestAgent(storage_path=kb_path, model=model)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing document with Claude Agent...", total=None)

            result = run_async(agent.ingest(str(path.absolute())))

            progress.update(task, completed=True)

        console.print("\n[bold green]✓ Ingestion Complete[/bold green]\n")
        console.print(Markdown(result))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def ingest_text(
    text: str = typer.Argument(..., help="Text content to ingest"),
    source: str = typer.Option("manual-input", "--source", "-s", help="Source name for citation"),
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", "-m", help="Claude model to use")
):
    """
    Ingest text content directly into the knowledge base.

    Useful for adding quick notes or content from clipboard.
    """
    console.print(Panel(
        f"[bold blue]Ingesting Text Content[/bold blue]\n\n"
        f"Source: {source}\n"
        f"Content length: {len(text)} characters",
        title="KB Ingest"
    ))

    try:
        agent = IngestAgent(storage_path=kb_path, model=model)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing content with Claude Agent...", total=None)

            result = run_async(agent.ingest_content(text, source))

            progress.update(task, completed=True)

        console.print("\n[bold green]✓ Ingestion Complete[/bold green]\n")
        console.print(Markdown(result))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# Analysis Commands
# =============================================================================

@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask the knowledge base"),
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", "-m", help="Claude model to use")
):
    """
    Ask a question to the knowledge base.

    The agent will search the knowledge base and provide an answer
    based on the stored information, with citations.
    """
    console.print(Panel(
        f"[bold blue]Querying Knowledge Base[/bold blue]\n\n"
        f"Question: {question}",
        title="KB Analysis"
    ))

    try:
        agent = AnalysisAgent(storage_path=kb_path, model=model)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Searching knowledge base...", total=None)

            result = run_async(agent.ask(question))

            progress.update(task, completed=True)

        console.print("\n[bold green]Answer:[/bold green]\n")
        console.print(Markdown(result))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def summary(
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", "-m", help="Claude model to use")
):
    """
    Get a summary of the knowledge base contents.
    """
    try:
        agent = AnalysisAgent(storage_path=kb_path, model=model)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Analyzing knowledge base...", total=None)

            result = run_async(agent.summarize_kb())

            progress.update(task, completed=True)

        console.print(Panel(Markdown(result), title="Knowledge Base Summary"))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def gaps(
    topic_area: str = typer.Argument(..., help="Topic area to analyze for gaps"),
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", "-m", help="Claude model to use")
):
    """
    Find gaps in knowledge for a specific topic area.
    """
    try:
        agent = AnalysisAgent(storage_path=kb_path, model=model)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Analyzing gaps in {topic_area}...", total=None)

            result = run_async(agent.find_gaps(topic_area))

            progress.update(task, completed=True)

        console.print(Panel(Markdown(result), title=f"Knowledge Gaps: {topic_area}"))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# Utility Commands
# =============================================================================

@app.command()
def status(
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path")
):
    """
    Show knowledge base status and statistics.
    """
    try:
        kb_tools = get_kb_tools(kb_path)
        stats = run_async(kb_tools.get_stats())

        if not stats["success"]:
            console.print(f"[red]Error:[/red] {stats.get('error', 'Unknown error')}")
            raise typer.Exit(1)

        s = stats["stats"]

        table = Table(title="Knowledge Base Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Location", kb_path)
        table.add_row("Total Topics", str(s["total_topics"]))
        table.add_row("Total Citations", str(s["total_citations"]))
        table.add_row("Total Logs", str(s["total_logs"]))
        table.add_row("Categories", ", ".join(s["categories"]) if s["categories"] else "None")

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command(name="list")
def list_topics(
    category: Optional[str] = typer.Argument(None, help="Category to filter by"),
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path")
):
    """
    List all topics in the knowledge base.
    """
    try:
        kb_tools = get_kb_tools(kb_path)
        result = run_async(kb_tools.list_topics(category or ""))

        if not result["success"]:
            console.print(f"[red]Error:[/red] {result.get('error', 'Unknown error')}")
            raise typer.Exit(1)

        if not result["topics"]:
            console.print("[yellow]No topics found in the knowledge base.[/yellow]")
            return

        table = Table(title=f"Topics{' in ' + category if category else ''}")
        table.add_column("Path", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Keywords", style="yellow")
        table.add_column("Modified", style="dim")

        for topic in result["topics"]:
            table.add_row(
                topic["path"],
                topic["title"],
                ", ".join(topic["keywords"][:3]) if topic["keywords"] else "",
                topic["last_modified"][:10] if topic["last_modified"] else ""
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path")
):
    """
    Search topics by keyword or content.
    """
    try:
        kb_tools = get_kb_tools(kb_path)
        result = run_async(kb_tools.search_topics(query))

        if not result["success"]:
            console.print(f"[red]Error:[/red] {result.get('error', 'Unknown error')}")
            raise typer.Exit(1)

        if not result["results"]:
            console.print(f"[yellow]No results found for: {query}[/yellow]")
            return

        console.print(f"\n[bold]Found {result['count']} results for '{query}':[/bold]\n")

        for item in result["results"]:
            console.print(f"[cyan]{item['path']}[/cyan] ({item['match_type']})")
            if "snippets" in item:
                for snippet in item["snippets"][:2]:
                    console.print(f"  Line {snippet['line_number']}: {snippet['content'][:80]}...")
            console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def read(
    topic_path: str = typer.Argument(..., help="Topic path to read (e.g., python/gil)"),
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path")
):
    """
    Read a specific topic from the knowledge base.
    """
    try:
        kb_tools = get_kb_tools(kb_path)
        result = run_async(kb_tools.read_topic(topic_path))

        if not result["success"]:
            console.print(f"[red]Error:[/red] {result.get('error', 'Unknown error')}")
            raise typer.Exit(1)

        # Show metadata
        if result.get("metadata"):
            meta = result["metadata"]
            console.print(Panel(
                f"Title: {meta.get('title', 'N/A')}\n"
                f"Keywords: {', '.join(meta.get('keywords', []))}\n"
                f"Version: {meta.get('version', 'N/A')}\n"
                f"Last Modified: {meta.get('last_modified', 'N/A')}",
                title=f"Topic: {topic_path}"
            ))

        # Show content
        console.print("\n[bold]Content:[/bold]\n")
        console.print(Markdown(result["content"]))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def rebuild_index(
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path")
):
    """
    Rebuild the knowledge base index from metadata files.
    """
    try:
        kb_tools = get_kb_tools(kb_path)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Rebuilding index...", total=None)

            result = run_async(kb_tools.rebuild_index())

            progress.update(task, completed=True)

        if result["success"]:
            console.print(f"[green]✓[/green] {result['message']}")
        else:
            console.print(f"[red]Error:[/red] {result.get('error', 'Unknown error')}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def migrate_index_v2(
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path")
):
    """
    Migrate index from v1.0 (monolithic) to v2.0 (sharded).

    This reduces I/O and token usage by 90-98% for large knowledge bases.
    """
    script_path = Path(__file__).parent / "scripts" / "migrate_index_v2.py"

    if not script_path.exists():
        console.print(f"[red]Error:[/red] Migration script not found: {script_path}")
        raise typer.Exit(1)

    console.print("[bold]Starting index migration to v2.0...[/bold]")
    console.print()

    # Run migration script
    result = subprocess.run(
        [sys.executable, str(script_path), "--kb-path", kb_path],
        check=False
    )

    sys.exit(result.returncode)


@app.command()
def migrate_index_v3(
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path")
):
    """
    Migrate index from v2.0 (sharded) to v3.0 (2-tier).

    This further reduces I/O by 99%+ for 1M-10M scale knowledge bases.
    - Keyword 2-tier lookup: 48MB → 70KB
    - More topic shards: 350MB → 3.5MB per shard
    """
    script_path = Path(__file__).parent / "scripts" / "migrate_index_v3.py"

    if not script_path.exists():
        console.print(f"[red]Error:[/red] Migration script not found: {script_path}")
        raise typer.Exit(1)

    console.print("[bold]Starting index migration to v3.0...[/bold]")
    console.print()

    # Run migration script
    result = subprocess.run(
        [sys.executable, str(script_path), "--kb-path", kb_path],
        check=False
    )

    sys.exit(result.returncode)


@app.command()
def init(
    kb_path: str = typer.Option(DEFAULT_KB_PATH, "--kb", "-k", help="Knowledge base path")
):
    """
    Initialize a new knowledge base.
    """
    try:
        storage = get_storage(kb_path)
        kb_tools = get_kb_tools(kb_path)

        # Create initial structure
        Path(kb_path).mkdir(parents=True, exist_ok=True)
        (Path(kb_path) / "topics").mkdir(exist_ok=True)
        (Path(kb_path) / "citations").mkdir(exist_ok=True)
        (Path(kb_path) / "logs").mkdir(exist_ok=True)
        (Path(kb_path) / "_index").mkdir(exist_ok=True)

        # Create initial index
        run_async(kb_tools.rebuild_index())

        console.print(f"[green]✓[/green] Knowledge base initialized at: {kb_path}")
        console.print("\nStructure created:")
        console.print("  topics/     - Topic files (.md) and metadata (.meta.json)")
        console.print("  citations/  - Citation records")
        console.print("  logs/       - Operation logs")
        console.print("  _index/     - Index cache")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
