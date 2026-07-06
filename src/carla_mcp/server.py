"""carla-mcp MCP server.

Skills-first design: capabilities live in ``skills/<name>/`` as a ``SKILL.md``
plus executable steps. This server exposes the skill registry over MCP so an
agent can discover skills, read their procedure, and run their read-only
preflight. Mutating build steps are intentionally NOT auto-run here — building
CARLA is a long, sudo-touching, ~120GB operation; the server surfaces the
procedure and preflight, and the agent/user drives execution deliberately.

Run:  carla-mcp   (stdio transport)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Repo root = three levels up from this file (src/carla_mcp/server.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

mcp = FastMCP("carla-mcp")


def _skill_dirs() -> list[Path]:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(p for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())


@mcp.tool()
def list_skills() -> list[dict]:
    """List available CARLA skills with their one-line description.

    Returns one entry per ``skills/<name>/SKILL.md`` found in the repo.
    """
    out: list[dict] = []
    for d in _skill_dirs():
        desc = ""
        for line in (d / "SKILL.md").read_text().splitlines():
            if line.startswith("description:"):
                desc = line.split(":", 1)[1].strip()
                break
        out.append({"name": d.name, "description": desc})
    return out


@mcp.tool()
def read_skill(name: str) -> str:
    """Return the full SKILL.md (procedure + gotchas) for the named skill."""
    skill = SKILLS_DIR / name / "SKILL.md"
    if not skill.is_file():
        raise ValueError(f"unknown skill {name!r}; see list_skills()")
    return skill.read_text()


@mcp.tool()
def skill_preflight(name: str) -> str:
    """Run a skill's read-only preflight (steps/00_check_env.sh) and return its report.

    Read-only: checks OS, disk, tools, and whether UE4/CARLA/conda are ready.
    Does not modify the system.
    """
    script = SKILLS_DIR / name / "steps" / "00_check_env.sh"
    if not script.is_file():
        raise ValueError(f"skill {name!r} has no preflight (steps/00_check_env.sh)")
    proc = subprocess.run(
        ["bash", str(script)],
        capture_output=True, text=True, timeout=120,
    )
    return f"exit={proc.returncode}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"


def main() -> None:
    """Console-script entrypoint: serve over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
