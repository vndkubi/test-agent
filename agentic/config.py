"""Configuration settings for the agentic workflow."""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env from user's home directory or current directory
def _load_config():
    """Load .env from multiple possible locations."""
    # Priority: current dir > home dir > package dir
    locations = [
        Path.cwd() / ".env",
        Path.home() / ".agentic" / ".env",
        Path(__file__).parent.parent / ".env",
    ]
    
    for loc in locations:
        if loc.exists():
            load_dotenv(loc)
            return loc
    
    load_dotenv()  # Try default
    return None

_config_path = _load_config()


@dataclass
class JiraConfig:
    """Jira connection and workflow configuration."""
    server: str = os.getenv("JIRA_SERVER", "")
    email: str = os.getenv("JIRA_EMAIL", "")
    api_token: str = os.getenv("JIRA_API_TOKEN", "")
    
    # Workflow status mapping
    status_todo: str = os.getenv("JIRA_STATUS_TODO", "To Do")
    status_in_progress: str = os.getenv("JIRA_STATUS_IN_PROGRESS", "In Progress")
    status_in_review: str = os.getenv("JIRA_STATUS_IN_REVIEW", "In Review")
    status_done: str = os.getenv("JIRA_STATUS_DONE", "Done")


@dataclass
class GitConfig:
    """Git and GitHub configuration."""
    repo: str = os.getenv("GITHUB_REPO", "")
    branch_prefix: str = "feature"
    

@dataclass
class WorkflowConfig:
    """Main workflow configuration."""
    context_dir: str = ".copilot"
    context_file: str = "context.md"


# Global config instances
jira_config = JiraConfig()
git_config = GitConfig()
workflow_config = WorkflowConfig()
