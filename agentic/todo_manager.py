"""Interactive TODO manager for PBI tracking."""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from .config import workflow_config


@dataclass
class TodoItem:
    """A single TODO item."""
    id: int
    title: str
    status: str = "pending"  # pending, in_progress, done
    category: str = "general"  # requirement, test, implementation
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "category": self.category
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TodoItem":
        return cls(**data)


class TodoManager:
    """Manages TODO items for a PBI."""
    
    STATUS_ICONS = {
        "pending": "⬜",
        "in_progress": "🔄",
        "done": "✅"
    }
    
    CATEGORY_COLORS = {
        "requirement": "cyan",
        "test": "yellow",
        "implementation": "green",
        "general": "white"
    }
    
    def __init__(self):
        self.console = Console()
        self.context_dir = workflow_config.context_dir
    
    def get_todo_file(self, pbi_key: str, working_dir: Optional[Path] = None) -> Path:
        """Get path to TODO JSON file for a PBI."""
        working_dir = working_dir or Path.cwd()
        return working_dir / self.context_dir / pbi_key / "todo.json"
    
    def load_todos(self, pbi_key: str, working_dir: Optional[Path] = None) -> tuple:
        """Load TODOs from file. Returns (pbi_summary, todos)."""
        file_path = self.get_todo_file(pbi_key, working_dir)
        
        if not file_path.exists():
            return None, []
        
        data = json.loads(file_path.read_text(encoding='utf-8'))
        todos = [TodoItem.from_dict(t) for t in data.get("todos", [])]
        return data.get("summary", ""), todos
    
    def save_todos(self, pbi_key: str, summary: str, todos: List[TodoItem], working_dir: Optional[Path] = None):
        """Save TODOs to file."""
        file_path = self.get_todo_file(pbi_key, working_dir)
        data = {
            "pbi_key": pbi_key,
            "summary": summary,
            "todos": [t.to_dict() for t in todos]
        }
        file_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        self._update_markdown(pbi_key, summary, todos, working_dir)
    
    def _update_markdown(self, pbi_key: str, summary: str, todos: List[TodoItem], working_dir: Optional[Path] = None):
        """Update the markdown TODO file."""
        working_dir = working_dir or Path.cwd()
        md_path = working_dir / self.context_dir / pbi_key / "todo.md"
        
        def render_category(cat: str, name: str):
            items = [t for t in todos if t.category == cat]
            if not items:
                return ""
            
            lines = [f"\n## {name}"]
            for t in items:
                check = "x" if t.status == "done" else " "
                prefix = "🔄 " if t.status == "in_progress" else ""
                lines.append(f"- [{check}] {prefix}{t.title}")
            return "\n".join(lines)
        
        done_count = len([t for t in todos if t.status == "done"])
        total = len(todos)
        pct = int(done_count / total * 100) if total > 0 else 0
        
        content = f'''# ✅ TODO: {pbi_key}

> **{summary}**
{render_category("requirement", "📋 Requirements")}
{render_category("test", "🧪 Tests")}
{render_category("implementation", "🔨 Implementation")}
{render_category("general", "📝 General")}

---
**Progress:** {done_count}/{total} ({pct}%)
'''
        md_path.write_text(content, encoding='utf-8')
    
    def show(self, pbi_key: str, working_dir: Optional[Path] = None):
        """Display TODOs in a nice table."""
        summary, todos = self.load_todos(pbi_key, working_dir)
        
        if not todos:
            self.console.print(f"[yellow]No TODOs found for {pbi_key}[/yellow]")
            self.console.print(f"[dim]Run 'agentic {pbi_key}' first to generate context.[/dim]")
            return
        
        done_count = len([t for t in todos if t.status == "done"])
        pct = int(done_count / len(todos) * 100)
        
        table = Table(title=f"📋 {pbi_key}: {summary}")
        table.add_column("#", style="dim", width=4)
        table.add_column("Status", width=6)
        table.add_column("Task", min_width=40)
        table.add_column("Category", width=14)
        
        for todo in todos:
            icon = self.STATUS_ICONS.get(todo.status, "⬜")
            color = self.CATEGORY_COLORS.get(todo.category, "white")
            style = "dim" if todo.status == "done" else ""
            
            table.add_row(
                str(todo.id),
                icon,
                todo.title,
                f"[{color}]{todo.category}[/{color}]",
                style=style
            )
        
        self.console.print(table)
        
        # Progress bar
        bar_len = 20
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        self.console.print(f"\n[bold]Progress:[/bold] [{bar}] {pct}% ({done_count}/{len(todos)})")
    
    def interactive(self, pbi_key: str, working_dir: Optional[Path] = None):
        """Interactive TODO management mode."""
        summary, todos = self.load_todos(pbi_key, working_dir)
        
        if not todos:
            self.console.print(f"[yellow]No TODOs found for {pbi_key}[/yellow]")
            return
        
        self.console.print(Panel.fit(
            f"[bold]Interactive TODO Manager[/bold]\n"
            f"[dim]{pbi_key}: {summary}[/dim]",
            border_style="blue"
        ))
        
        while True:
            self.show(pbi_key, working_dir)
            self.console.print("\n[dim]Commands: (n)ext, (d)one, (u)ndo, (s)tart, (q)uit[/dim]")
            
            cmd = Prompt.ask("Command", default="q")
            
            if cmd.lower() == 'q':
                break
            elif cmd.lower() == 'n':
                # Find next pending
                pending = [t for t in todos if t.status == "pending"]
                if pending:
                    pending[0].status = "in_progress"
                    self.save_todos(pbi_key, summary, todos, working_dir)
                    self.console.print(f"[green]Started: {pending[0].title}[/green]")
                else:
                    self.console.print("[yellow]No pending tasks![/yellow]")
            elif cmd.lower() == 'd':
                # Mark in_progress as done
                in_progress = [t for t in todos if t.status == "in_progress"]
                if in_progress:
                    in_progress[0].status = "done"
                    self.save_todos(pbi_key, summary, todos, working_dir)
                    self.console.print(f"[green]✓ Done: {in_progress[0].title}[/green]")
                else:
                    # Or select one
                    task_id = Prompt.ask("Task ID to mark done")
                    try:
                        task = next(t for t in todos if t.id == int(task_id))
                        task.status = "done"
                        self.save_todos(pbi_key, summary, todos, working_dir)
                        self.console.print(f"[green]✓ Done: {task.title}[/green]")
                    except (StopIteration, ValueError):
                        self.console.print("[red]Invalid task ID[/red]")
            elif cmd.lower() == 's':
                task_id = Prompt.ask("Task ID to start")
                try:
                    task = next(t for t in todos if t.id == int(task_id))
                    # Reset others
                    for t in todos:
                        if t.status == "in_progress":
                            t.status = "pending"
                    task.status = "in_progress"
                    self.save_todos(pbi_key, summary, todos, working_dir)
                    self.console.print(f"[cyan]🔄 Started: {task.title}[/cyan]")
                except (StopIteration, ValueError):
                    self.console.print("[red]Invalid task ID[/red]")
            elif cmd.lower() == 'u':
                # Undo last done
                done = [t for t in todos if t.status == "done"]
                if done:
                    done[-1].status = "pending"
                    self.save_todos(pbi_key, summary, todos, working_dir)
                    self.console.print(f"[yellow]↩ Undone: {done[-1].title}[/yellow]")
                else:
                    self.console.print("[yellow]Nothing to undo[/yellow]")
            else:
                # Maybe it's a task ID
                try:
                    task_id = int(cmd)
                    task = next(t for t in todos if t.id == task_id)
                    self.console.print(f"\nTask {task_id}: {task.title}")
                    action = Prompt.ask("Action", choices=["done", "start", "pending"], default="done")
                    task.status = "in_progress" if action == "start" else action
                    self.save_todos(pbi_key, summary, todos, working_dir)
                except (ValueError, StopIteration):
                    self.console.print("[red]Unknown command[/red]")
    
    def update_status(self, pbi_key: str, task_id: int, status: str, working_dir: Optional[Path] = None):
        """Update a specific task status."""
        summary, todos = self.load_todos(pbi_key, working_dir)
        
        try:
            task = next(t for t in todos if t.id == task_id)
            task.status = status
            self.save_todos(pbi_key, summary, todos, working_dir)
            return True
        except StopIteration:
            return False


todo_manager = TodoManager()
