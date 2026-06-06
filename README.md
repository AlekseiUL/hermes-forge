# Hermes Forge

![Hermes Forge: самоулучшение агента через evidence, evals и review gates](docs/assets/hermes-forge-agent-self-improvement.jpg)

Universal local-first improvement loop for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Forge helps any Hermes user answer one practical question:

> What can my agent setup improve, why, how do I prove it, and what is the safest next step?

It scans a Hermes home, collects safe evidence, groups weak signals, and produces reviewable improvement opportunities with hypotheses, experiments, success criteria and safe next steps.

It is **not autonomous self-modification**. It does not rewrite your agent by itself. The candidate `apply` path can run one bounded executor after explicit approval: `skill_frontmatter_metadata_v1`, which changes only approved `SKILL.md` frontmatter metadata after creating a local backup.

## Why this exists

Hermes Forge is inspired by the practical idea behind evidence-driven self-improvement work: improvement should not mean blind self-editing. It should mean a controlled loop where real behavior produces observations, observations become evidence, evidence becomes an improvement candidate, and the candidate is checked before anyone applies it.

For Hermes Agent, that loop becomes:

```text
Hermes runtime -> observations -> evidence -> opportunities -> experiments -> candidates -> apply gate
```

This repository is **Anthropic-inspired**, not Anthropic-affiliated, and not an implementation of an official Anthropic system or paper. It translates the principle into a practical, local-first improvement loop for Hermes users.

## Operating flow

```text
improve --mode read-only -> evidence -> findings -> opportunities -> report -> optional gated change
```

The core idea is:

```text
found -> checked -> proposed improvement -> experiment/eval -> safe next step
```

## Who is this for?

Hermes Forge is for:

- Hermes Agent users with multiple profiles, skills, cron jobs or runtime logs;
- developers building safer agent workflows;
- teams that want evidence before changing skills, routing, tasks or automations;
- maintainers who want a repeatable improvement rhythm without silent self-modification.

It is not:

- an official Hermes Agent project;
- an Anthropic project;
- a background agent that edits itself automatically;
- a security scanner or secret collector;
- a “fix everything” button.

## What it can improve today

Forge currently finds improvement candidates from:

- profile inventory;
- skill frontmatter metadata;
- cron metadata;
- bounded log categories and safe classifiers;
- session DB aggregate metadata;
- optional Kanban SQLite aggregate metadata;
- optional existing Doctor report summaries.

Then it creates an improvement report that says: what can become better, what evidence supports it, how to test the improvement, what success looks like, and why the change must not be applied automatically.

## Quick start from source

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
hermes-forge doctor
hermes-forge capabilities
```

## One-command read-only improvement loop

Run Forge against a Hermes home without changing it:

```bash
hermes-forge improve --mode read-only --hermes-home ~/.hermes --all-profiles --out ./forge-runs/latest
```

Compare with a previous run when you have one:

```bash
hermes-forge improve --mode read-only --hermes-home ~/.hermes --all-profiles --baseline ./forge-runs/previous --out ./forge-runs/latest
```

Open:

```text
./forge-runs/latest/report.md
```

The report answers:

- what can be improved;
- why Forge thinks so;
- what evidence exists;
- what state the opportunity is in (`watch_only`, `needs_owner_decision`, `ready_for_experiment`, `ready_for_diff_preview`);
- what experiment or eval would prove the improvement;
- what typed safe next step follows (`review`, `create_eval`, `open_diff`, `ask_approval`, `no_change`);
- how this run compares with a previous baseline, if provided;
- what Forge did not touch.

Artifacts include:

- `run.json`
- `policy.json`
- `inventory.json`
- `evidence-ledger.jsonl`
- `findings.json`
- `dedup-groups.json`
- `opportunities.json`
- `proposals.json`
- `scan-summary.json`
- `baseline-comparison.json`
- `report.md`
- `redaction-report.json`

## Experiment planner

Turn one opportunity into a safe experiment plan/result without applying changes:

```bash
hermes-forge experiment --opportunity ./forge-runs/latest/opportunities.json --id opp-0001 --out ./forge-runs/experiments/opp-0001
```

For allowlisted deterministic plans only, request readiness validation:

```bash
hermes-forge experiment --opportunity ./forge-runs/latest/opportunities.json --id opp-0001 --out ./forge-runs/experiments/opp-0001 --run
```

Experiment artifacts include:

- `experiment-plan.json`
- `experiment-result.json`
- `checks.json`
- `expected-outcome.md`
- `experiment.md`

Experiment statuses:

- `PLAN_ONLY`
- `READY_TO_RUN`
- `PASSED`
- `FAILED`
- `BLOCKED_NEEDS_OWNER_CONTEXT`

`experiment` never executes arbitrary commands from an opportunity. In this release `--run` validates readiness for exact allowlisted plans; it does not shell out to the documented eval command and does not mark experiments as passed.

## Diff preview

Turn an experiment result into a preview-only change package:

```bash
hermes-forge diff-preview --experiment ./forge-runs/experiments/opp-0001 --hermes-home ~/.hermes --out ./forge-runs/diff-preview/opp-0001
```

Diff-preview artifacts include:

- `diff-preview.json`
- `diff-preview.md`
- `proposed-files.json`
- `risk-check.json`
- `rollback-plan.md`
- `tests-to-run.md`
- `candidate-patch.json`
- `candidate.diff`
- `approval-checklist.md`

`diff-preview` shows what kind of file/change could be prepared next, why, what tests should run, and what rollback would be needed. When the experiment is ready, it also writes a **candidate patch preview**: a unified diff against a virtual review path. That diff is for review only. It has no live target path, changes zero files, and still requires a separate approval/apply gate.

## Apply gate and first executor

Validate and execute a bounded candidate after explicit approval:

```bash
hermes-forge apply \
  --candidate ./forge-runs/diff-preview/opp-0001/candidate-patch.json \
  --approve 'approve:hermes-forge-candidates/opp-0001/skill_frontmatter.md' \
  --live-target ~/.hermes/profiles/operator/skills/example/SKILL.md \
  --hermes-home ~/.hermes \
  --out ./forge-runs/apply/opp-0001 \
  --execute
