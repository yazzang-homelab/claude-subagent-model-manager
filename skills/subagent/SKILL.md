---
name: subagent
description: 현재 메인 모델과 파일 기반 서브에이전트들의 모델을 카테고리별로 보여주고, 대화형으로 지정·저장하는 도구. 저장 범위는 전역(~/.claude) 또는 프로젝트(./.claude)를 선택. claude·free-claude(fcc) 양쪽 공통. "서브에이전트 모델", "subagent 모델 설정", "/subagent" 요청 시 사용.
---

# /subagent — 서브에이전트 모델 관리

## 목적
- 메인 모델 + 커스텀 서브에이전트별 모델(카테고리별)을 조회·지정·저장
- 저장 범위: **전역**(`~/.claude/agents`) 또는 **프로젝트**(`./.claude/agents`, 전역을 오버라이드)
- claude / fcc 공통 (fcc는 opus/sonnet/haiku 별칭을 백엔드로 라우팅)
- 전부 사용자 소유 경로 → claude·fcc 업데이트에도 생존

## 엔진
- `python3 ~/.claude/skills/subagent/subagent_tool.py <cmd>`
- 조회: `show`(JSON) · `table`(사람용)
- 수정: `set --agent N --model M --scope user|project [--follow-symlink]`
       · `set-main --model M --scope user|project`
       · `set-fcc-tier --tier opus|sonnet|haiku|fallback --model P/M`
- 모든 수정 = `.bak-subagent-<ts>` 백업 선행

## 웹 대시보드 (선택)
- `python3 ~/.claude/skills/subagent/dashboard.py` → Flask 앱. 기본 `127.0.0.1:8097`, `SUBAGENT_DASH_HOST=0.0.0.0`로 LAN 노출(신뢰된 내부망 전용).
- systemd 상주: `subagent-dashboard.service` (재부팅 생존, `MemoryMax=128M`).
- **모델 탭**: 메인 모델·에이전트별 모델·(fcc면) 티어 매핑을 드롭다운으로 지정. 저장 범위(전역/프로젝트), 심링크 가드 모달, 우상단 **한/영 전환** 버튼.
  - ⚠ 상주 서버는 '현재 폴더'가 없다 → **프로젝트 스코프는 폴더 경로 입력 필수**(엔진 `set`/`set-main`에 `--project-dir` 추가). 빈 경로면 API가 거부(루트 오기록 방지).
- **세션 탭**: `~/.claude/projects/*/*.jsonl`의 `ai-title`·`last-prompt`·`cwd`를 스캔해 `/resume`처럼 세션 제목·**실제 cwd(프로젝트)**·최근 활동·마지막 프롬프트를 나열(검색·ID 복사, 재개는 터미널 `claude --resume <id>`).
  - 각 행의 **⚙ 모델 설정** 버튼 → 모델 탭(전역)으로 이동. ⚠ Claude의 "프로젝트"=실행 cwd라, 거의 모든 세션이 `/root`(=전역 폴더)면 subagent 설정은 **전역(모든 세션 공통)** 이다. 배너로 명시.
- `subagent_tool.py`의 `show`/`set_agent`/`set_main`/`set_fcc_tier`를 그대로 재사용 → CLI와 동일 로직·동일 백업.
- ⚠ **API 키·자격증명은 노출/전송하지 않는다** — 모델명만 다룸(`show()`에 키 미포함). 세션 탭도 제목·프롬프트 메타만 읽음.

## 실행 절차 (이 순서로)

1. **상태 제시**
   - `subagent_tool.py table` 실행 → 결과를 사용자에게 그대로 보여준다.
   - 런처(claude/fcc), 메인 모델, 카테고리별 에이전트 모델, (fcc면) 티어→백엔드 매핑을 확인시킨다.

2. **무엇을 바꿀지 확인** — `AskUserQuestion`으로 물어본다.
   - 대상: 메인 모델 / 특정 카테고리·에이전트 / fcc 티어 매핑 중 무엇인지.
   - 새 모델 값: `opus` `sonnet` `haiku` `fable` `inherit` 또는 전체 ID.
   - 카테고리 단위 변경이면 그 카테고리에 속한 에이전트 전부에 동일 적용.

3. **저장 범위 선택** — `AskUserQuestion`으로 물어본다.
   - **전역(user)**: `~/.claude/agents/*.md` — 모든 프로젝트에 적용.
   - **프로젝트(project)**: `./.claude/agents/*.md` — 이 프로젝트만. 전역본을 그림자 복사해 오버라이드.
   - ⚠ `table`에 "전역=프로젝트 동일" 경고가 뜨면(작업 폴더가 홈) 두 범위가 같은 디렉터리임을 알린다.

4. **적용**
   - 각 대상마다 `set` / `set-main` / `set-fcc-tier` 호출.
   - **심링크 가드**: `set`이 `[guard]`로 거부하면 공유 원본임을 알리고, 사용자에게 (a) 프로젝트 그림자 사본(`--scope project`) 또는 (b) 공유 원본 수정(`--follow-symlink`) 중 선택하게 한다. 임의로 `--follow-symlink` 쓰지 말 것.
   - 결과의 `backup` 경로와 `note`(반영 시점)를 사용자에게 보고.

5. **반영 시점 안내**
   - 에이전트 frontmatter: 다음 스폰부터 즉시(재시작 불필요).
   - 메인 모델(settings.json): 현재 세션 미반영 → `/model`로 전환하거나 재시작.
   - fcc 티어 매핑(~/.fcc/.env): `fcc-server` 재시작 후 반영.

## 원칙
- 되돌리기: 모든 수정은 자동 `.bak`. 되돌리려면 해당 `.bak-subagent-*`를 원본명으로 복사.
- 내장 에이전트(claude/Explore/Plan/general-purpose 등)는 파일이 아니라 frontmatter로 못 바꾼다 → 호출 시 model 파라미터 또는 `CLAUDE_CODE_SUBAGENT_MODEL`(전체 강제)로만. 이 한계를 사용자에게 명시.
- 카테고리 = 에이전트 frontmatter의 `category:` 필드(없으면 `uncategorized`). 카테고리를 새로 나누려면 각 에이전트에 `category:` 추가를 제안.
