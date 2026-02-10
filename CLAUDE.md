# Project Bootstrap & Development Standards

> When Claude Code reads this file, it should treat Section 1 as actionable setup tasks
> and Section 2 as ongoing behavioral rules to follow throughout development.

---

## Section 1: Project Setup (Run Once)

When starting a new project or first reading this file, execute the following setup steps.
Ask the user: "Do you want me to run all setup steps automatically, or list them for you to confirm one by one?"

### Step 1.1: Check Available Skills

List available skills that can help with the project:

```
/help
```

Claude Code has built-in skills for common tasks like creating commits, reviewing PRs, working with PDFs, etc. Use the appropriate skill when needed.

### Step 1.2: Create Security Configuration

If `.claude/settings.json` does not exist, create it with these deny rules:

```json
{
  "permissions": {
    "deny": [
      "Bash(cat .env*)",
      "Bash(cat */.env*)",
      "Bash(*secret*)",
      "Bash(*password*)",
      "Bash(*.pem)",
      "Bash(*.key)"
    ]
  }
}
```

### Step 1.3: Create .gitignore

If `.gitignore` does not exist, create one with at minimum:

```
# Secrets
.env
.env.*
.env.local

# Dependencies
node_modules/
vendor/
__pycache__/
*.pyc
venv/
.venv/

# Build outputs
dist/
build/
.next/
out/

# OS files
.DS_Store
Thumbs.db

# IDE (uncomment if not sharing configs)
# .idea/
# .vscode/
```

### Step 1.4: Create .env.example

If the project uses environment variables, create `.env.example` with placeholder values:

```
# Copy this file to .env and fill in your actual values
# NEVER commit .env to version control

API_KEY=your_api_key_here
DATABASE_URL=your_database_url_here
```

### Step 1.5: Verify Security Setup

After completing all steps, verify:
1. `.env` is listed in `.gitignore`
2. `.claude/settings.json` exists with deny rules for sensitive commands
3. No secrets exist in any tracked files (`git status` and review staged files)

Report the setup results to the user.

---

## Section 2: Ongoing Development Rules

These rules apply to ALL coding activities throughout the project lifecycle.

### 2.1 Secrets Management (Always Enforced)

- NEVER hard-code API keys, passwords, tokens, or credentials in source code
- ALL secrets must go through environment variables loaded from `.env`
- If a user provides a secret in a prompt, warn them immediately and do NOT echo it back
- Before every commit, check that no sensitive data is in staged changes
- When creating new integrations or API connections, always use `.env` pattern from the start
- **Before every `git push`, run security checks to scan for leaked secrets**

### 2.2 Testing Discipline

- Write unit tests for every new function or module
- Run existing tests BEFORE and AFTER making changes
- Test both happy paths and edge cases (empty input, invalid data, boundary values)
- Name tests descriptively: the name should explain what is being verified
- If the project has no testing framework, set one up before writing the first feature

### 2.3 Error Handling

- Every external call (API, database, file system) must have proper error handling
- Error messages must be descriptive and actionable
  - ❌ `catch(e) { console.log("error") }`
  - ✅ `catch(e) { console.error("Failed to fetch user data:", e.message) }`
- Never silently swallow errors
- Use appropriate error types and HTTP status codes

### 2.4 Code Quality & Refactoring

- Keep functions small and focused: one function, one job
- Use clear, descriptive names — no vague abbreviations
- Comment the "why", not the "what"
- All code and comments must be in English
- After completing a feature, review for duplication and unnecessary complexity
- Suggest refactoring when copy-paste patterns or overly long functions appear
- Run tests before and after refactoring to ensure behavior is unchanged

### 2.5 Version Control Habits

- Commit frequently with meaningful messages
- Use conventional commit format: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`
- Create a new branch for each feature or fix before making changes
- Never force-push to shared branches

### 2.6 Planning Before Coding

- For tasks involving more than 3 files, create a plan first
- Break complex tasks into stages with clear success criteria
- Get user confirmation on the plan before writing code
- Use Claude Code's plan mode for architectural decisions

### 2.7 Explaining Code to the User

- After generating or modifying code, provide a plain-language summary
- Use analogies and simple terms when the user is not a developer
- Offer to explain complex logic step by step
- When adding a new dependency, explain what it does and why it is needed

### 2.8 Dependency Management

- Only add dependencies that are genuinely needed
- Verify that packages actually exist and are actively maintained before installing
- Prefer well-known, widely-used packages over obscure alternatives
- Check for known security vulnerabilities before adding a dependency
