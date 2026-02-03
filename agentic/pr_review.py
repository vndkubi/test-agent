"""PR Review automation - fetch, analyze, and respond to PR comments."""

import subprocess
import json
import re
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console

console = Console()


class CommentCategory(Enum):
    """Categories for PR comments."""
    CODE_FIX = "code_fix"           # Direct code change needed
    LOGIC_ISSUE = "logic_issue"     # Logic/design problem
    QUESTION = "question"           # Reviewer asking question
    SUGGESTION = "suggestion"       # Optional improvement
    NITPICK = "nitpick"            # Minor style/formatting
    APPROVAL = "approval"           # LGTM, approved
    RESOLVED = "resolved"           # Already resolved
    UNKNOWN = "unknown"


class FixDifficulty(Enum):
    """Difficulty level for fixes."""
    AUTO = "auto"           # Can auto-fix
    SIMPLE = "simple"       # Easy manual fix
    COMPLEX = "complex"     # Needs analysis
    DISCUSSION = "discussion"  # Not a fix, needs reply


@dataclass
class PRComment:
    """Parsed PR review comment."""
    id: int
    author: str
    body: str
    file_path: Optional[str]
    line: Optional[int]
    diff_hunk: Optional[str]
    created_at: str
    state: str  # PENDING, SUBMITTED, etc.
    
    # Analysis results
    category: CommentCategory = CommentCategory.UNKNOWN
    difficulty: FixDifficulty = FixDifficulty.COMPLEX
    suggested_fix: Optional[str] = None
    draft_reply: Optional[str] = None
    
    # Reply tracking
    replies: list = field(default_factory=list)  # List of reply dicts with body and created_at
    is_fixed: bool = False  # True if latest reply indicates fixed
    needs_rework: bool = False  # True if reviewer rejected or requested changes
    last_reply_summary: Optional[str] = None  # Summary of latest reply status
    
    def to_dict(self):
        return {
            "id": self.id,
            "author": self.author,
            "body": self.body,
            "file_path": self.file_path,
            "line": self.line,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "suggested_fix": self.suggested_fix,
            "draft_reply": self.draft_reply,
            "is_fixed": self.is_fixed,
            "needs_rework": self.needs_rework
        }


@dataclass
class PRReviewSummary:
    """Summary of PR review analysis."""
    pr_number: int
    pr_title: str
    pr_url: str
    total_comments: int
    auto_fixable: list[PRComment] = field(default_factory=list)
    simple_fixes: list[PRComment] = field(default_factory=list)
    complex_fixes: list[PRComment] = field(default_factory=list)
    discussions: list[PRComment] = field(default_factory=list)
    resolved: list[PRComment] = field(default_factory=list)


