# claude-subagent-model-manager

> **Claude Code** 서브에이전트 모델을 **카테고리별로** 대화형 관리하는 도구. 기본 Claude Code와 [free-claude-code](https://github.com/)(`fcc`) 양쪽에서 동작하며, **전역** 또는 **프로젝트** 범위로 저장하고, 모든 수정은 백업이 선행됩니다.

English README: [README.md](README.md)

---

## 왜 만들었나

Claude Code는 파일 기반 서브에이전트마다 frontmatter로 모델을 선언할 수 있습니다(`model: opus|sonnet|haiku|fable|inherit`). *정적* 지정에는 충분하지만, 다음 두 가지는 **네이티브로 지원되지 않습니다**:

- **조건부 매핑** — 예: "메인이 Opus일 땐 서브를 Sonnet으로, 메인이 저가 티어일 땐 서브를 Opus로." 활성 메인 모델을 읽어 분기하는 메커니즘이 없습니다.
- **세션 단위 카테고리별 오버라이드** — 세션 레벨 노브는 `CLAUDE_CODE_SUBAGENT_MODEL` 하나뿐이고, 이건 **모든** 서브에이전트를 한 모델로 강제(카테고리 구분 불가)합니다.

이 스킬은 실용적 대안을 제공합니다: `/subagent` 하나로 현재 메인 모델 + 파일 기반 서브에이전트 모델을 카테고리별로 보여주고, 원하는 값으로 지정한 뒤 **전역**(`~/.claude/agents`) 또는 **프로젝트**(`./.claude/agents`, 전역을 오버라이드) 범위로 영속시킵니다.

## 무엇을 관리하나

| 대상 | 메커니즘 | 존중 주체 |
|---|---|---|
| 카테고리·에이전트별 서브 모델 | `*.md` 에이전트 파일의 `model:` frontmatter | Claude Code 네이티브(우선순위 3) |
| 메인 모델 | `settings.json`의 `model` | Claude Code(세션엔 `/model` 또는 재시작 필요) |
| `fcc` 티어→백엔드 매핑 | `~/.fcc/.env`의 `MODEL_OPUS/SONNET/HAIKU/MODEL` | fcc 라우팅 프록시(`fcc-server` 재시작 필요) |

모든 대상이 **사용자 소유 경로**(`~/.claude`, `~/.fcc/.env`)에 있어 Claude Code·fcc 패키지 업데이트에도 살아남습니다.

## `fcc`(free-claude-code)와의 동작

`fcc`는 진짜 `claude` 바이너리를 프록시 환경변수만 주입해 실행합니다 — 설정을 분기하지 않습니다. 따라서 `~/.claude/skills`와 `~/.claude/agents`를 공유하며, **스킬 하나로 양쪽 런처를 모두 커버**합니다.

`fcc`는 또한 Claude의 `opus`/`sonnet`/`haiku` 별칭을 **라우팅 키**로 재사용합니다. `model: haiku`인 서브에이전트는 `~/.fcc/.env`의 `MODEL_HAIKU`가 가리키는 백엔드(비-Anthropic 포함)로 라우팅됩니다. 그래서:

- **티어 레이어**(`opus`/`sonnet`/`haiku`/`fable`)가 양쪽 공통 제어면입니다.
- `fcc`에선 `set-fcc-tier`로 각 티어가 *실제* 무엇으로 도는지 재지정할 수 있습니다(예: `haiku → 내-프로바이더/저가-모델`).

런처 감지 마커: `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1`(+ localhost `ANTHROPIC_BASE_URL`)이면 세션이 `fcc` 하에 있습니다.

## 설치

```bash
git clone https://github.com/yazzang-homelab/claude-subagent-model-manager.git
mkdir -p ~/.claude/skills/subagent
cp claude-subagent-model-manager/skills/subagent/* ~/.claude/skills/subagent/
```

Claude Code는 `~/.claude/skills/`의 스킬을 자동 인식합니다. 재시작(또는 새 세션)하면 `/subagent`를 쓸 수 있습니다.

## 사용법

### 대화형 (권장)

`/subagent`를 입력하면 스킬이:

1. **상태 표시** — 런처, 메인 모델, 카테고리별 서브 모델, (`fcc`면) 티어→백엔드 매핑.
2. **변경 대상 질문** — 특정 에이전트 / 카테고리 전체 / 메인 모델 / `fcc` 티어.
3. **저장 범위 질문** — 전역 / 프로젝트.
4. **적용** — `.bak-subagent-<타임스탬프>` 자동 백업 후, 백업 위치와 반영 시점을 보고.

### 직접 CLI

엔진은 의존성 없는 Python CLI라 직접 호출도 가능합니다:

```bash
TOOL=~/.claude/skills/subagent/subagent_tool.py

python3 $TOOL show            # 전체 상태 JSON
python3 $TOOL table           # 사람용 표

# 특정 에이전트 모델 지정 (전역)
python3 $TOOL set --agent codebase-locator --model haiku --scope user

# 이 프로젝트만 지정 (./.claude/agents에 그림자 사본 생성)
python3 $TOOL set --agent codebase-analyzer --model sonnet --scope project

# 메인 모델 지정
python3 $TOOL set-main --model opus --scope user

# (fcc 전용) 티어를 다른 백엔드로 재지정
python3 $TOOL set-fcc-tier --tier haiku --model 내-프로바이더/저가-모델
```

## 저장 범위

- **전역(`user`)** → `~/.claude/agents/*.md`. 모든 프로젝트에 적용.
- **프로젝트(`project`)** → `./.claude/agents/*.md`. 이 프로젝트만 적용하며 같은 이름의 전역 에이전트를 **오버라이드**. 전역에만 있는 에이전트면 프로젝트 폴더에 **그림자 사본**을 만들어 거기만 수정 → 전역 파일은 그대로.

> 현재 작업 폴더가 홈 디렉터리면 전역=프로젝트가 **같은 폴더**로 해석됩니다. 이 경우 도구가 경고를 출력합니다.

## 안전장치

- **백업 선행** — 모든 수정 전 `.bak-subagent-<타임스탬프>`를 옆에 생성. 되돌리려면 백업을 원본명으로 복사.
- **심링크 가드** — 에이전트 파일이 심링크(예: 다른 repo에서 공유)면 `set`이 기본 거부하고 실제 대상 경로를 출력. 이후 프로젝트 그림자 사본(`--scope project`) 또는 공유 원본 직접 수정(`--follow-symlink`) 중 선택.
- **시크릿 무접촉** — 경로와 모델명만 읽으며, API 키를 출력·전송하지 않음. `~/.fcc/.env`의 모델 티어 키 외 값은 건드리지 않음.

## 한계

- **내장 에이전트**(`claude`, `Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `statusline-setup`)는 파일이 아니라 하네스 제공 → frontmatter로 모델 지정 불가. 호출 시 `model` 파라미터 또는 `CLAUDE_CODE_SUBAGENT_MODEL`(전체 강제)로만.
- **메인 모델** `settings.json` 변경은 현재 세션에 즉시 반영되지 않음 → `/model` 또는 재시작.
- **`fcc` 티어** 변경은 라우팅 프록시가 `~/.fcc/.env`를 다시 읽도록 `fcc-server` 재시작 필요.
- **카테고리**는 각 에이전트 frontmatter의 선택적 `category:` 필드에서 옴(없으면 `uncategorized`). 그룹핑하려면 에이전트 파일에 `category:`를 추가.

## 저장소 구성

```
skills/subagent/
├── SKILL.md            # /subagent 스킬 정의 + 단계별 흐름
└── subagent_tool.py    # 엔진: show / table / set / set-main / set-fcc-tier
```

## 라이선스

MIT — [LICENSE](LICENSE) 참조.
