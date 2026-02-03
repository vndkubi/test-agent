# 🚀 Agentic Development Workflow

Automated workflow: **Jira PBI → TDD Implementation → PR Creation → PR Review → Jira Update**

## 📋 Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Use Cases](#use-cases)
- [Commands Reference](#commands-reference)
- [Troubleshooting](#troubleshooting)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎫 **Jira Integration** | Fetch PBI details, update status automatically |
| 🌿 **Git Automation** | Create branches, commit, push |
| 📝 **PR Creation** | Auto-fill PR from Jira content |
| 🤖 **Copilot Context** | Generate multi-file context for GitHub Copilot |
| ✅ **TODO Manager** | Interactive task tracking per PBI |
| 🔍 **PR Review** | Analyze PR comments, categorize by complexity |
| 🔧 **Auto-Fix** | Auto-apply simple PR review fixes |

---

## 📦 Installation

### Option 1: Install from GitHub (Recommended)

```bash
# Clone repository
git clone https://github.com/vndkubi/test-agent.git
cd test-agent

# Install globally
pip install -e .

# Verify installation
agentic --version
```

### Option 2: Install from source

```bash
# Clone and install dependencies
git clone https://github.com/vndkubi/test-agent.git
cd test-agent
pip install -r requirements.txt

# Install as global CLI
pip install -e .
```

### Prerequisites

1. **Python 3.10+**
2. **GitHub CLI** - [Install gh](https://cli.github.com/)
   ```bash
   # Authenticate gh
   gh auth login
   ```
3. **Jira API Token** - [Create token](https://id.atlassian.com/manage-profile/security/api-tokens)

---

## ⚙️ Configuration

### Config File Locations (Priority Order)

1. `.env` in **current working directory** (project-specific)
2. `~/.agentic/.env` in **home directory** (global default)
3. `.env` in **agentic package directory**

### Setup for Your Repository

**Step 1:** Create `.env` in your project root:

```bash
cd /path/to/your-project
touch .env
```

**Step 2:** Add configuration:

```env
# ========================================
# JIRA CONFIGURATION
# ========================================
JIRA_SERVER=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token

# Jira Workflow Status Mapping (customize to match your board)
JIRA_STATUS_TODO=To Do
JIRA_STATUS_IN_PROGRESS=In Progress
JIRA_STATUS_IN_REVIEW=In Review
JIRA_STATUS_DONE=Done

# ========================================
# GITHUB CONFIGURATION (Optional)
# ========================================
# Uses gh CLI auth by default - no config needed
# GITHUB_REPO=owner/repo-name  # Only if different from git remote
```

### Get Jira API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Copy token to `JIRA_API_TOKEN`

### Verify Configuration

```bash
# Test Jira connection
agentic TEST-1 --skip-jira  # Dry run without Jira

# Or test with real Jira (will show error if config is wrong)
agentic YOUR-PBI-123
```

---

## 🎯 Use Cases

### Use Case 1: Start New PBI Work

**Scenario:** You have a Jira ticket `PROJ-456` and want to start implementing.

```bash
cd /path/to/your-project
agentic PROJ-456
```

**What happens:**
1. ✅ Fetches Jira PBI details
2. ✅ Creates branch `feature/PROJ-456`
3. ✅ Updates Jira status → "In Progress"
4. ✅ Generates context files in `.copilot/PROJ-456/`
5. ⏸️ Waits for you to implement
6. ✅ Creates PR with Jira content
7. ✅ Updates Jira status → "In Review"

### Use Case 2: Track Progress with TODO

**Scenario:** You want to track implementation progress.

```bash
# View TODO list
agentic todo PROJ-456

# Interactive mode (mark tasks done)
agentic todo PROJ-456 -i
```

### Use Case 3: Review PR Comments

**Scenario:** Your PR has review comments and you want to analyze them.

```bash
# Analyze PR #42
agentic pr review 42
```

**Output:**
```
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Category         ┃ Count ┃ Action                ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ 🤖 Auto-fixable  │     2 │ agentic pr fix --auto │
│ 🔧 Simple fixes  │     1 │ Quick manual fix      │
│ 🔨 Complex fixes │     3 │ Use Copilot           │
│ 💬 Discussions   │     1 │ Reply needed          │
└──────────────────┴───────┴───────────────────────┘
```

### Use Case 4: Auto-Fix PR Comments

**Scenario:** You want to quickly fix simple review comments.

```bash
# Auto-fix and push to PR branch
agentic pr fix 42 --auto
```

**What happens:**
1. ✅ Switches to PR branch automatically
2. ✅ Applies simple fixes (typos, whitespace, etc.)
3. ✅ Commits and pushes to PR branch
4. ✅ Replies to PR comments with commit hash

### Use Case 5: Multiple Projects Setup

**Scenario:** You work on multiple repositories with different Jira boards.

**Project A:**
```bash
cd ~/projects/project-a
# Create .env with JIRA_SERVER=https://company-a.atlassian.net
agentic PROJA-123
```

**Project B:**
```bash
cd ~/projects/project-b
# Create .env with JIRA_SERVER=https://company-b.atlassian.net
agentic PROJB-456
```

### Use Case 6: Test Without Jira

**Scenario:** You want to test the workflow without Jira connection.

```bash
# Skip all Jira operations
agentic TEST-1 --skip-jira
```

### Use Case 7: Create Draft PR

**Scenario:** You want to create a draft PR for early feedback.

```bash
agentic PROJ-789 --draft
```

---

## 📖 Commands Reference

### Main Workflow

```bash
agentic <PBI-KEY> [options]

Options:
  --skip-jira       Skip Jira operations (for testing)
  --draft           Create PR as draft
  --dir, -d DIR     Project directory (default: current)
  --version, -v     Show version
```

### TODO Manager

```bash
agentic todo <PBI-KEY> [options]

Options:
  -i, --interactive    Interactive mode
```

**Interactive Commands:**
- `n` - Start next pending task
- `d` - Mark current task done
- `s` - Start specific task (by ID)
- `u` - Undo last done
- `q` - Quit

### PR Review

```bash
agentic pr review <PR-NUMBER> [options]

Options:
  --dir, -d DIR     Project directory
```

**Generated Files:**
- `.copilot/pr-<N>/review.md` - Full analysis
- `.copilot/pr-<N>/fixes.md` - Copilot prompts for complex fixes
- `.copilot/pr-<N>/discussions.md` - Reply suggestions

### PR Fix

```bash
agentic pr fix <PR-NUMBER> [options]

Options:
  --auto            Apply fixes without confirmation
  --dry-run         Show what would be done
  --dir, -d DIR     Project directory
```

---

## 🗂️ Generated Context Files

When you run `agentic <PBI-KEY>`, it generates:

```
.copilot/
└── <PBI-KEY>/
    ├── index.md           # Navigation & workflow overview
    ├── requirements.md    # Parsed Jira requirements
    ├── tests.md           # TDD test plan
    ├── implementation.md  # Implementation guide
    ├── todo.json          # Task data (for CLI)
    └── todo.md            # Human-readable tasks

tests/
└── test_<pbi_key>.py      # Pytest skeleton from AC
```

**Use with Copilot Chat:**
```
@workspace Analyze #file:.copilot/PROJ-123/requirements.md and suggest implementation
```

---

## 🔧 Troubleshooting

### "Jira connection failed"

```bash
# Check your .env file
cat .env

# Verify Jira URL is correct (include https://)
JIRA_SERVER=https://your-company.atlassian.net

# Verify API token is valid
# Create new token: https://id.atlassian.com/manage-profile/security/api-tokens
```

### "gh CLI not authenticated"

```bash
# Login to GitHub
gh auth login

# Verify auth
gh auth status
```

### "Branch already exists"

```bash
# Delete local branch and retry
git branch -D feature/PBI-123
agentic PBI-123
```

### "Could not find PR"

```bash
# List open PRs
gh pr list

# Use PR number (not branch name)
agentic pr review 42
```

### "No .env found"

```bash
# Create .env in project root
cp /path/to/test-agent/.env.example .env
# Edit with your credentials
```

---

## 🔄 Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENTIC WORKFLOW                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📥 INPUT: agentic PROJ-123                                     │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    │
│  │ Fetch Jira  │───▶│ Create Branch│───▶│ Generate Context│    │
│  │ PBI Details │    │ feature/...  │    │ .copilot/       │    │
│  └─────────────┘    └──────────────┘    └─────────────────┘    │
│                                                │                │
│       ┌────────────────────────────────────────┘                │
│       ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  🛑 MANUAL: Implement with Copilot (TDD)                │   │
│  │     - Open .copilot/PROJ-123/index.md                   │   │
│  │     - Use Copilot Chat with context files               │   │
│  │     - Track progress: agentic todo PROJ-123 -i          │   │
│  └─────────────────────────────────────────────────────────┘   │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    │
│  │ Commit &    │───▶│ Create PR    │───▶│ Update Jira     │    │
│  │ Push        │    │ (auto-fill)  │    │ → In Review     │    │
│  └─────────────┘    └──────────────┘    └─────────────────┘    │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  🔄 PR REVIEW CYCLE                                     │   │
│  │     - agentic pr review <PR#>  → Analyze comments       │   │
│  │     - agentic pr fix <PR#> --auto → Apply fixes         │   │
│  │     - Repeat until approved                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  📤 OUTPUT: Merged PR, Jira updated to Done                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📝 Example: Full Workflow Session

```bash
# 1. Go to your project
cd ~/projects/my-app

# 2. Create project-specific .env (first time only)
cat > .env << 'EOF'
JIRA_SERVER=https://mycompany.atlassian.net
JIRA_EMAIL=dev@mycompany.com
JIRA_API_TOKEN=ATATT3xFfGF0xxxx
JIRA_STATUS_IN_PROGRESS=In Progress
JIRA_STATUS_IN_REVIEW=Code Review
EOF

# 3. Start working on PBI
agentic MYAPP-123

# 4. Open context in VSCode
code .copilot/MYAPP-123/index.md

# 5. Track progress interactively
agentic todo MYAPP-123 -i

# 6. After PR is created, handle reviews
agentic pr review 15
agentic pr fix 15 --auto

# 7. Done! PR merged, Jira updated automatically
```

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m 'Add my feature'`
4. Push: `git push origin feature/my-feature`
5. Create Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
