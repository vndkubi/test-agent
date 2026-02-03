"""Auto-fixer for simple PR review comments."""

import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass

from rich.console import Console

from .pr_review import PRComment, CommentCategory, FixDifficulty

console = Console()


@dataclass
class AppliedFix:
    """Record of an applied fix."""
    comment: PRComment
    file_path: str
    success: bool
    message: str


class AutoFixer:
    """Applies automatic fixes for simple PR comments."""
    
    def __init__(self, working_dir: Optional[Path] = None):
        self.working_dir = working_dir or Path.cwd()
    
    def apply_fixes(self, comments: List[PRComment], dry_run: bool = True) -> List[AppliedFix]:
        """
        Apply fixes for auto-fixable comments.
        
        Args:
            comments: List of comments to fix
            dry_run: If True, only show what would be done
            
        Returns:
            List of applied fixes
        """
        results = []
        
        for comment in comments:
            if comment.difficulty != FixDifficulty.AUTO:
                continue
            
            if not comment.file_path:
                results.append(AppliedFix(
                    comment=comment,
                    file_path="",
                    success=False,
                    message="No file path specified"
                ))
                continue
            
            result = self._apply_single_fix(comment, dry_run)
            results.append(result)
        
        return results
    
    def _apply_single_fix(self, comment: PRComment, dry_run: bool) -> AppliedFix:
        """Apply a single fix."""
        file_path = self.working_dir / comment.file_path
        
        if not file_path.exists():
            return AppliedFix(
                comment=comment,
                file_path=str(comment.file_path),
                success=False,
                message=f"File not found: {comment.file_path}"
            )
        
        # Read file
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.splitlines(keepends=True)
        except Exception as e:
            return AppliedFix(
                comment=comment,
                file_path=str(comment.file_path),
                success=False,
                message=f"Cannot read file: {e}"
            )
        
        # Determine fix type and apply
        fix_applied = False
        fix_message = ""
        
        body_lower = comment.body.lower()
        
        # var → const/let fix
        if re.search(r'use\s+(const|let)\s+instead', body_lower):
            match = re.search(r'use\s+[`\']?(const|let)[`\']?\s+instead', body_lower)
            if match and comment.line:
                target_var = match.group(1)
                line_idx = comment.line - 1
                if 0 <= line_idx < len(lines):
                    old_line = lines[line_idx]
                    new_line = re.sub(r'\b(var|let|const)\b', target_var, old_line, count=1)
                    if old_line != new_line:
                        lines[line_idx] = new_line
                        fix_applied = True
                        fix_message = f"Changed to `{target_var}`"
        
        # Remove extra whitespace
        elif 'extra' in body_lower and ('space' in body_lower or 'whitespace' in body_lower):
            if comment.line:
                line_idx = comment.line - 1
                if 0 <= line_idx < len(lines):
                    old_line = lines[line_idx]
                    new_line = re.sub(r'  +', ' ', old_line)  # Multiple spaces to single
                    new_line = new_line.rstrip() + '\n' if old_line.endswith('\n') else new_line.rstrip()
                    if old_line != new_line:
                        lines[line_idx] = new_line
                        fix_applied = True
                        fix_message = "Removed extra whitespace"
        
        # Add missing semicolon
        elif 'missing' in body_lower and 'semicolon' in body_lower:
            if comment.line:
                line_idx = comment.line - 1
                if 0 <= line_idx < len(lines):
                    old_line = lines[line_idx]
                    if not old_line.rstrip().endswith((';', '{', '}', ':')):
                        new_line = old_line.rstrip() + ';\n'
                        lines[line_idx] = new_line
                        fix_applied = True
                        fix_message = "Added semicolon"
        
        # Apply GitHub suggestion block
        elif '```suggestion' in comment.body:
            suggestion_match = re.search(r'```suggestion\s*\n(.*?)\n```', comment.body, re.DOTALL)
            if suggestion_match and comment.line:
                suggestion = suggestion_match.group(1)
                line_idx = comment.line - 1
                if 0 <= line_idx < len(lines):
                    lines[line_idx] = suggestion + '\n'
                    fix_applied = True
                    fix_message = "Applied suggestion"
        
        # Typo fix
        elif 'typo' in body_lower:
            typo_match = re.search(r'[`\'\"](\w+)[`\'\"]\s*(?:→|->|to|should be)\s*[`\'\"](\w+)[`\'\"]', comment.body)
            if typo_match and comment.line:
                old_word, new_word = typo_match.groups()
                line_idx = comment.line - 1
                if 0 <= line_idx < len(lines):
                    old_line = lines[line_idx]
                    new_line = old_line.replace(old_word, new_word)
                    if old_line != new_line:
                        lines[line_idx] = new_line
                        fix_applied = True
                        fix_message = f"Fixed typo: {old_word} → {new_word}"
        
        if not fix_applied:
            return AppliedFix(
                comment=comment,
                file_path=str(comment.file_path),
                success=False,
                message="Could not determine how to apply fix"
            )
        
        # Write changes (if not dry run)
        if not dry_run:
            try:
                file_path.write_text(''.join(lines), encoding='utf-8')
            except Exception as e:
                return AppliedFix(
                    comment=comment,
                    file_path=str(comment.file_path),
                    success=False,
                    message=f"Failed to write: {e}"
                )
        
        return AppliedFix(
            comment=comment,
            file_path=str(comment.file_path),
            success=True,
            message=fix_message + (" (dry run)" if dry_run else "")
        )
    
    def generate_fix_commit_message(self, fixes: List[AppliedFix]) -> str:
        """Generate commit message for applied fixes."""
        successful = [f for f in fixes if f.success]
        
        if not successful:
            return ""
        
        if len(successful) == 1:
            return f"fix: {successful[0].message}"
        
        return f"fix: address {len(successful)} review comments"


# Singleton
auto_fixer = AutoFixer()
