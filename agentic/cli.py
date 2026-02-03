#!/usr/bin/env python3
"""
Agentic Development Workflow CLI

Usage:
    agentic <PBI-KEY> [options]
    
Examples:
    agentic PBI-123
    agentic SCRUM-456 --draft
    agentic PBI-789 --skip-jira
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from .jira_connector import jira_connector, PBIData
from .context_generator import context_generator
from .git_automation import git_automation

console = Console()


def print_banner():
    """Print welcome banner."""
    console.print(Panel.fit(
        "[bold blue]🚀 Agentic Development Workflow[/bold blue]\n"
        "[dim]Jira → TDD → PR → Done[/dim]",
        border_style="blue"
    ))


def print_step(step: int, total: int, message: str, status: str = ""):
    """Print workflow step."""
    status_icon = {
        "": "⏳",
        "done": "[green]✓[/green]",
        "skip": "[yellow]○[/yellow]",
        "error": "[red]✗[/red]",
        "wait": "[cyan]⏸[/cyan]"
    }.get(status, "⏳")
    
    console.print(f"{status_icon} [{step}/{total}] {message}")


def run_workflow(
    pbi_key: str,
    working_dir: Optional[Path] = None,
    skip_jira: bool = False,
    draft_pr: bool = False
):
    """Run the complete agentic development workflow."""
    working_dir = working_dir or Path.cwd()
    total_steps = 7
    
    # Update git automation working directory
    git_automation.set_working_dir(working_dir)
    
    print_banner()
    console.print(f"\n[bold]PBI:[/bold] {pbi_key}")
    console.print(f"[bold]Project:[/bold] {working_dir}\n")
    
    # Check if working_dir is a git repo
    if not git_automation.is_git_repo():
        console.print(f"[red]✗[/red] {working_dir} is not a git repository!")
        console.print("[yellow]Tip: Run this command from your project directory[/yellow]")
        return False
    
    # ============================================
    # Step 1: Fetch Jira PBI
    # ============================================
    print_step(1, total_steps, f"Fetching Jira {pbi_key}...")
    
    pbi: Optional[PBIData] = None
    if skip_jira:
        print_step(1, total_steps, "Jira fetch skipped", "skip")
        pbi = PBIData(
            key=pbi_key,
            summary="Test PBI Summary",
            description="Test description",
            acceptance_criteria=["AC 1", "AC 2", "AC 3"],
            status="To Do",
            issue_type="Story",
            priority="Medium",
            labels=[],
            assignee=None,
            reporter="test@test.com",
            url=f"https://jira.example.com/browse/{pbi_key}"
        )
    else:
        try:
            pbi = jira_connector.fetch_pbi(pbi_key)
            print_step(1, total_steps, f"Fetched: {pbi.summary[:50]}...", "done")
        except Exception as e:
            print_step(1, total_steps, f"Failed to fetch Jira: {e}", "error")
            console.print("\n[yellow]Tip: Check ~/.agentic/.env or use --skip-jira[/yellow]")
            return False
    
    # ============================================
    # Step 2: Create feature branch
    # ============================================
    print_step(2, total_steps, f"Creating branch feature/{pbi_key}...")
    
    success, branch_name = git_automation.create_feature_branch(pbi_key)
    if success:
        print_step(2, total_steps, f"Branch: {branch_name}", "done")
    else:
        print_step(2, total_steps, f"Branch creation failed: {branch_name}", "error")
        return False
    
    # ============================================
    # Step 3: Update Jira to In Progress
    # ============================================
    print_step(3, total_steps, "Updating Jira → In Progress...")
    
    if skip_jira:
        print_step(3, total_steps, "Jira update skipped", "skip")
    else:
        if jira_connector.transition_to_in_progress(pbi_key):
            print_step(3, total_steps, "Jira status updated", "done")
        else:
            print_step(3, total_steps, "Could not update Jira status", "skip")
    
    # ============================================
    # Step 4: Generate Copilot context
    # ============================================
    print_step(4, total_steps, "Generating Copilot context...")
    
    try:
        context_file = context_generator.generate(pbi, working_dir)
        print_step(4, total_steps, f"Context: {context_file.relative_to(working_dir)}", "done")
    except Exception as e:
        print_step(4, total_steps, f"Context generation failed: {e}", "error")
        return False
    
    # ============================================
    # Step 5: Manual implementation with Copilot
    # ============================================
    console.print("\n" + "─" * 50)
    console.print(Panel.fit(
        "[bold cyan]🛑 Manual Step: Implement with Copilot[/bold cyan]\n\n"
        f"1. Open [bold]{context_file.relative_to(working_dir)}[/bold]\n"
        "2. Use Copilot Chat to analyze requirements\n"
        "3. Follow TDD: Write tests first, then implement\n"
        "4. Come back here when ready to create PR",
        border_style="cyan"
    ))
    console.print("─" * 50 + "\n")
    
    print_step(5, total_steps, "Waiting for implementation...", "wait")
    
    if not Confirm.ask("\n[bold]Ready to create PR?[/bold]"):
        console.print("[yellow]Workflow paused. Run again when ready.[/yellow]")
        return False
    
    # ============================================
    # Step 6: Commit, push, and create PR
    # ============================================
    print_step(6, total_steps, "Creating PR...")
    
    if git_automation.has_uncommitted_changes():
        commit_msg = Prompt.ask(
            "Commit message",
            default=f"Implement {pbi.summary[:40]}"
        )
        success, _ = git_automation.commit_changes(pbi_key, commit_msg)
        if not success:
            print_step(6, total_steps, "Commit failed", "error")
            return False
    
    success, _ = git_automation.push_branch()
    if not success:
        print_step(6, total_steps, "Push failed", "error")
        return False
    
    success, pr_url = git_automation.create_pull_request(pbi, draft=draft_pr)
    if success:
        print_step(6, total_steps, "PR created", "done")
    else:
        print_step(6, total_steps, f"PR creation failed: {pr_url}", "error")
        return False
    
    # ============================================
    # Step 7: Update Jira to In Review
    # ============================================
    print_step(7, total_steps, "Updating Jira → In Review...")
    
    if skip_jira:
        print_step(7, total_steps, "Jira update skipped", "skip")
    else:
        if jira_connector.transition_to_in_review(pbi_key):
            print_step(7, total_steps, "Jira status updated", "done")
        else:
            print_step(7, total_steps, "Could not update Jira status", "skip")
    
    # ============================================
    # Done!
    # ============================================
    console.print("\n" + "─" * 50)
    console.print(Panel.fit(
        "[bold green]✅ Workflow Complete![/bold green]\n\n"
        f"[bold]PR:[/bold] {pr_url}\n"
        f"[bold]Jira:[/bold] {pbi.url}\n\n"
        "[dim]Next: Review PR and merge[/dim]",
        border_style="green"
    ))
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Agentic Development Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    agentic PBI-123
    agentic SCRUM-456 --draft
    agentic PBI-789 --skip-jira
    
Config: ~/.agentic/.env or .env in current directory
        """
    )
    
    parser.add_argument(
        "pbi_key",
        help="Jira issue key (e.g., PBI-123, SCRUM-456)"
    )
    
    parser.add_argument(
        "--skip-jira",
        action="store_true",
        help="Skip Jira operations (for testing)"
    )
    
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Create PR as draft"
    )
    
    parser.add_argument(
        "--dir", "-d",
        type=Path,
        default=None,
        help="Project directory (default: current directory)"
    )
    
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="agentic 1.0.0"
    )
    
    args = parser.parse_args()
    
    success = run_workflow(
        pbi_key=args.pbi_key,
        working_dir=args.dir,
        skip_jira=args.skip_jira,
        draft_pr=args.draft
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
