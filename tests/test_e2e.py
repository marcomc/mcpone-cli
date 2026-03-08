from __future__ import annotations

from pathlib import Path

from mcpone_cli.cli import app


def test_market_install_and_sync_to_codex(runner, temp_db: Path, resources_dir: Path) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            str(_config_file(temp_db, resources_dir)),
            "market",
            "install",
            "Context7",
            "--app",
            "Codex",
            "--cluster",
            "Cluster A",
            "--param",
            "CONTEXT7_API_KEY=test-key",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Installed Context7" in result.output

    sync_result = runner.invoke(
        app, ["--config", str(_config_file(temp_db, resources_dir)), "sync", "app", "Codex"]
    )
    assert sync_result.exit_code == 0, sync_result.output

    codex_config = (temp_db.parent / "codex.toml").read_text(encoding="utf-8")
    assert "Context7_id_" in codex_config
    assert "--api-key" in codex_config
    assert "test-key" in codex_config


def test_import_file_into_mcpone(runner, temp_db: Path, resources_dir: Path) -> None:
    claude_config = temp_db.parent / "claude.json"
    claude_config.write_text(
        """
        {
          "mcpServers": {
            "GitHub[id=PX649D]": {
              "command": "docker",
              "args": ["run", "-i", "--rm", "ghcr.io/github/github-mcp-server:latest"]
            }
          }
        }
        """,
        encoding="utf-8",
    )

    add_app = runner.invoke(
        app,
        [
            "--config",
            str(_config_file(temp_db, resources_dir)),
            "apps",
            "add-custom",
            "Claude CLI",
            str(claude_config),
            "--config-key",
            "mcpServers",
        ],
    )
    assert add_app.exit_code == 0, add_app.output

    imported = runner.invoke(
        app,
        [
            "--config",
            str(_config_file(temp_db, resources_dir)),
            "import",
            "app",
            "Claude CLI",
        ],
    )
    assert imported.exit_code == 0, imported.output
    assert "Imported 1 server" in imported.output

    server_list = runner.invoke(
        app,
        ["--config", str(_config_file(temp_db, resources_dir)), "servers", "list"],
    )
    assert server_list.exit_code == 0, server_list.output
    assert "GitHub" in server_list.output


def _config_file(temp_db: Path, resources_dir: Path) -> Path:
    config_path = temp_db.parent / "config.toml"
    config_path.write_text(
        f'db_path = "{temp_db}"\nresources_dir = "{resources_dir}"\nbackup_on_write = false\n',
        encoding="utf-8",
    )
    return config_path
