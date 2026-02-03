"""Interactive TODO manager for tracking PBI progress."""

import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from .config import workflow_config

console = Console()


class TodoManager:
    """Manages interactive TODO checklist for PBIs."""
    
    def __init__(self, working_dir: Optional[Path] = None):
        self.working_dir = working_dir or Path.cwd()
        self.context_dir = self.working_dir / workflow_config.context_dir
    
    def get_todo_file(self, pbi_key: str) -> Path:
        """Get path to todo.json for a PBI."""
        return self.context_dir / pbi_key / "todo.json"
    
    def load_todos(self, pbi_key: str) -> dict:
        """Load TODO data from file."""
        todo_file = self.get_todo_file(pbi_key)
        if not todo_file.exists():
            raise FileNotFoundError(f"No TODO found for {pbi_key}. Run workflow first.")
        
        return json.loads(todo_file.read_text(encoding='utf-8'))
    
    def save_todos(self, pbi_key: str, data: dict):
        """Save TODO data to file."""
        todo_file = self.get_todo_file(pbi_key)
        todo_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
        
        # Also update markdown view
        self._update_markdown(pbi_key, data)
    
    def _update_markdown(self, pbi_key: str, data: dict):
        """Update todo.md with current status."""
        md_file = self.context_dir / pbi_key / "todo.md"
        
        todos = data["todos"]
        done_count = sum(1 for t in todos if t["status"] == "done")
        total = len(todos)
        progress_pct = int(done_count / total * 100) if total > 0 else 0
        
        # Group by category
        requirements = [t for t in todos if t["category"] == "requirement"]
        tests = [t for t in todos if t["category"] == "test"]
        implementation = [t for t in todos if t["category"] == "implementation"]
        
        def render_todos(items):
            lines = []
            for t in items:
                checkbox = "x" if t["status"] == "done" else " "
                status_marker = ""
                if t["status"] == "in-progress":
                    status_marker = " 🔄"
                lines.append(f"- [{checkbox}] {t['title']}{status_marker}")
            return "\n".join(lines)
        
        content = f'''# ✅ TODO: {pbi_key}

> **{data["summary"]}**
> 
> Use `agentic todo {pbi_key}` to manage interactively

---

## 📋 Requirements
{render_todos(requirements)}

## 🧪 Tests  
{render_todos(tests)}

## 🔨 Implementation
{render_todos(implementation)}

---

## Progress

```
Total: {total} tasks
Done:  {done_count} / {total} ({progress_pct}%)

{"█" * (progress_pct // 5)}{"░" * (20 - progress_pct // 5)} {progress_pct}%
```

---
_Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}_
'''
        md_file.write_text(content, encoding='utf-8')
    
    def show(self, pbi_key: str):
        """Display TODO list in terminal."""
        data = self.load_todos(pbi_key)
        todos = data["todos"]
        
        console.print(Panel.fit(
            f"[bold]{pbi_key}[/bold]: {data['summary']}",
            border_style="blue"
        ))
        
        # Create table
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", width=3)
        table.add_column("Status", width=12)
        table.add_column("Category", width=14)
        table.add_column("Task")
        
        for todo in todos:
            status_style = {
                "pending": "[dim]⬜ pending[/dim]",
                "in-progress": "[yellow]🔄 working[/yellow]",
                "done": "[green]✅ done[/green]"
            }.get(todo["status"], todo["status"])
            
            cat_style = {
                "requirement": "[cyan]requirement[/cyan]",
                "test": "[magenta]test[/magenta]",
                "implementation": "[blue]implementation[/blue]"
            }.get(todo["category"], todo["category"])
            
            table.add_row(
                str(todo["id"]),
                status_style,
                cat_style,
                todo["title"]
            )
        
        console.print(table)
        
        # Show progress
        done_count = sum(1 for t in todos if t["status"] == "done")
        total = len(todos)
        progress_pct = int(done_count / total * 100) if total > 0 else 0
        
        console.print(f"\n[bold]Progress:[/bold] {done_count}/{total} ({progress_pct}%)")
        console.print(f"[green]{'█' * (progress_pct // 5)}[/green][dim]{'░' * (20 - progress_pct // 5)}[/dim]")
    
    def interactive(self, pbi_key: str):
        """Interactive TODO management."""
        while True:
            console.clear()
            self.show(pbi_key)
            
            console.print("\n[bold]Commands:[/bold]")
            console.print("  [cyan]s[/cyan] <id>  - Start task (in-progress)")
            console.print("  [green]d[/green] <id>  - Done task")
            console.print("  [yellow]r[/yellow] <id>  - Reset to pending")
            console.print("  [blue]a[/blue]      - Add new task")
            console.print("  [red]q[/red]      - Quit")
            
            cmd = Prompt.ask("\nCommand").strip().lower()
            
            if cmd == 'q':
                break
            
            if cmd == 'a':
                self._add_task(pbi_key)
                continue
            
            if len(cmd) >= 2:
                action = cmd[0]
                try:
                    task_id = int(cmd.split()[1])
                    
                    if action == 's':
                        self.update_status(pbi_key, task_id, "in-progress")
                    elif action == 'd':
                        self.update_status(pbi_key, task_id, "done")
                    elif action == 'r':
                        self.update_status(pbi_key, task_id, "pending")
                except (ValueError, IndexError):
                    console.print("[red]Invalid command. Use: s/d/r <id>[/red]")
                    Prompt.ask("Press Enter to continue")
    
    def update_status(self, pbi_key: str, task_id: int, status: str):
        """Update a task's status."""
        data = self.load_todos(pbi_key)
        
        for todo in data["todos"]:
            if todo["id"] == task_id:
                todo["status"] = status
                self.save_todos(pbi_key, data)
                return True
        
        return False
    
    def _add_task(self, pbi_key: str):
        """Add a new task interactively."""
        data = self.load_todos(pbi_key)
        
        title = Prompt.ask("Task title")
        if not title:
            return
        
        category = Prompt.ask(
            "Category",
            choices=["requirement", "test", "implementation"],
            default="implementation"
        )
        
        # Get next ID
        max_id = max(t["id"] for t in data["todos"]) if data["todos"] else 0
        
        data["todos"].append({
            "id": max_id + 1,
            "title": title,
            "status": "pending",
            "category": category
        })
        
        self.save_todos(pbi_key, data)
        console.print(f"[green]✓[/green] Added task #{max_id + 1}")
    
    def mark_done(self, pbi_key: str, task_id: int):
        """Quick mark task as done."""
        if self.update_status(pbi_key, task_id, "done"):
            console.print(f"[green]✓[/green] Task #{task_id} marked as done")
        else:
            console.print(f"[red]✗[/red] Task #{task_id} not found")
    
    def get_progress(self, pbi_key: str) -> tuple[int, int]:
        """Get progress (done, total)."""
        data = self.load_todos(pbi_key)
        todos = data["todos"]
        done = sum(1 for t in todos if t["status"] == "done")
        return done, len(todos)


# Singleton instance
todo_manager = TodoManager()
