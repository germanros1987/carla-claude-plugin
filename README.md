# carla-claude-plugin

A **Claude Code plugin** that teaches Claude to build [CARLA](https://carla.org)
(UE4.26) from source, drive the CarlaUE4 editor headlessly via Python, and author
new **drivable** vehicles end-to-end.

It bundles three skills plus a small MCP server that exposes the skill registry.

| Skill | What it does |
|-------|--------------|
| `build-carla-ue4-linux` | Build CARLA `ue4-dev` (UE 4.26) from source on Linux, incl. Ubuntu 24.04 — headless server + Python client wheel. |
| `ue4-editor-python` | Drive the CarlaUE4 project headless via UE4 editor Python (blueprints, assets, maps) — no GUI. |
| `add-carla-vehicle` | Automate CARLA's "add a vehicle" tutorial headless: author, wire and register a 4-wheeled vehicle that spawns **and drives** under the Traffic Manager. |

## Install

The marketplace is this repo; install with two commands.

**From GitHub:**

```bash
claude plugin marketplace add <owner>/carla-claude-plugin
claude plugin install carla-mcp@carla
```

**From a local clone:**

```bash
git clone <url> carla-claude-plugin
claude plugin marketplace add ./carla-claude-plugin
claude plugin install carla-mcp@carla
```

Or interactively: `/plugin marketplace add <path-or-repo>` then `/plugin`.
Installing the bundled MCP server asks for a one-time trust confirmation.

## Requirements

- **Claude Code**.
- The build / editor / vehicle skills operate on a **CARLA + UE4 checkout**. They
  default to `carla/` and `UnrealEngine_4.26/` next to the skills, but every path
  is overridable — point them at your checkout via `CARLA_UE4_ROOT`, `UE4_ROOT`,
  `CARLA_CONDA_ENV` (see [`skills/build-carla-ue4-linux/env.sh`](skills/build-carla-ue4-linux/env.sh)).
- `add-carla-vehicle` needs a CARLA build that includes `UVehicleAuthoringLibrary`
  (CarlaTools) — see [carla-simulator/carla#9805](https://github.com/carla-simulator/carla/pull/9805).
- The MCP server needs the `mcp` Python package on the `python3` it runs with:
  `pip install mcp` (or `pip install .` here for the `carla-mcp` console script).

## MCP server

Registered by [`.mcp.json`](.mcp.json) as `carla`, run as
`python3 -m carla_mcp.server` (stdio). Tools: `list_skills`, `read_skill`,
`skill_preflight`.

## License

MIT — see [LICENSE](LICENSE).
