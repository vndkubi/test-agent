# Agentic Development Workflow

🚀 Automated workflow: Jira PBI → TDD Implementation → PR Creation → Jira Update

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```env
JIRA_SERVER=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token

# Customize Jira workflow statuses to match yours
JIRA_STATUS_TODO=To Do
JIRA_STATUS_IN_PROGRESS=In Progress
JIRA_STATUS_IN_REVIEW=In Review
JIRA_STATUS_DONE=Done
```

### 3. Ensure GitHub CLI is authenticated

```bash
gh auth login
```

### 4. Run Workflow

```bash
python workflow.py PBI-123
```

## Workflow Steps

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  1️⃣  Fetch Jira PBI details                                 │
│       ↓                                                     │
│  2️⃣  Create feature branch (feature/PBI-123)                │
│       ↓                                                     │
│  3️⃣  Update Jira status → In Progress                       │
│       ↓                                                     │
│  4️⃣  Generate Copilot context (.copilot/context.md)         │
│       ↓                                                     │
│  5️⃣  🛑 MANUAL: Implement with TDD using Copilot            │
│       ↓                                                     │
│  6️⃣  Commit, push, create PR (auto-filled from Jira)        │
│       ↓                                                     │
│  7️⃣  Update Jira status → In Review                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Usage Options

```bash
# Normal workflow
python workflow.py PBI-123

# Create draft PR
python workflow.py PBI-123 --draft

# Skip Jira operations (testing)
python workflow.py PBI-123 --skip-jira

# Specify working directory
python workflow.py PBI-123 --dir /path/to/project
```

## VSCode Integration

Use `Ctrl+Shift+P` → "Tasks: Run Task" → Select workflow task:

- **🚀 Run Workflow** - Full workflow with Jira
- **🧪 Run Workflow (Test Mode)** - Skip Jira operations
- **📋 Run Workflow (Draft PR)** - Create draft PR

## Project Structure

```
agentic/
├── workflow.py              # Main entry point
├── requirements.txt         # Python dependencies
├── .env.example            # Environment template
├── .env                    # Your configuration (gitignored)
├── config/
│   ├── __init__.py
│   └── settings.py         # Configuration classes
├── src/
│   ├── __init__.py
│   ├── jira_connector.py   # Jira API operations
│   ├── context_generator.py # Copilot context builder
│   └── git_automation.py   # Git & PR operations
└── .vscode/
    └── tasks.json          # VSCode tasks
```

## Getting Jira API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a name and copy the token
4. Paste in your `.env` file

## Customizing Jira Workflow

Update the status names in `.env` to match your Jira workflow:

```env
JIRA_STATUS_TODO=To Do
JIRA_STATUS_IN_PROGRESS=In Development
JIRA_STATUS_IN_REVIEW=Code Review
JIRA_STATUS_DONE=Closed
```

## TDD with Copilot

When the workflow pauses for implementation:

1. Open `.copilot/context.md` - contains parsed requirements
2. Use Copilot Chat prompts provided in the context file
3. Follow TDD:
   - 🔴 **Red**: Write failing tests first
   - 🟢 **Green**: Implement to pass tests
   - 🔵 **Blue**: Refactor while keeping tests green
4. Return to terminal and confirm PR creation

## License

MIT
