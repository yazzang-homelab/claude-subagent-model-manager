#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
subagent_tool.py — /subagent 스킬 엔진.

역할
- 현재 런처(claude / free-claude=fcc) 감지
- 메인 모델 + 파일 기반 커스텀 서브에이전트별 모델 + fcc 티어→백엔드 매핑 조회
- 안전 수정: 에이전트 frontmatter model / settings.json main model / ~/.fcc/.env 티어 매핑
- 모든 대상은 사용자 소유 경로 → claude/fcc 패키지 업데이트에도 생존
- 모든 수정 전 .bak 백업 (되돌리기 원칙)

외부 의존성 0 (표준 라이브러리만). fcc 패키지를 import 하지 않음(업데이트 내성).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

HOME = Path.home()
CWD = Path.cwd()

USER_CLAUDE = HOME / ".claude"
USER_AGENTS = USER_CLAUDE / "agents"
USER_SETTINGS = USER_CLAUDE / "settings.json"
PROJECT_CLAUDE = CWD / ".claude"
PROJECT_AGENTS = PROJECT_CLAUDE / "agents"
PROJECT_SETTINGS = PROJECT_CLAUDE / "settings.json"
FCC_ENV = HOME / ".fcc" / ".env"
FCC_ENV_LEGACY = HOME / ".config" / "free-claude-code" / ".env"

TIER_ALIASES = ("opus", "sonnet", "haiku", "fable", "inherit")
FCC_TIER_KEYS = {"opus": "MODEL_OPUS", "sonnet": "MODEL_SONNET",
                 "haiku": "MODEL_HAIKU", "fallback": "MODEL"}
# 하네스 내장 에이전트 — 파일이 아니므로 frontmatter 로 제어 불가.
BUILTIN_AGENTS = ["claude", "Explore", "Plan", "general-purpose",
                  "claude-code-guide", "statusline-setup"]


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _backup(path: Path) -> str | None:
    """수정 전 .bak 백업 생성. 심링크는 실제 내용을 복사."""
    if not path.exists():
        return None
    bak = path.with_name(path.name + f".bak-subagent-{_now_tag()}")
    shutil.copy2(path, bak)
    return str(bak)


# ---------------------------------------------------------------- 감지/조회

def detect_launcher() -> dict:
    """fcc 는 자식 claude 에 프록시 env 를 주입한다."""
    gw = os.environ.get("CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY")
    base = os.environ.get("ANTHROPIC_BASE_URL", "")
    is_fcc = gw == "1" or ("localhost" in base) or ("127.0.0.1" in base)
    return {
        "launcher": "fcc" if is_fcc else "claude",
        "anthropic_base_url": base or None,
        "gateway_discovery": gw,
    }


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_main_model() -> dict:
    proj = _read_json(PROJECT_SETTINGS).get("model") if PROJECT_SETTINGS.exists() else None
    user = _read_json(USER_SETTINGS).get("model") if USER_SETTINGS.exists() else None
    env = os.environ.get("ANTHROPIC_MODEL") or os.environ.get("CLAUDE_CODE_MODEL")
    # 유효 순서: 세션 env > project settings > user settings
    effective = env or proj or user
    return {
        "effective": effective,
        "session_env": env,
        "project_settings": proj,
        "user_settings": user,
    }