class PRReviewFetcher:
    """Fetches PR review comments via gh CLI."""
    
    def __init__(self, working_dir: Optional[Path] = None):
        self.working_dir = working_dir or Path.cwd()
    
    def _run_gh(self, args: list[str]) -> Tuple[bool, str]:
        """Run gh CLI command.
        
        Security note: subprocess.run with a list argument is safe from command injection
        because arguments are passed directly to the executable without shell interpretation.
        The 'args' parameter comes from internal code, not user input.
        """
        try:
            # nosec B603 - args is a controlled list, not user input
            result = subprocess.run(
                ["gh"] + args,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )
            return True, result.stdout.strip() if result.stdout else ""
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip() if e.stderr else str(e)
        except FileNotFoundError:
            return False, "gh CLI not found"
    
    def get_pr_for_branch(self, branch: str) -> Optional[dict]:
        """Get PR info for a branch."""
        success, output = self._run_gh([
            "pr", "view", branch,
            "--json", "number,title,url,state,headRefName"
        ])
        
        if success:
            return json.loads(output)
        return None
    
    def get_pr_by_number(self, pr_number: int) -> Optional[dict]:
        """Get PR info by number."""
        success, output = self._run_gh([
            "pr", "view", str(pr_number),
            "--json", "number,title,url,state,headRefName"
        ])
        
        if success:
            return json.loads(output)
        return None
    
    def fetch_review_comments(self, pr_number: int) -> list[PRComment]:
        """Fetch all review comments for a PR, including reply status."""
        # Get review comments (inline comments on code)
        success, output = self._run_gh([
            "api", f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/comments",
            "--jq", "."
        ])
        
        comments = []
        if success and output:
            try:
                raw_comments = json.loads(output)
                
                # First pass: collect only original comments (not replies)
                for c in raw_comments:
                    # Skip reply comments - they have in_reply_to_id
                    if c.get("in_reply_to_id"):
                        continue
                        
                    comments.append(PRComment(
                        id=c["id"],
                        author=c["user"]["login"],
                        body=c["body"],
                        file_path=c.get("path"),
                        line=c.get("line") or c.get("original_line"),
                        diff_hunk=c.get("diff_hunk"),
                        created_at=c["created_at"],
                        state=c.get("state", "SUBMITTED")
                    ))
                
                # Second pass: populate replies and detect fixed status
                self._populate_reply_status(comments, raw_comments)
                
            except json.JSONDecodeError:
                pass
        
        # Also get issue comments (general PR comments)
        success, output = self._run_gh([
            "api", f"repos/{{owner}}/{{repo}}/issues/{pr_number}/comments",
            "--jq", "."
        ])
        
        if success and output:
            try:
                raw_comments = json.loads(output)
                for c in raw_comments:
                    comments.append(PRComment(
                        id=c["id"],
                        author=c["user"]["login"],
                        body=c["body"],
                        file_path=None,
                        line=None,
                        diff_hunk=None,
                        created_at=c["created_at"],
                        state="SUBMITTED"
                    ))
            except json.JSONDecodeError:
                pass
        
        return comments
    
    def _populate_reply_status(self, comments: list[PRComment], raw_comments: list):
        """Check replies to comments and determine status based on latest reply."""
        # Build a map of comment_id -> replies with timestamps
        reply_map = {}  # parent_id -> list of {body, created_at, author}
        for c in raw_comments:
            parent_id = c.get("in_reply_to_id")
            if parent_id:
                if parent_id not in reply_map:
                    reply_map[parent_id] = []
                reply_map[parent_id].append({
                    "body": c["body"],
                    "created_at": c["created_at"],
                    "author": c["user"]["login"]
                })
        
        # Markers for different statuses
        fixed_markers = [
            "fixed in commit", "fixed in ", "done", "resolved", "applied", "✅"
        ]
        reviewer_full_ack_markers = [
            "looks good now", "lgtm", "approved", "this looks good", 
            "great fix", "perfect", "all good", "ship it", "👍"
        ]
        reviewer_partial_ack_markers = [
            "thanks for applying", "thanks for fixing", "thanks for the fix",
            "thanks for following up"
        ]
        # Markers that indicate more work needed (even after partial ack)
        more_work_markers = [
            "you might want to", "you might also want", "could you also",
            "please also", "also need to", "still need", "one more thing",
            "introduced", "duplicates", "encoding issue", "clean this up",
            "double-check", "double check", "might want to clean",
            "want to double", "if you'd like"
        ]
        reject_markers = [
            "doesn't fix", "does not fix", "doesn't solve", "does not solve",
            "still broken", "still wrong", "still incorrect", "not quite",
            "please try again", "try again", "needs more work", "not right",
            "this is wrong", "that's not", "incorrect", "won't work",
            "doesn't work", "does not work", "please revise", "please update",
            "the issue is still", "problem remains", "❌", "👎"
        ]
        
        # Update comments with their replies
        for comment in comments:
            replies = reply_map.get(comment.id, [])
            comment.replies = replies
            
            if not replies:
                continue
            
            # Sort replies by created_at to get latest
            sorted_replies = sorted(replies, key=lambda r: r["created_at"])
            latest_reply = sorted_replies[-1]
            latest_body = latest_reply["body"].lower()
            
            # Check latest reply status - order matters!
            # 1. Check for explicit reject first
            if any(marker in latest_body for marker in reject_markers):
                comment.needs_rework = True
                comment.is_fixed = False
                comment.last_reply_summary = f"⚠️ Reviewer requested changes"
                continue
            
            # 2. Check for explicit fix markers from our tool (before reviewer reply)
            if any(marker in latest_body for marker in fixed_markers):
                comment.is_fixed = True
                comment.needs_rework = False
                comment.last_reply_summary = f"✅ Fixed"
                continue
            
            # 3. Check for FULL acknowledgment (no more work needed)
            if any(marker in latest_body for marker in reviewer_full_ack_markers):
                comment.is_fixed = True
                comment.needs_rework = False
                comment.last_reply_summary = f"✅ Approved by reviewer"
                continue
            
            # 4. Check for partial ack + more work suggested
            has_partial_ack = any(marker in latest_body for marker in reviewer_partial_ack_markers)
            has_more_work = any(marker in latest_body for marker in more_work_markers)
            
            if has_partial_ack and has_more_work:
                # Reviewer acknowledged but suggested more changes
                comment.needs_rework = True
                comment.is_fixed = False
                comment.last_reply_summary = f"⚠️ Partial fix - more changes suggested"
                continue
            elif has_partial_ack:
                # Pure acknowledgment without suggestions
                comment.is_fixed = True
                comment.needs_rework = False
                comment.last_reply_summary = f"✅ Approved by reviewer"
                continue
            
            # 5. Check ALL replies for fix markers (not just latest)
            for reply in replies:
                reply_body = reply["body"].lower()
                if any(marker in reply_body for marker in fixed_markers):
                    # Found a fix, but check if there's a reject after it
                    fix_time = reply["created_at"]
                    has_reject_after = any(
                        r["created_at"] > fix_time and 
                        any(m in r["body"].lower() for m in reject_markers + more_work_markers)
                        for r in replies
                    )
                    if has_reject_after:
                        comment.needs_rework = True
                        comment.is_fixed = False
                        comment.last_reply_summary = f"⚠️ Fix was rejected"
                    else:
                        comment.is_fixed = True
                        comment.last_reply_summary = f"✅ Fixed (pending review)"
                    break
    
    def reply_to_comment(self, pr_number: int, comment_id: int, body: str) -> bool:
        """Reply to a review comment."""
        success, _ = self._run_gh([
            "api", f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/comments/{comment_id}/replies",
            "-f", f"body={body}"
        ])
        return success
    
    def post_pr_comment(self, pr_number: int, body: str) -> bool:
        """Post a general comment on PR."""
        success, _ = self._run_gh([
            "pr", "comment", str(pr_number),
            "--body", body
        ])
        return success