```

The first registered executor is intentionally narrow:

```text
skill_frontmatter_metadata_v1
```

It can only change approved `SKILL.md` frontmatter keys:

- `description`
- `tags`
- `version`
- `category`

It does not edit the skill body, configs, memory, cron, runtime files, or arbitrary unified diffs. If the candidate does not contain `executor_id: skill_frontmatter_metadata_v1` plus an allowed `frontmatter_patch`, Forge stops before mutation.

Apply artifacts include:

- `apply-plan.json`
- `apply-plan.md`
- `backup-manifest.json`
- `apply-result.json`
- local-private backup under `backups/` when execution happens

Expected bounded executor result when all gates pass and `--execute` is present:

```json
{"status": "APPLY_EXECUTED", "files_changed": 1, "executor_id": "skill_frontmatter_metadata_v1"}
```

Expected result for virtual candidates without a registered executor:

```json
{"status": "APPLY_BLOCKED_NO_EXECUTOR"}
```

## Low-level example flow

These commands use synthetic fixtures from this source checkout:

```bash
hermes-forge scan --hermes-home tests/fixtures/hermes_home_minimal --all-profiles --kanban-db tests/fixtures/kanban/kanban.db --doctor-report tests/fixtures/doctor/report.json --out /tmp/hermes-forge-scan
hermes-forge analyze --scan /tmp/hermes-forge-scan --out /tmp/hermes-forge-scan/analysis
hermes-forge propose --analysis /tmp/hermes-forge-scan/analysis --out /tmp/hermes-forge-scan/proposals
hermes-forge eval --proposal /tmp/hermes-forge-scan/proposals/prop-0001/proposal.json --out /tmp/hermes-forge-scan/evals/prop-0001
hermes-forge apply --proposal /tmp/hermes-forge-scan/proposals/prop-0001/proposal.json
```

For most users, start with `improve --mode read-only`; the low-level commands are kept for inspection and tooling.

Expected MVP apply result:

```json
{"status": "APPLY_DISABLED_IN_MVP"}
```

Legacy proposal apply still exits non-zero by design. Candidate apply exits zero only when a registered bounded executor actually succeeds.

## Safety model

Default mode is read-only. Forge writes only under `--out`, and `--out` is blocked if it is inside the scanned Hermes home.

Forge does not:

- restart gateways;
- execute cron jobs;
- execute plugins;
- execute MCP servers;
- edit arbitrary skills, skill bodies or memory;
- send platform messages;
- push to GitHub;
- require network access.

Session, log, skill, task and report text is treated as untrusted data, never as instructions.

See [`docs/safety-model.md`](docs/safety-model.md).

## Examples

See [`examples/`](examples/) for source-checkout examples:

- minimal Hermes fixture;
- optional Kanban metadata;
- existing Doctor report import;
- `NO_CHANGE` proposal.

## Current status

Implemented:

- CLI: `doctor`, `capabilities`, `improve`, `experiment`, `diff-preview`, `scan`, `analyze`, `propose`, `eval`, `apply`, `rollback`;
- read-only evidence adapters;
- one-shot read-only improvement loop;
- opportunity reports with hypotheses, opportunity states, structured eval plans, success criteria and typed safe next steps;
- baseline comparison between read-only `improve` runs;
- safe `experiment` planner/results between opportunity and future diff-preview;
- preview-only `diff-preview` package with proposed file shapes, risk check, tests, rollback plan and candidate unified diff artifacts;
- gated apply with first bounded executor: `skill_frontmatter_metadata_v1` for approved `SKILL.md` frontmatter metadata only;
- first-class `NO_CHANGE` proposals;
- deterministic eval plans;
- actionable proposal templates with priority, review focus and next checks;
- privacy scanner;
- synthetic fixtures and tests;
- repository-quality GitHub Actions workflow.

Known limitations:

- session DB support is metadata-only and schema-limited;
- Kanban support is optional and metadata-only;
- log taxonomy is heuristic and category-only;
- eval output is a deterministic plan, not a benchmark runner;
- candidate diffs use virtual review paths until a concrete live target is approved;
- only one apply executor exists: `skill_frontmatter_metadata_v1`;
- arbitrary unified diffs, configs, cron, memory, runtime files and skill bodies are not executable targets;
- legacy proposal `apply` remains disabled in MVP.

## Русская версия

Hermes Forge - это локальный контур самоулучшения агента для Hermes Agent.

Он нужен, когда агентная система уже работает не как игрушка, а как рабочий инструмент: есть профили, skills, cron-задачи, логи, session history, иногда Kanban и отдельные doctor reports. В такой системе рано или поздно появляется вопрос: что улучшать, почему именно это, как проверить результат и где безопасная граница изменения.

Hermes Forge отвечает на этот вопрос через проверяемый цикл:

```text
наблюдения / evidence / opportunities / experiments / diff preview / apply gate
```

По умолчанию Forge работает read-only. Он читает только безопасные metadata и категории сигналов, собирает evidence ledger, группирует слабые места и готовит review-карточки. В карточке видно: что можно улучшить, какие evidence это подтверждают, какой experiment или eval нужен, что будет считаться успехом и какой следующий шаг безопасен.

## Что он умеет сейчас

- сканирует Hermes home и named profiles;
- смотрит skill frontmatter metadata;
- читает cron metadata без запуска jobs;
- считает категории в логах без raw log text;
- собирает session DB aggregate metadata;
- опционально учитывает Kanban SQLite aggregate metadata;
- опционально подтягивает summary из Doctor report;
- делает `improve --mode read-only` report;
- готовит experiment plan и diff-preview;
- показывает candidate diff только как review artifact;
- поддерживает один узкий apply executor: `skill_frontmatter_metadata_v1`.

## Для кого

- для пользователей Hermes Agent, у которых уже есть несколько профилей, skills, cron или runtime logs;
- для разработчиков, которые хотят улучшать agent workflow через evidence, а не через догадки;
- для команд, где перед изменением skills, routing или automation нужен review;
- для тех, кто хочет повторяемый improvement loop без скрытого self-editing.

## Что это не делает

Forge не переписывает агента сам. Он не перезапускает gateway, не запускает cron, plugins или MCP servers, не отправляет platform messages и не пушит изменения в GitHub. Session, log, skill, task и report text считаются untrusted data, а не инструкциями.

Apply сейчас ограничен одним executor. Он может менять только явно одобренные metadata-поля в `SKILL.md`: `description`, `tags`, `version`, `category`. Тело skill, memory, configs, cron, runtime files и arbitrary diffs не трогаются.

## Быстрый старт

```bash
git clone https://github.com/AlekseiUL/hermes-forge.git
cd hermes-forge
python -m pip install -e ".[dev]"
hermes-forge doctor
hermes-forge capabilities
```

Read-only запуск по локальному Hermes:

```bash
hermes-forge improve --mode read-only --hermes-home ~/.hermes --all-profiles --out ./forge-runs/latest
```

После запуска откройте:

```text
./forge-runs/latest/report.md
```

## Что получается на выходе

Forge создаёт набор локальных артефактов: `inventory.json`, `evidence-ledger.jsonl`, `findings.json`, `opportunities.json`, `proposals.json`, `report.md`, `redaction-report.json` и другие файлы для review. Эти артефакты по умолчанию считаются private local output. Перед публикацией их нужно проверять privacy scan.

## Public links / Полезные ссылки

- YouTube: https://youtube.com/@alekseiulianov
- Telegram channel - Sprut AI: https://t.me/Sprut_AI
- Telegram chat - Sprut AI: https://t.me/+eH-qNIDmud8zNDZi
- AI Операционка: https://t.me/tribute/app?startapp=sJyg

## Canonical source

This project is maintained by Aleksei Ulianov / Sprut_AI.
Original repository: https://github.com/AlekseiUL/hermes-forge

If you found this project mirrored, repackaged, or redistributed elsewhere, check this repository as the source of truth.

## Attribution

Where permitted by the applicable license, if you reuse, fork, modify, package, or publish this work, keep the original copyright and license notice and link back to the canonical repository.

## License

MIT. See [`LICENSE`](LICENSE).
