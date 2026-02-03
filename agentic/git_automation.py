"""Git and GitHub PR automation using gh CLI."""

import subprocess
import re
from pathlib import Path
from typing import Optional, Tuple

from rich.console import Console

from .config import git_config
from .jira_connector import PBIData

console = Console()


class GitAutomation:
    """Handles Git operations and GitHub PR creation via gh CLI."""
    
    def __init__(self, working_dir: Optional[Path] = None):
        self.working_dir = working_dir or Path.cwd()
    
    def set_working_dir(self, path: Path):
        """Update working directory."""
        self.working_dir = path
    
    def _run_command(self, cmd: list[str], check: bool = True) -> Tuple[bool, str]:
        """Run a shell command."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                check=check
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip() or str(e)
        except FileNotFoundError:
            return False, f"Command not found: {cmd[0]}"
    
    def check_gh_cli(self) -> bool:
        """Check if gh CLI is installed and authenticated."""
        success, output = self._run_command(["gh", "auth", "status"], check=False)
        if not success:
            console.print("[red]✗[/red] GitHub CLI not authenticated. Run: gh auth login")
            return False
        return True
    
    def is_git_repo(self) -> bool:
        """Check if working directory is a git repository."""
        success, _ = self._run_command(["git", "rev-parse", "--git-dir"], check=False)
        return success
    
    def get_current_branch(self) -> str:
        """Get current git branch name."""
        success, output = self._run_command(["git", "branch", "--show-current"])
        return output if success else "unknown"
    
    def get_default_branch(self) -> str:
        """Get the default branch (main or master)."""
        success, output = self._run_command(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD", "--short"],
            check=False
        )
        if success:
            return output.replace("origin/", "")
        
        for branch in ["main", "master"]:
            success, _ = self._run_command(
                ["git", "show-ref", "--verify", f"refs/heads/{branch}"],
                check=False
            )
            if success:
                return branch
        
        return "main"
    
    def create_feature_branch(self, pbi_key: str) -> Tuple[bool, str]:
        """Create and checkout a new feature branch."""
        safe_key = re.sub(r'[^a-zA-Z0-9-]', '-', pbi_key)
        branch_name = f"{git_config.branch_prefix}/{safe_key}"
        
        self._run_command(["git", "fetch", "origin"], check=False)
        
        default_branch = self.get_default_branch()
        
        success, error = self._run_command(["git", "checkout", default_branch], check=False)
        if success:
            self._run_command(["git", "pull", "origin", default_branch], check=False)
        
        success, error = self._run_command(
            ["git", "checkout", "-b", branch_name],
            check=False
        )
        
        if not success:
            success, error = self._run_command(
                ["git", "checkout", branch_name],
                check=False
            )
            if success:
                console.print(f"[yellow]![/yellow] Branch {branch_name} already exists, switched to it")
                return True, branch_name
        
        if success:
            console.print(f"[green]✓[/green] Created branch: {branch_name}")
            return True, branch_name
        else:
            console.print(f"[red]✗[/red] Failed to create branch: {error}")
            return False, error
    
    def commit_changes(self, pbi_key: str, message: str) -> Tuple[bool, str]:
        """Stage all changes and commit."""
        success, _ = self._run_command(["git", "add", "-A"])
        if not success:
            return False, "Failed to stage changes"
        
        success, status = self._run_command(["git", "status", "--porcelain"])
        if success and not status:
            return False, "No changes to commit"
        
        full_message = f"feat({pbi_key}): {message}"
        success, output = self._run_command(
            ["git", "commit", "-m", full_message],
            check=False
        )
        
        if success:
            _, commit_hash = self._run_command(["git", "rev-parse", "--short", "HEAD"])
            console.print(f"[green]✓[/green] Committed: {commit_hash} - {full_message[:50]}...")
            return True, commit_hash
        else:
            return False, output
    
    def push_branch(self, branch_name: Optional[str] = None) -> Tuple[bool, str]:
        """Push current or specified branch to origin."""
        branch = branch_name or self.get_current_branch()
        
        success, output = self._run_command(
            ["git", "push", "-u", "origin", branch],
            check=False
        )
        
        if success or "Everything up-to-date" in output:
            console.print(f"[green]✓[/green] Pushed branch: {branch}")
            return True, output
        else:
            console.print(f"[red]✗[/red] Failed to push: {output}")
            return False, output
    
    def create_pull_request(self, pbi: PBIData, draft: bool = False) -> Tuple[bool, str]:
        """Create a GitHub Pull Request with Jira content."""
        if not self.check_gh_cli():
            return False, "gh CLI not available"
        
        title = f"[{pbi.key}] {pbi.summary}"
        body = self._build_pr_body(pbi)
        base_branch = self.get_default_branch()
        
        cmd = [
            "gh", "pr", "create",
            "--title", title,
            "--body", body,
            "--base", base_branch
        ]
        
        if draft:
            cmd.append("--draft")
        
        success, output = self._run_command(cmd, check=False)
        
        if success:
            pr_url = output.strip().split('\n')[-1]
            console.print(f"[green]✓[/green] Created PR: {pr_url}")
            return True, pr_url
        else:
            console.print(f"[red]✗[/red] Failed to create PR: {output}")
            return False, output
    
    def _build_pr_body(self, pbi: PBIData) -> str:
        """Build PR description from PBI data."""
        
        ac_checklist = ""
        if pbi.acceptance_criteria:
            ac_checklist = "\n".join(f"- [ ] {ac}" for ac in pbi.acceptance_criteria)
        else:
            ac_checklist = "- [ ] _Add acceptance criteria_"
        
        return f'''## 📋 Summary

{pbi.summary}

**Jira:** [{pbi.key}]({pbi.url})  
**Type:** {pbi.issue_type} | **Priority:** {pbi.priority}

---

## 📝 Description

{pbi.description if pbi.description else "_See Jira for details._"}

---

## ✅ Acceptance Criteria

{ac_checklist}

---

## 🧪 Testing

- [ ] Unit tests added/updated
- [ ] All tests passing
- [ ] Manual testing completed

---

_This PR was created by Agentic Workflow Tool_
'''
    
    def has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        success, output = self._run_command(["git", "status", "--porcelain"])
        return bool(output.strip()) if success else False
    
    def checkout_branch(self, branch_name: str) -> bool:
        """Checkout an existing branch."""
        # Fetch first to ensure we have latest
        self._run_command(["git", "fetch", "origin"], check=False)
        
        # Try checkout
        success, error = self._run_command(
            ["git", "checkout", branch_name],
            check=False
        )
        
        if not success:
            # Try checkout tracking remote
            success, error = self._run_command(
                ["git", "checkout", "-b", branch_name, f"origin/{branch_name}"],
                check=False
            )
        
        return success
    
    def get_last_commit_hash(self) -> str:
        """Get the short hash of the last commit."""
        success, output = self._run_command(["git", "rev-parse", "--short", "HEAD"])
        return output if success else "unknown"


git_automation = GitAutomation()
