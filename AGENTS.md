# Instructions for Coding Agents

Before making any changes:
1. Read PROJECT_CONTEXT.md completely.
2. Inspect the relevant source files and tests.
3. Check git status before editing.
4. Follow the existing architecture and conventions.

Implementation rules:
- Keep changes minimal and avoid unnecessary abstractions.
- Reuse existing models, services, and utilities.
- Do not add dependencies or introduce frameworks without a clear need.
- Never expose secrets or modify .env.
- Do not commit generated files or __pycache__.
- Add or update tests for every meaningful behavior change.
- Tests must not call external LLM APIs unless explicitly requested.
- Run the relevant tests and the full pytest suite when practical.
- Never claim tests passed unless they were actually run.

After every implementation task:
1. Update PROJECT_CONTEXT.md with completed changes,
   current architecture, tests, known issues, and next steps.
2. Keep the context concise and factual.
3. Preserve important design decisions and limitations.
4. Do not overwrite useful context with vague summaries.
5. Report changed files, test results, and remaining issues.

Do not implement unrelated roadmap items without approval.
