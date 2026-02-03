"""Enhanced context generator with multi-file support."""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from .config import workflow_config
from .jira_connector import PBIData


@dataclass
class ContextFiles:
    """Generated context file paths."""
    requirements: Path
    tests: Path
    implementation: Path
    todo: Path
    test_skeleton: Optional[Path] = None


@dataclass 
class TodoItem:
    """Interactive todo item."""
    id: int
    title: str
    status: str = "pending"
    category: str = "general"
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "category": self.category
        }


class EnhancedContextGenerator:
    """Generates multi-file context for Copilot with interactive TODO."""
    
    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir or workflow_config.context_dir)
    
    def generate(self, pbi: PBIData, working_dir: Path) -> ContextFiles:
        """Generate all context files."""
        context_dir = working_dir / self.output_dir / pbi.key
        context_dir.mkdir(parents=True, exist_ok=True)
        
        requirements_file = self._generate_requirements(pbi, context_dir)
        tests_file = self._generate_tests(pbi, context_dir)
        implementation_file = self._generate_implementation(pbi, context_dir)
        todo_file = self._generate_todo(pbi, context_dir)
        test_skeleton = self._generate_test_skeleton(pbi, working_dir)
        self._generate_index(pbi, context_dir, test_skeleton)
        
        return ContextFiles(
            requirements=requirements_file,
            tests=tests_file,
            implementation=implementation_file,
            todo=todo_file,
            test_skeleton=test_skeleton
        )
    
    def _generate_requirements(self, pbi: PBIData, context_dir: Path) -> Path:
        file_path = context_dir / "requirements.md"
        ac_list = "\n".join(f"- [ ] {ac}" for ac in pbi.acceptance_criteria) if pbi.acceptance_criteria else "_No AC found._"
        labels = ", ".join(f"`{label}`" for label in pbi.labels) if pbi.labels else "_None_"
        
        content = f'''# 📋 Requirements: {pbi.key}

## Summary
**{pbi.summary}**

| Field | Value |
|-------|-------|
| Jira | [{pbi.key}]({pbi.url}) |
| Type | {pbi.issue_type} |
| Priority | {pbi.priority} |
| Labels | {labels} |

## Description
{pbi.description or "_No description._"}

## Acceptance Criteria
{ac_list}

## Copilot Prompt
```
@workspace Analyze #file:{pbi.key}/requirements.md and suggest implementation approach
```
'''
        file_path.write_text(content, encoding='utf-8')
        return file_path
    
    def _generate_tests(self, pbi: PBIData, context_dir: Path) -> Path:
        file_path = context_dir / "tests.md"
        test_cases = self._generate_test_cases(pbi)
        
        content = f'''# 🧪 Test Plan: {pbi.key}

## TDD Approach
```
🔴 RED    → Write failing tests
🟢 GREEN  → Write code to pass
🔵 BLUE   → Refactor
```

## Test Cases
{test_cases}

## Copilot Prompt
```
@workspace Based on #file:{pbi.key}/tests.md generate pytest tests
```
'''
        file_path.write_text(content, encoding='utf-8')
        return file_path
    
    def _generate_test_cases(self, pbi: PBIData) -> str:
        if not pbi.acceptance_criteria:
            return "| # | Test Case | Priority |\n|---|-----------|----------|\n| 1 | _Define tests_ | High |"
        
        rows = ["| # | Test Case | AC | Priority |", "|---|-----------|-------|----------|"]
        for i, ac in enumerate(pbi.acceptance_criteria, 1):
            test_name = self._ac_to_test_name(ac)
            short_ac = ac[:40] + "..." if len(ac) > 40 else ac
            rows.append(f"| {i} | `{test_name}` | {short_ac} | {'High' if i <= 3 else 'Medium'} |")
        return "\n".join(rows)
    
    def _ac_to_test_name(self, ac: str) -> str:
        clean = ''.join(c if c.isalnum() or c == ' ' else '' for c in ac.lower())
        return f"test_{'_'.join(clean.split()[:5])}"
    
    def _generate_implementation(self, pbi: PBIData, context_dir: Path) -> Path:
        file_path = context_dir / "implementation.md"
        content = f'''# 🔨 Implementation: {pbi.key}

## Checklist
- [ ] Review requirements
- [ ] Write tests (TDD)
- [ ] Implement code
- [ ] Refactor
- [ ] Documentation

## Files to Modify
| File | Action | Description |
|------|--------|-------------|
| | | |

## Copilot Prompt
```
@workspace Implement {pbi.key} based on #file:{pbi.key}/requirements.md
```
'''
        file_path.write_text(content, encoding='utf-8')
        return file_path
    
    def _generate_todo(self, pbi: PBIData, context_dir: Path) -> Path:
        file_path = context_dir / "todo.json"
        todos = []
        todo_id = 1
        
        todos.append(TodoItem(todo_id, "Review requirements", "pending", "requirement").to_dict()); todo_id += 1
        todos.append(TodoItem(todo_id, "Analyze scope", "pending", "requirement").to_dict()); todo_id += 1
        
        ac_list = pbi.acceptance_criteria or []
        for ac in ac_list[:5]:
            short = ac[:35] + "..." if len(ac) > 35 else ac
            todos.append(TodoItem(todo_id, f"Test: {short}", "pending", "test").to_dict()); todo_id += 1
        
        todos.append(TodoItem(todo_id, "Implement feature", "pending", "implementation").to_dict()); todo_id += 1
        todos.append(TodoItem(todo_id, "Handle edge cases", "pending", "implementation").to_dict()); todo_id += 1
        todos.append(TodoItem(todo_id, "Refactor", "pending", "implementation").to_dict()); todo_id += 1
        
        data = {"pbi_key": pbi.key, "summary": pbi.summary, "todos": todos}
        file_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        
        # Also generate markdown
        self._generate_todo_markdown(pbi, context_dir, todos)
        return file_path
    
    def _generate_todo_markdown(self, pbi: PBIData, context_dir: Path, todos: list):
        file_path = context_dir / "todo.md"
        
        def render(items, cat):
            filtered = [t for t in items if t["category"] == cat]
            return "\n".join(f"- [ ] {t['title']}" for t in filtered)
        
        content = f'''# ✅ TODO: {pbi.key}

> **{pbi.summary}**

## 📋 Requirements
{render(todos, "requirement")}

## 🧪 Tests
{render(todos, "test")}

## 🔨 Implementation
{render(todos, "implementation")}

---
Progress: 0/{len(todos)} (0%)
'''
        file_path.write_text(content, encoding='utf-8')
    
    def _generate_test_skeleton(self, pbi: PBIData, working_dir: Path) -> Optional[Path]:
        tests_dir = working_dir / "tests"
        tests_dir.mkdir(exist_ok=True)
        
        init_file = tests_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding='utf-8')
        
        test_file = tests_dir / f"test_{pbi.key.lower().replace('-', '_')}.py"
        
        # Skip if test file already exists (don't overwrite user's tests)
        if test_file.exists():
            return test_file
        
        test_funcs = []
        ac_list = pbi.acceptance_criteria or []
        for i, ac in enumerate(ac_list[:5], 1):
            func_name = self._ac_to_test_name(ac)
            test_funcs.append(f'''
def {func_name}():
    """AC {i}: {ac[:60]}"""
    # TODO: Implement
    pytest.skip("Not implemented")
''')
        
        placeholder = 'def test_placeholder():\n    pytest.skip("Add tests")'
        tests_code = "".join(test_funcs) if test_funcs else placeholder
        content = f'''"""Tests for {pbi.key}: {pbi.summary}"""
import pytest

{tests_code}
'''
        test_file.write_text(content, encoding='utf-8')
        return test_file
    
    def _generate_index(self, pbi: PBIData, context_dir: Path, test_skeleton: Optional[Path]):
        file_path = context_dir / "index.md"
        content = f'''# 🚀 {pbi.key}: {pbi.summary}

## Files
- [requirements.md](requirements.md)
- [tests.md](tests.md)
- [implementation.md](implementation.md)
- [todo.md](todo.md)

## Workflow
1. Read requirements.md
2. Write tests (TDD)
3. Implement
4. Track with `agentic todo {pbi.key}`

**Jira:** [{pbi.key}]({pbi.url})
'''
        file_path.write_text(content, encoding='utf-8')


enhanced_context_generator = EnhancedContextGenerator()