class CommentAnalyzer:
    """Analyzes PR comments and categorizes them."""
    
    # Patterns for categorization
    APPROVAL_PATTERNS = [
        r'\blgtm\b', r'\bapproved?\b', r'\bship\s?it\b', r'👍', r'✅',
        r'\blooks?\s+good\b', r'\bnice\b', r'\bgreat\b'
    ]
    
    QUESTION_PATTERNS = [
        r'\?$', r'^why\b', r'^what\b', r'^how\b', r'^can\s+you\b',
        r'^could\s+you\b', r'^should\b', r'\bexplain\b'
    ]
    
    NITPICK_PATTERNS = [
        r'\bnit\b', r'\bnitpick\b', r'\bminor\b', r'\btypo\b',
        r'\bspacing\b', r'\bindent', r'\bwhitespace\b', r'\bformat'
    ]
    
    SUGGESTION_PATTERNS = [
        r'\bconsider\b', r'\bmight\b', r'\bcould\b', r'\bmaybe\b',
        r'\bsuggestion\b', r'\boptional\b', r'\bfyi\b'
    ]
    
    SECURITY_PATTERNS = [
        r'\bsecurity\b', r'\bvulnerability\b', r'\binjection\b', r'\bxss\b',
        r'\bsql\s*injection\b', r'\bcommand\s*injection\b', r'\bpath\s*traversal\b',
        r'\bdangerous\b', r'\baudit\b', r'\bmalicious\b', r'\bexploit\b',
        r'\bsensitive\s*data\b', r'\bapi.?token\b', r'\bsecret\b', r'\bcredential\b',
        r'\bopengrep\b', r'\bsemgrep\b', r'\bsnyk\b'
    ]
    
    CODE_FIX_PATTERNS = [
        r'\bshould\s+be\b', r'\bchange\s+to\b', r'\buse\b.*\binstead\b',
        r'\breplace\b', r'\bremove\b', r'\badd\b', r'\bmissing\b',
        r'\brename\b', r'\bwrong\b', r'\bincorrect\b', r'\bbug\b'
    ]
    
    # Auto-fixable patterns with fix templates
    AUTO_FIX_PATTERNS = {
        r'use\s+[`\']?(const|let)[`\']?\s+instead\s+of\s+[`\']?(var|let|const)[`\']?': 
            lambda m: f"Replace `{m.group(4) or m.group(3)}` with `{m.group(1)}`",
        r'remove\s+(unused|extra)\s+import':
            lambda m: "Remove unused import",
        r'add\s+missing\s+(semicolon|comma|bracket)':
            lambda m: f"Add missing {m.group(1)}",
        r'(typo|spelling).*[`\']?(\w+)[`\']?.*[`\']?(\w+)[`\']?':
            lambda m: f"Fix typo: `{m.group(2)}` → `{m.group(3)}`",
        r'extra\s+(space|whitespace|line)':
            lambda m: "Remove extra whitespace",
        r'missing\s+(space|newline)':
            lambda m: f"Add missing {m.group(1)}",
        r'should\s+(return|be)\s+[`\']?(\w+)[`\']?':
            lambda m: f"Change return value to `{m.group(2)}`",
        r'rename\s+[`\']?(\w+)[`\']?\s+to\s+[`\']?(\w+)[`\']?':
            lambda m: f"Rename `{m.group(1)}` to `{m.group(2)}`",
    }
    
    def analyze(self, comment: PRComment) -> PRComment:
        """Analyze and categorize a comment."""
        body_lower = comment.body.lower().strip()
        
        # Check approval first
        if self._matches_patterns(body_lower, self.APPROVAL_PATTERNS):
            comment.category = CommentCategory.APPROVAL
            comment.difficulty = FixDifficulty.DISCUSSION
            return comment
        
        # Check questions
        if self._matches_patterns(body_lower, self.QUESTION_PATTERNS):
            comment.category = CommentCategory.QUESTION
            comment.difficulty = FixDifficulty.DISCUSSION
            comment.draft_reply = self._generate_question_reply(comment)
            return comment
        
        # Check nitpicks
        if self._matches_patterns(body_lower, self.NITPICK_PATTERNS):
            comment.category = CommentCategory.NITPICK
            auto_fix = self._try_auto_fix(comment)
            if auto_fix:
                comment.difficulty = FixDifficulty.AUTO
                comment.suggested_fix = auto_fix
            else:
                comment.difficulty = FixDifficulty.SIMPLE
            return comment
        
        # Check security issues BEFORE suggestions (security issues often use "consider" language)
        if self._matches_patterns(body_lower, self.SECURITY_PATTERNS):
            comment.category = CommentCategory.CODE_FIX  # Security issues need fixing
            comment.difficulty = FixDifficulty.COMPLEX  # Security fixes need careful review
            return comment
        
        # Check suggestions
        if self._matches_patterns(body_lower, self.SUGGESTION_PATTERNS):
            comment.category = CommentCategory.SUGGESTION
            comment.difficulty = FixDifficulty.DISCUSSION
            comment.draft_reply = self._generate_suggestion_reply(comment)
            return comment
        
        # Check code fixes
        if self._matches_patterns(body_lower, self.CODE_FIX_PATTERNS):
            comment.category = CommentCategory.CODE_FIX
            auto_fix = self._try_auto_fix(comment)
            if auto_fix:
                comment.difficulty = FixDifficulty.AUTO
                comment.suggested_fix = auto_fix
            elif self._is_simple_fix(comment):
                comment.difficulty = FixDifficulty.SIMPLE
            else:
                comment.difficulty = FixDifficulty.COMPLEX
            return comment
        
        # Check for code blocks with fixes (even if not matching other patterns)
        if '```python' in comment.body or '```suggestion' in comment.body:
            comment.category = CommentCategory.CODE_FIX
            auto_fix = self._try_auto_fix(comment)
            if auto_fix:
                comment.difficulty = FixDifficulty.AUTO
                comment.suggested_fix = auto_fix
            elif self._is_simple_fix(comment):
                comment.difficulty = FixDifficulty.SIMPLE
            else:
                comment.difficulty = FixDifficulty.COMPLEX
            return comment
        
        # Check for logic issues
        if any(word in body_lower for word in ['logic', 'handle', 'case', 'error', 'null', 'undefined', 'edge', 'guard', 'none', 'typeerror', 'crash']):
            comment.category = CommentCategory.LOGIC_ISSUE
            # Check if there's a suggested fix pattern
            auto_fix = self._try_auto_fix(comment)
            if auto_fix:
                comment.difficulty = FixDifficulty.AUTO
                comment.suggested_fix = auto_fix
            elif self._is_simple_fix(comment):
                comment.difficulty = FixDifficulty.SIMPLE
            else:
                comment.difficulty = FixDifficulty.COMPLEX
            return comment
        
        # Default: unknown, treat as complex
        comment.category = CommentCategory.UNKNOWN
        comment.difficulty = FixDifficulty.COMPLEX
        return comment
    
    def _matches_patterns(self, text: str, patterns: list[str]) -> bool:
        """Check if text matches any pattern."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _try_auto_fix(self, comment: PRComment) -> Optional[str]:
        """Try to generate auto-fix for comment."""
        body_lower = comment.body.lower()
        
        for pattern, fix_func in self.AUTO_FIX_PATTERNS.items():
            match = re.search(pattern, body_lower, re.IGNORECASE)
            if match:
                return fix_func(match)
        
        # Check for code suggestion in comment (```suggestion blocks)
        suggestion_match = re.search(r'```suggestion\s*\n(.*?)\n```', comment.body, re.DOTALL)
        if suggestion_match:
            return f"Apply suggestion:\n{suggestion_match.group(1)}"
        
        # Check for python code blocks with simple patterns
        python_match = re.search(r'```python\s*\n(.*?)\n```', comment.body, re.DOTALL)
        if python_match:
            code = python_match.group(1).strip()
            # Simple one-liner or guard clause
            if code.count('\n') <= 2 and len(code) < 200:
                return f"Apply code fix:\n```python\n{code}\n```"
        
        # Check for inline code with "instead" pattern
        instead_match = re.search(r'[`\']([^`\']+)[`\']\s*instead', comment.body, re.IGNORECASE)
        if instead_match:
            return f"Use `{instead_match.group(1)}` instead"
        
        return None
    
    def _is_simple_fix(self, comment: PRComment) -> bool:
        """Determine if fix is simple (one-liner)."""
        simple_indicators = [
            'rename', 'typo', 'import', 'const', 'let', 'var',
            'semicolon', 'comma', 'bracket', 'parenthesis',
            'guard', 'check', 'if not', 'or []', 'or {}', '= None',
            'exists', 'missing'
        ]
        body_lower = comment.body.lower()
        
        # Check for simple code blocks (1-3 lines)
        code_match = re.search(r'```\w*\s*\n(.*?)\n```', comment.body, re.DOTALL)
        if code_match:
            code_lines = code_match.group(1).strip().split('\n')
            if len(code_lines) <= 3:
                return True
        
        return any(ind in body_lower for ind in simple_indicators)
    
    def _generate_question_reply(self, comment: PRComment) -> str:
        """Generate draft reply for question."""
        return f"_[Draft reply for question]_\n\n> {comment.body[:100]}...\n\nTODO: Explain the reasoning here."
    
    def _generate_suggestion_reply(self, comment: PRComment) -> str:
        """Generate draft reply for suggestion."""
        return f"_[Draft reply for suggestion]_\n\nThanks for the suggestion! [Accept/Decline with reason]"


class PRReviewManager:
    """Manages the full PR review workflow."""
    
    def __init__(self, working_dir: Optional[Path] = None):
        self.working_dir = working_dir or Path.cwd()
        self.fetcher = PRReviewFetcher(working_dir)
        self.analyzer = CommentAnalyzer()
    
    def analyze_pr(self, pr_identifier: str | int) -> Optional[PRReviewSummary]:
        """
        Analyze all comments on a PR.
        
        Args:
            pr_identifier: PR number or branch name
        """
        # Get PR info
        if isinstance(pr_identifier, int) or pr_identifier.isdigit():
            pr_info = self.fetcher.get_pr_by_number(int(pr_identifier))
        else:
            pr_info = self.fetcher.get_pr_for_branch(pr_identifier)
        
        if not pr_info:
            console.print(f"[red]✗[/red] Could not find PR: {pr_identifier}")
            return None
        
        pr_number = pr_info["number"]
        console.print(f"[green]✓[/green] Found PR #{pr_number}: {pr_info['title']}")
        
        # Fetch comments
        comments = self.fetcher.fetch_review_comments(pr_number)
        console.print(f"[green]✓[/green] Fetched {len(comments)} comments")
        
        if not comments:
            console.print("[yellow]No review comments found[/yellow]")
            return PRReviewSummary(
                pr_number=pr_number,
                pr_title=pr_info["title"],
                pr_url=pr_info["url"],
                total_comments=0
            )
        
        # Analyze each comment
        summary = PRReviewSummary(
            pr_number=pr_number,
            pr_title=pr_info["title"],
            pr_url=pr_info["url"],
            total_comments=len(comments)
        )
        
        for comment in comments:
            analyzed = self.analyzer.analyze(comment)
            
            if analyzed.category == CommentCategory.APPROVAL:
                summary.resolved.append(analyzed)
            elif analyzed.category == CommentCategory.RESOLVED:
                summary.resolved.append(analyzed)
            elif analyzed.difficulty == FixDifficulty.AUTO:
                summary.auto_fixable.append(analyzed)
            elif analyzed.difficulty == FixDifficulty.SIMPLE:
                summary.simple_fixes.append(analyzed)
            elif analyzed.difficulty == FixDifficulty.DISCUSSION:
                summary.discussions.append(analyzed)
            else:
                summary.complex_fixes.append(analyzed)
        
        return summary
    
    def generate_review_context(self, summary: PRReviewSummary, output_dir: Path) -> Path:
        """Generate context files for PR review."""
        review_dir = output_dir / ".copilot" / f"pr-{summary.pr_number}"
        review_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate main review file
        review_file = review_dir / "review.md"
        content = self._build_review_context(summary)
        review_file.write_text(content, encoding='utf-8')
        
        # Generate fixes file
        if summary.auto_fixable or summary.simple_fixes or summary.complex_fixes:
            fixes_file = review_dir / "fixes.md"
            fixes_content = self._build_fixes_context(summary)
            fixes_file.write_text(fixes_content, encoding='utf-8')
        
        # Generate discussions file
        if summary.discussions:
            discussions_file = review_dir / "discussions.md"
            discussions_content = self._build_discussions_context(summary)
            discussions_file.write_text(discussions_content, encoding='utf-8')
        
        # Save raw data for CLI
        data_file = review_dir / "review_data.json"
        data = {
            "pr_number": summary.pr_number,
            "pr_title": summary.pr_title,
            "pr_url": summary.pr_url,
            "auto_fixable": [c.to_dict() for c in summary.auto_fixable],
            "simple_fixes": [c.to_dict() for c in summary.simple_fixes],
            "complex_fixes": [c.to_dict() for c in summary.complex_fixes],
            "discussions": [c.to_dict() for c in summary.discussions]
        }
        data_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
        
        return review_file
    
    def _build_review_context(self, summary: PRReviewSummary) -> str:
        """Build main review context markdown."""
        auto_count = len(summary.auto_fixable)
        simple_count = len(summary.simple_fixes)
        complex_count = len(summary.complex_fixes)
        discussion_count = len(summary.discussions)
        
        return f'''# 📝 PR Review: #{summary.pr_number}

**{summary.pr_title}**

[View PR]({summary.pr_url})

---

## Summary

| Category | Count | Action |
|----------|-------|--------|
| 🤖 Auto-fixable | {auto_count} | Run `agentic pr fix --auto` |
| 🔧 Simple fixes | {simple_count} | Quick manual fixes |
| 🔨 Complex fixes | {complex_count} | Needs Copilot assistance |
| 💬 Discussions | {discussion_count} | Reply needed |
| ✅ Resolved | {len(summary.resolved)} | No action |

**Total:** {summary.total_comments} comments

---

## Quick Actions

### Auto-fix all simple issues
```bash
agentic pr fix {summary.pr_number} --auto
```

### Review fixes interactively
```bash
agentic pr fix {summary.pr_number}
```

### Reply to discussions
```bash
agentic pr reply {summary.pr_number}
```

---

## Files

- [fixes.md](fixes.md) - All code fixes needed
- [discussions.md](discussions.md) - Questions & suggestions to reply

---
_Generated by Agentic Workflow_
'''
    
    def _build_fixes_context(self, summary: PRReviewSummary) -> str:
        """Build fixes context markdown."""
        sections = []
        
        if summary.auto_fixable:
            sections.append("## 🤖 Auto-fixable\n")
            sections.append("_These can be fixed automatically:_\n")
            for c in summary.auto_fixable:
                sections.append(self._format_fix_comment(c))
        
        if summary.simple_fixes:
            sections.append("\n## 🔧 Simple Fixes\n")
            sections.append("_Quick one-liner fixes:_\n")
            for c in summary.simple_fixes:
                sections.append(self._format_fix_comment(c))
        
        if summary.complex_fixes:
            sections.append("\n## 🔨 Complex Fixes\n")
            sections.append("_Need analysis - use Copilot:_\n")
            for c in summary.complex_fixes:
                sections.append(self._format_fix_comment(c))
                sections.append(f'''
**Copilot Prompt:**
```
@workspace Fix this review comment in {c.file_path or 'the code'}:
"{c.body[:200]}"
```
''')
        
        return f'''# 🔧 Fixes Needed: PR #{summary.pr_number}

{"".join(sections)}

---
_Generated by Agentic Workflow_
'''
    
    def _format_fix_comment(self, comment: PRComment) -> str:
        """Format a fix comment for markdown."""
        location = ""
        if comment.file_path:
            location = f"📍 `{comment.file_path}`"
            if comment.line:
                location += f" (line {comment.line})"
        
        fix_section = ""
        if comment.suggested_fix:
            fix_section = f"\n**Suggested fix:** {comment.suggested_fix}"
        
        return f'''
### {comment.category.value.replace('_', ' ').title()}
{location}

> {comment.body}

**Author:** @{comment.author}
{fix_section}

---
'''
    
    def _build_discussions_context(self, summary: PRReviewSummary) -> str:
        """Build discussions context markdown."""
        sections = []
        
        for c in summary.discussions:
            draft = c.draft_reply or "_[Write your reply here]_"
            sections.append(f'''
### {c.category.value.replace('_', ' ').title()} from @{c.author}

> {c.body}

**Draft reply:**
{draft}

---
''')
        
        return f'''# 💬 Discussions: PR #{summary.pr_number}

_Review and customize replies before posting._

{"".join(sections)}

## Post all replies
```bash
agentic pr reply {summary.pr_number} --confirm
```

---
_Generated by Agentic Workflow_
'''


# Singleton
pr_review_manager = PRReviewManager()
