# Roles & Collaboration
# AI Agent Roles & Collaboration

This file defines a small set of AI-agent roles and short prompt templates you can use to instruct the assistant(s) when working on the Infodemica site. The goal is to keep the workflow simple and actionable: each AI role performs a focused job and returns concrete outputs (patches, checks, docs) that humans review and run.

**Principles**
- Keep agent roles minimal and practical.
- Agents produce concrete, reviewable artifacts (apply_patch-style patches, tests, docs, or analysis).
- Humans review, run, and approve changes before merging or deploying.

**AI Agent Roles**
- **Developer (AI)**
	- Purpose: Implement features or fixes, produce code patches, and add tests.
	- Expected output: an `apply_patch`-style diff (or file content), minimal unit tests, and a short PR description + run instructions.
	- Prompt template: `You are the Developer AI. Implement: <short task description>. Return only an apply_patch diff and a short explanation of what changed, a test or smoke-check, and a one-line 'how to run locally' command. Ask clarifying questions if requirements are ambiguous. Keep changes minimal and safe.`

- **Quality Reviewer (AI)**
	- Purpose: Review code patches, point out bugs, missing tests, security issues, and suggest minimal fixes.
	- Expected output: a review checklist, prioritized issues with line references, and a follow-up patch if straightforward to fix.
	- Prompt template: `You are the Quality Reviewer AI. Given this patch or file, run a static review: list incorrect assumptions, bugs, test gaps, security/privacy concerns, and propose minimal fixes. If a one-file fix is safe, return an apply_patch. Otherwise list steps for a human reviewer.`

- **Infra/DevOps Assistant (AI)**
	- Purpose: Propose infrastructure changes (Celery, Redis, storage), generate config snippets (docker-compose, systemd units), and sanity-check deployment steps.
	- Expected output: small config files, a docker-compose snippet, and a concise checklist of steps to run in staging.
	- Prompt template: `You are the Infra AI. Provide a minimal docker-compose snippet to run Redis, a Celery worker, and the Django dev server, plus commands to run a smoke test. Keep it simple for local dev.`

- **Coordinator (AI)**
	- Purpose: Break a larger task into smaller subtasks, assign them to agent roles, and produce a todo checklist.
	- Expected output: a clear, ordered todo list with small actionable items, and recommended next step.
	- Prompt template: `You are the Coordinator AI. Given the goal '<goal>', produce 5–8 ordered tasks, each 1–2 sentences, and assign an agent role to each task.`

**How to use these agents**
- Always include acceptance criteria and required files/paths in the prompt (e.g., which file to edit, expected outputs).
- Ask the Developer AI for an `apply_patch` style diff and then send that diff to the Quality Reviewer AI for review before applying.
- Use the Coordinator AI when the task is larger than one patch; it will split work and assign roles.

**Rules and expectations for AI outputs**
- Prefer small, focused patches. If more than 3 files change, break into multiple patches.
- Include tests or a smoke-check where possible.
- If the change requires infra (Redis, S3, ffmpeg), the Infra AI should provide a clear checklist and a minimal config snippet.
- Flag any external API keys or secrets and do not print them in outputs.

**Human responsibilities**
- Review AI-produced patches and run tests locally.
- Approve, modify, or reject patches and handle deployment.

**Example workflow (minimal)**
1. Coordinator AI produces a todo list: `Add Celery scaffold`, `Add task wrapper`, `Enqueue from views`.
2. Developer AI implements the Celery scaffold and returns an `apply_patch` diff.
3. Quality Reviewer AI reviews the patch; if small fixes are needed it returns another `apply_patch`.
4. Dev runs tests, deploys worker, and verifies behavior.

Keep the roles light and iterative — the AI's job is to accelerate drafting and checks, while humans retain final control.

---

If you want, I can now scaffold a set of short prompt templates in `ai-prompts/` (one file per role) so we can reuse them when invoking the assistant. Would you like me to add those prompt templates?
