# claude-subagent-model-manager

> Interactive, per-category model manager for **Claude Code** subagents — works with both stock Claude Code and [free-claude-code](https://github.com/) (`fcc`). Choose models per agent/category, save **globally** or **per-project**, backup-first.

한국어 README: [README.ko.md](README.ko.md)

---

## Why this exists

Claude Code lets each file-based subagent declare a model in its frontmatter (`model: opus|sonnet|haiku|fable|inherit`). That is enough for *static* per-agent assignment, but two things are **not** supported natively:

- **Conditional mapping** — e.g. "when the main model is Opus, run subagents on Sonnet; when the main model is a cheap tier, run subagents on Opus." No native mechanism reads the active main model and branches.
- **Per-session, per-category overrides** — the only session-level knob is `CLAUDE_CODE_SUBAGENT_MODEL`, which forces **all** subagents to one model (no per-category granularity).

This skill gives you the practical equivalent: a single `/subagent` command that shows the current main model + every file-based subagent's model grouped by category, then lets you set them and persist the change at the scope you choose — **global** (`~/.claude/agents`) or **project** (`./.claude/agents`, which overrides global).

## What it manages

| Target | Mechanism | Honored by |
|---|---|---|
| Per-category / per-agent subagent model | `model:` frontmatter in `*.md` agent files | Claude Code natively (priority 3) |
| Main model | `model` in `settings.json` | Claude Code (session needs `/model` or restart) |
| `fcc` tier → backend mapping | `MODEL_OPUS/SONNET/HAIKU/MODEL` in `~/.fcc/.env` | fcc routing proxy (needs `fcc-server` restart) |

Everything lives under **user-owned paths** (`~/.claude`, `~/.fcc/.env`), so it survives both Claude Code and fcc package updates.

## How it works with `fcc` (free-claude-code)

`fcc` launches the *real* `claude` binary with proxy environment variables injected — it does **not** fork the config. So `~/.claude/skills` and `~/.claude/agents` are shared, and this one skill covers both launchers.

`fcc` also reuses Claude's `opus` / `sonnet` / `haiku` aliases as **routing keys**. A subagent set to `model: haiku` routes to whatever `MODEL_HAIKU` points at in `~/.fcc/.env` (which may be any non-Anthropic backend). So:

- The **tier layer** (`opus`/`sonnet`/`haiku`/`fable`) is the shared control surface for both launchers.
- Under `fcc`, `set-fcc-tier` lets you re-point what each tier *actually* runs on (e.g. `haiku → your-provider/some-cheap-model`).

Launcher detection marker: `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` (+ a localhost `ANTHROPIC_BASE_URL`) means the session is under `fcc`.

## Install

```bash
git clone https://github.com/yazzang-homelab/claude-subagent-model-manager.git
mkdir -p ~/.claude/skills/subagent
cp claude-subagent-model-manager/skills/subagent/* ~/.claude/skills/subagent/
```

Claude Code auto-discovers skills in `~/.claude/skills/`. Restart Claude Code (or start a new session) and the `/subagent` skill is available.

## Usage

### Interactive (recommended)

Type `/subagent`. The skill will:

1. **Show state** — launcher, main model, per-category subagent models, and (under `fcc`) the tier→backend mapping.
2. **Ask what to change** — a specific agent, a whole category, the main model, or an `fcc` tier.
3. **Ask the save scope** — global or project.
4. **Apply** — with an automatic `.bak-subagent-<timestamp>` backup, then report where the backup is and when the change takes effect.

### Direct CLI

The engine is a dependency-free Python CLI you can also call directly:

```bash
TOOL=~/.claude/skills/subagent/subagent_tool.py

python3 $TOOL show            # full state as JSON
python3 $TOOL table           # human-readable table

# set one agent's model (global)
python3 $TOOL set --agent codebase-locator --model haiku --scope user

# set one agent for THIS project only (creates a shadow copy under ./.claude/agents)
python3 $TOOL set --agent codebase-analyzer --model sonnet --scope project

# set the main model
python3 $TOOL set-main --model opus --scope user

# (fcc only) re-point a tier to a different backend
python3 $TOOL set-fcc-tier --tier haiku --model your-provider/some-cheap-model
```

### Web dashboard

A small Flask dashboard reuses the same engine functions (`show` / `set_agent` / `set_main` / `set_fcc_tier`) — identical logic, identical backup-first behavior — behind a browser UI with dropdowns, scope selector, a symlink-guard prompt, and a **KO/EN language toggle**.

```bash
python3 ~/.claude/skills/subagent/dashboard.py     # serves on 0.0.0.0:8097
```

Run it persistently via systemd — an example unit is included:

```bash
cp skills/subagent/subagent-dashboard.service.example /etc/systemd/system/subagent-dashboard.service
systemctl daemon-reload && systemctl enable --now subagent-dashboard.service
```

> **Secrets stay out.** The dashboard only ever moves model *names*; `show()` never includes API keys, and the page transmits nothing else. Bind it to a trusted LAN / localhost only — the write endpoint has no auth by design (it edits local user-owned files).

## Scopes

- **Global (`user`)** → `~/.claude/agents/*.md`. Applies to every project.
- **Project (`project`)** → `./.claude/agents/*.md`. Applies only to the current project and **overrides** the global agent of the same name. If the agent only exists globally, a **shadow copy** is created in the project dir and edited there — your global file is untouched.

> If your current working directory is your home directory, global and project resolve to the **same** folder; the tool prints a warning when this happens.

## Safety

- **Backup-first** — every mutation writes a `.bak-subagent-<timestamp>` next to the file before editing. To revert, copy the backup back over the original.
- **Symlink guard** — if an agent file is a symlink (e.g. shared from another repo), `set` refuses by default and prints the real target. You then choose: create a project shadow copy (`--scope project`) or explicitly edit the shared original (`--follow-symlink`).
- **No secrets touched** — the tool reads paths and model names only; it never prints or transmits API keys. `~/.fcc/.env` values other than the model-tier keys are left alone.

## Limitations

- **Built-in agents** (`claude`, `Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `statusline-setup`) are provided by the harness, not files — you cannot set their model via frontmatter. Use a per-invocation `model` parameter or `CLAUDE_CODE_SUBAGENT_MODEL` (all-or-one) instead.
- **Main model** changes in `settings.json` don't hot-apply to the current session; use `/model` or restart.
- **`fcc` tier** changes need a `fcc-server` restart so the routing proxy reloads `~/.fcc/.env`.
- **Categories** come from an optional `category:` field in each agent's frontmatter (falls back to `uncategorized`). Add `category:` to your agent files to group them.

## Repo layout

```
skills/subagent/
├── SKILL.md                              # /subagent skill definition + step-by-step flow
├── subagent_tool.py                      # engine: show / table / set / set-main / set-fcc-tier
├── dashboard.py                          # optional Flask web UI (KO/EN toggle) reusing the engine
└── subagent-dashboard.service.example    # systemd unit for persistent hosting
```

## License

MIT — see [LICENSE](LICENSE).
