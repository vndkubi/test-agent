#!/usr/bin/env python3
"""
Agentic Development Workflow CLI

Usage:
    agentic <PBI-KEY> [options]
    agentic todo <PBI-KEY>              # Interactive TODO manager
    agentic pr review <PR>              # Analyze PR comments
    agentic pr fix <PR> [--auto]        # Fix PR comments
    
Examples:
    agentic PBI-123
    agentic SCRUM-456 --draft
    agentic pr review 42
    agentic pr fix 42 --auto
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from .jira_connector import jira_connector, PBIData
from .enhanced_context_generator import enhanced_context_generator
from .git_automation import git_automation
from .todo_manager import todo_manager
from .pr_review import pr_review_manager, PRReviewSummary
from .auto_fixer import auto_fixer

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
        context_file = enhanced_context_generator.generate(pbi, working_dir)
        print_step(4, total_steps, f"Context: {context_file.requirements.relative_to(working_dir)}", "done")
    except Exception as e:
        print_step(4, total_steps, f"Context generation failed: {e}", "error")
        return False
    
    # ============================================
    # Step 5: Manual implementation with Copilot
    # ============================================
    context_dir = context_file.requirements.parent.relative_to(working_dir)
    console.print("\n" + "─" * 50)
    console.print(Panel.fit(
        "[bold cyan]🛑 Manual Step: Implement with Copilot[/bold cyan]\n\n"
        f"1. Open [bold]{context_dir}/index.md[/bold]\n"
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
    # Check for subcommands first
    if len(sys.argv) > 1:
        if sys.argv[1] == "todo":
            # Handle todo subcommand
            todo_parser = argparse.ArgumentParser(prog="agentic todo")
            todo_parser.add_argument("pbi_key", help="Jira issue key")
            todo_parser.add_argument("-i", "--interactive", action="store_true")
            todo_parser.add_argument("--dir", "-d", type=Path, default=None)
            args = todo_parser.parse_args(sys.argv[2:])
            action = "interactive" if args.interactive else "show"
            success = run_todo(args.pbi_key, args.dir, action)
            sys.exit(0 if success else 1)
        
        elif sys.argv[1] == "pr":
            handle_pr_command()
    
    # Main workflow parser
    parser = argparse.ArgumentParser(
        description="Agentic Development Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    agentic PBI-123              # Run full workflow
    agentic SCRUM-456 --draft    # Create draft PR
    agentic todo SCRUM-123       # Show TODO list
    agentic todo SCRUM-123 -i    # Interactive TODO
    agentic pr review 42         # Analyze PR comments
    agentic pr fix 42 --auto     # Auto-fix PR comments
    
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
        version="agentic 1.2.0"
    )
    
    args = parser.parse_args()
    
    success = run_workflow(
        pbi_key=args.pbi_key,
        working_dir=args.dir,
        skip_jira=args.skip_jira,
        draft_pr=args.draft
    )
    
    sys.exit(0 if success else 1)


# ============================================
# PR Review Commands
# ============================================

def run_pr_review(pr_id: str, working_dir: Optional[Path] = None):
    """Analyze PR comments."""
    working_dir = working_dir or Path.cwd()
    pr_review_manager.working_dir = working_dir
    pr_review_manager.fetcher.working_dir = working_dir
    
    console.print(Panel.fit(
        "[bold blue]📝 PR Review Analysis[/bold blue]",
        border_style="blue"
    ))
    
    # Analyze PR
    summary = pr_review_manager.analyze_pr(pr_id)
    if not summary:
        return False
    
    # Count pending vs already fixed
    pending_auto = [c for c in summary.auto_fixable if not c.is_fixed]
    pending_simple = [c for c in summary.simple_fixes if not c.is_fixed]
    pending_complex = [c for c in summary.complex_fixes if not c.is_fixed]
    pending_discussions = [c for c in summary.discussions if not c.is_fixed]
    
    fixed_count = sum(1 for c in summary.auto_fixable + summary.simple_fixes + 
                      summary.complex_fixes + summary.discussions if c.is_fixed)
    
    # Show summary table
    table = Table(title=f"PR #{summary.pr_number}: {summary.pr_title[:50]}")
    table.add_column("Category", style="cyan")
    table.add_column("Pending", justify="right")
    table.add_column("Fixed", justify="right", style="dim")
    table.add_column("Action")
    
    table.add_row("🤖 Auto-fixable", str(len(pending_auto)), f"({len(summary.auto_fixable) - len(pending_auto)})", "agentic pr fix --auto")
    table.add_row("🔧 Simple fixes", str(len(pending_simple)), f"({len(summary.simple_fixes) - len(pending_simple)})", "Quick manual fix")
    table.add_row("🔨 Complex fixes", str(len(pending_complex)), f"({len(summary.complex_fixes) - len(pending_complex)})", "Use Copilot")
    table.add_row("💬 Discussions", str(len(pending_discussions)), f"({len(summary.discussions) - len(pending_discussions)})", "Reply needed")
    table.add_row("✅ Resolved", str(len(summary.resolved)), "", "No action")
    
    console.print(table)
    
    if fixed_count > 0:
        console.print(f"\n[dim]({fixed_count} comments already addressed with replies)[/dim]")
    
    # Generate context files
    context_file = pr_review_manager.generate_review_context(summary, working_dir)
    console.print(f"\n[green]✓[/green] Context generated: {context_file.relative_to(working_dir)}")
    
    # Show next steps
    if pending_auto:
        console.print(f"\n[yellow]→[/yellow] Run [bold]agentic pr fix {pr_id} --auto[/bold] to auto-fix {len(pending_auto)} issues")
    
    if pending_complex:
        console.print(f"[yellow]→[/yellow] Open [bold].copilot/pr-{summary.pr_number}/fixes.md[/bold] for Copilot prompts")
    
    if pending_discussions:
        console.print(f"[yellow]→[/yellow] Review [bold].copilot/pr-{summary.pr_number}/discussions.md[/bold] for replies")
    
    return True


def run_pr_fix(pr_id: str, auto: bool = False, dry_run: bool = False, working_dir: Optional[Path] = None):
    """Fix PR comments."""
    working_dir = working_dir or Path.cwd()
    pr_review_manager.working_dir = working_dir
    pr_review_manager.fetcher.working_dir = working_dir
    auto_fixer.working_dir = working_dir
    
    console.print(Panel.fit(
        "[bold blue]🔧 PR Fix Mode[/bold blue]",
        border_style="blue"
    ))
    
    # Analyze PR first
    summary = pr_review_manager.analyze_pr(pr_id)
    if not summary:
        return False
    
    # Filter out already-fixed comments
    pending_auto = [c for c in summary.auto_fixable if not c.is_fixed]
    pending_simple = [c for c in summary.simple_fixes if not c.is_fixed]
    
    # Show skipped (already fixed) comments
    skipped = [c for c in summary.auto_fixable + summary.simple_fixes if c.is_fixed]
    if skipped:
        console.print(f"\n[dim]Skipped (already fixed): {len(skipped)} comments[/dim]")
        for c in skipped:
            console.print(f"  [dim]• {c.file_path}:{c.line} - already replied[/dim]")
    
    if not pending_auto and not pending_simple:
        console.print("[green]✓[/green] All fixable comments have been addressed!")
        return True
    
    # Show what will be fixed
    console.print(f"\n[bold]Pending auto-fixable ({len(pending_auto)}):[/bold]")
    for c in pending_auto:
        console.print(f"  • {c.file_path}:{c.line} - {c.suggested_fix or c.body[:50]}")
    
    if not auto:
        if not Confirm.ask("\nApply these fixes?"):
            return False
    
    # Apply fixes (only pending ones)
    fixes = auto_fixer.apply_fixes(pending_auto, dry_run=dry_run)
    
    # Show results
    console.print(f"\n[bold]Results:[/bold]")
    for fix in fixes:
        status = "[green]✓[/green]" if fix.success else "[red]✗[/red]"
        console.print(f"  {status} {fix.file_path} - {fix.message}")
    
    successful = [f for f in fixes if f.success]
    if successful and not dry_run:
        # Commit changes
        if auto or Confirm.ask("\nCommit fixes?"):
            msg = auto_fixer.generate_fix_commit_message(fixes)
            git_automation.set_working_dir(working_dir)
            git_automation.commit_changes(pr_id, msg)
            git_automation.push_branch()
            console.print("[green]✓[/green] Fixes committed and pushed")
            
            # Reply to comments
            if auto or Confirm.ask("Reply to PR comments?"):
                commit_hash = git_automation.get_last_commit_hash()
                for fix in successful:
                    reply_body = f"Fixed in commit {commit_hash}: {fix.message}"
                    pr_review_manager.fetcher.reply_to_comment(
                        int(pr_id), 
                        fix.comment.id, 
                        reply_body
                    )
                console.print(f"[green]✓[/green] Replied to {len(successful)} comments")
    
    return True


def handle_pr_command():
    """Handle pr subcommand."""
    if len(sys.argv) < 3:
        console.print("Usage: agentic pr <review|fix> <PR>")
        sys.exit(1)
    
    action = sys.argv[2]
    
    if action == "review":
        parser = argparse.ArgumentParser(prog="agentic pr review")
        parser.add_argument("pr_id", help="PR number or branch name")
        parser.add_argument("--dir", "-d", type=Path, default=None)
        args = parser.parse_args(sys.argv[3:])
        
        success = run_pr_review(args.pr_id, args.dir)
        sys.exit(0 if success else 1)
    
    elif action == "fix":
        parser = argparse.ArgumentParser(prog="agentic pr fix")
        parser.add_argument("pr_id", help="PR number or branch name")
        parser.add_argument("--auto", action="store_true", help="Auto-apply without confirmation")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
        parser.add_argument("--dir", "-d", type=Path, default=None)
        args = parser.parse_args(sys.argv[3:])
        
        success = run_pr_fix(args.pr_id, args.auto, args.dry_run, args.dir)
        sys.exit(0 if success else 1)
    
    else:
        console.print(f"Unknown pr command: {action}")
        console.print("Available: review, fix")
        sys.exit(1)


if __name__ == "__main__":
    main()