def _parse_frontmatter(text: str) -> tuple[dict, tuple[int, int] | None]:
    """--- ... --- 블록에서 최상위 key:value 추출. 반환 (dict, (start,end) 줄 인덱스)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, None
    fm: dict[str, str] = {}
    for ln in lines[1:end]:
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", ln)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm, (0, end)


def _agent_entry(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        text = ""
    fm, _ = _parse_frontmatter(text)
    return {
        "name": fm.get("name") or path.stem,
        "model": fm.get("model") or "inherit",
        "category": fm.get("category") or "uncategorized",
        "description": (fm.get("description") or "")[:120],
        "path": str(path),
        "is_symlink": path.is_symlink(),
        "symlink_target": os.path.realpath(path) if path.is_symlink() else None,
    }


def list_agents() -> dict:
    def scan(d: Path) -> list[dict]:
        if not d.is_dir():
            return []
        return [_agent_entry(p) for p in sorted(d.glob("*.md"))]

    scope_collapsed = USER_AGENTS.resolve() == PROJECT_AGENTS.resolve()
    return {
        "scope_collapsed": scope_collapsed,  # cwd 가 홈이면 user==project
        "user": scan(USER_AGENTS),
        "project": [] if scope_collapsed else scan(PROJECT_AGENTS),
    }


def _parse_env_line_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for ln in path.read_text(encoding="utf-8").splitlines():
        m = re.match(rf'^\s*{re.escape(key)}\s*=\s*(.*)$', ln)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def fcc_tier_map() -> dict:
    env = FCC_ENV if FCC_ENV.exists() else (FCC_ENV_LEGACY if FCC_ENV_LEGACY.exists() else None)
    if env is None:
        return {"env_path": None, "mapping": {}}
    return {
        "env_path": str(env),
        "mapping": {tier: _parse_env_line_value(env, key)
                    for tier, key in FCC_TIER_KEYS.items()},
    }


def show() -> dict:
    return {
        **detect_launcher(),
        "main_model": read_main_model(),
        "agents": list_agents(),
        "fcc": fcc_tier_map(),
        "builtin_agents": BUILTIN_AGENTS,
        "paths": {
            "user_agents": str(USER_AGENTS),
            "project_agents": str(PROJECT_AGENTS),
            "user_settings": str(USER_SETTINGS),
            "project_settings": str(PROJECT_SETTINGS),
            "fcc_env": str(FCC_ENV),
        },
    }


# ---------------------------------------------------------------- 표(사람용)

def table() -> str:
    d = show()
    L = []
    L.append(f"■ 런처: {d['launcher']}" + (f"  (base={d['anthropic_base_url']})" if d['anthropic_base_url'] else ""))
    mm = d["main_model"]
    L.append(f"■ 메인 모델(유효): {mm['effective']}   "
             f"[env={mm['session_env']} · proj={mm['project_settings']} · user={mm['user_settings']}]")
    if d["launcher"] == "fcc" and d["fcc"]["mapping"]:
        L.append("■ fcc 티어→백엔드 매핑 (" + str(d["fcc"]["env_path"]) + ")")
        for tier, v in d["fcc"]["mapping"].items():
            L.append(f"    {tier:8s} → {v}")
    L.append("")
    L.append("■ 파일 기반 서브에이전트 (frontmatter model 로 제어)")
    ag = d["agents"]
    if ag["scope_collapsed"]:
        L.append("  ⚠ 현재 작업 폴더가 홈(~)이라 전역=프로젝트 스코프가 동일 디렉터리입니다.")

    def emit(scope_name: str, items: list[dict]):
        if not items:
            return
        L.append(f"  [{scope_name}]")
        by_cat: dict[str, list[dict]] = {}
        for it in items:
            by_cat.setdefault(it["category"], []).append(it)
        for cat in sorted(by_cat):
            L.append(f"    · {cat}")
            for it in by_cat[cat]:
                flag = "  🔗symlink→공유" if it["is_symlink"] else ""
                L.append(f"        {it['name']:32s} {it['model']:10s}{flag}")

    emit("user (전역)", ag["user"])
    emit("project (프로젝트)", ag["project"])
    L.append("")
    L.append("■ 내장 에이전트(파일 아님 · frontmatter 불가): " + ", ".join(d["builtin_agents"]))
    L.append("    → 호출 시 model 파라미터 또는 CLAUDE_CODE_SUBAGENT_MODEL(전체 강제)로만 지정")
    return "\n".join(L)


# ---------------------------------------------------------------- 수정

def _write_model_frontmatter(path: Path, model: str) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    fm, span = _parse_frontmatter(text)
    if span is None:
        raise SystemExit(f"[err] frontmatter 없음: {path}")
    _, end = span
    # model 줄 교체 또는 name 뒤 삽입
    replaced = False
    for i in range(1, end):
        if re.match(r"^model:\s*", lines[i]):
            lines[i] = f"model: {model}"
            replaced = True
            break
    if not replaced:
        insert_at = 1
        for i in range(1, end):
            if re.match(r"^name:\s*", lines[i]):
                insert_at = i + 1
                break
        lines.insert(insert_at, f"model: {model}")
    trailing_nl = "\n" if text.endswith("\n") else ""
    path.write_text("\n".join(lines) + trailing_nl, encoding="utf-8")


def set_agent(name: str, model: str, scope: str, follow_symlink: bool) -> dict:
    if scope not in ("user", "project"):
        raise SystemExit("[err] scope 는 user|project")
    src_dir = USER_AGENTS if scope == "user" else PROJECT_AGENTS
    target = src_dir / f"{name}.md"

    # project 스코프인데 프로젝트에 없으면 전역본을 그림자 복사
    created_shadow = False
    if scope == "project" and not target.exists():
        user_src = USER_AGENTS / f"{name}.md"
        if not user_src.exists():
            raise SystemExit(f"[err] '{name}' 에이전트 파일을 전역/프로젝트 어디에도 못 찾음")
        PROJECT_AGENTS.mkdir(parents=True, exist_ok=True)
        shutil.copy2(os.path.realpath(user_src), target)  # 내용 복사(심링크 아님)
        created_shadow = True

    if not target.exists():
        raise SystemExit(f"[err] 파일 없음: {target}")

    if target.is_symlink() and not follow_symlink:
        real = os.path.realpath(target)
        raise SystemExit(
            f"[guard] '{name}' 은 심링크 → {real}\n"
            f"        수정하면 공유 원본이 바뀝니다. 정말이면 --follow-symlink,\n"
            f"        아니면 --scope project 로 프로젝트 그림자 사본을 만드세요.")

    bak = None if created_shadow else _backup(target)
    _write_model_frontmatter(target, model)
    return {"ok": True, "name": name, "model": model, "scope": scope,
            "path": str(target), "backup": bak, "created_shadow": created_shadow,
            "note": "frontmatter 는 다음 서브에이전트 스폰부터 즉시 반영(재시작 불필요)"}


def set_main(model: str, scope: str) -> dict:
    path = USER_SETTINGS if scope == "user" else PROJECT_SETTINGS
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_json(path) if path.exists() else {}
    bak = _backup(path)
    data["model"] = model
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True, "model": model, "scope": scope, "path": str(path), "backup": bak,
            "note": "현재 세션엔 즉시 반영 안 됨 → /model 로 전환하거나 재시작"}


def set_fcc_tier(tier: str, model: str) -> dict:
    if tier not in FCC_TIER_KEYS:
        raise SystemExit(f"[err] tier 는 {list(FCC_TIER_KEYS)} 중 하나")
    env = FCC_ENV if FCC_ENV.exists() else (FCC_ENV_LEGACY if FCC_ENV_LEGACY.exists() else None)
    if env is None:
        raise SystemExit(f"[err] fcc .env 없음 ({FCC_ENV}) — fcc-init 먼저 실행")
    key = FCC_TIER_KEYS[tier]
    bak = _backup(env)
    lines = env.read_text(encoding="utf-8").splitlines()
    done = False
    for i, ln in enumerate(lines):
        if re.match(rf'^\s*{re.escape(key)}\s*=', ln):
            lines[i] = f'{key}="{model}"'
            done = True
            break
    if not done:
        lines.append(f'{key}="{model}"')
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "tier": tier, "key": key, "model": model, "path": str(env),
            "backup": bak, "note": "fcc-server 재시작 후 반영(라우팅 프록시가 .env 재로딩해야 함)"}


# ---------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser(prog="subagent_tool")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("show", help="상태 JSON")
    sub.add_parser("table", help="상태 표(사람용)")

    p = sub.add_parser("set", help="에이전트 모델 지정")
    p.add_argument("--agent", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--scope", choices=["user", "project"], default="user")
    p.add_argument("--follow-symlink", action="store_true")

    p = sub.add_parser("set-main", help="메인 모델 지정")
    p.add_argument("--model", required=True)
    p.add_argument("--scope", choices=["user", "project"], default="user")

    p = sub.add_parser("set-fcc-tier", help="fcc 티어→백엔드 매핑")
    p.add_argument("--tier", required=True, choices=list(FCC_TIER_KEYS))
    p.add_argument("--model", required=True)

    a = ap.parse_args()
    if a.cmd == "show":
        print(json.dumps(show(), ensure_ascii=False, indent=2))
    elif a.cmd == "table":
        print(table())
    elif a.cmd == "set":
        print(json.dumps(set_agent(a.agent, a.model, a.scope, a.follow_symlink),
                         ensure_ascii=False, indent=2))
    elif a.cmd == "set-main":
        print(json.dumps(set_main(a.model, a.scope), ensure_ascii=False, indent=2))
    elif a.cmd == "set-fcc-tier":
        print(json.dumps(set_fcc_tier(a.tier, a.model), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
