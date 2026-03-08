from __future__ import annotations

import json
import sqlite3
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


def test_add_server_and_enable_across_multiple_clusters(
    runner, temp_db: Path, resources_dir: Path
) -> None:
    config_file = _config_file(temp_db, resources_dir)

    create_cluster = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "clusters",
            "create",
            "Testing",
            "--app",
            "Codex",
        ],
    )
    assert create_cluster.exit_code == 0, create_cluster.output

    add_server = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "servers",
            "add",
            "Local Dev Server",
            "--command",
            "python3",
            "--arg",
            "-m",
            "--arg",
            "my_local_server",
            "--env",
            "DEBUG=true",
        ],
    )
    assert add_server.exit_code == 0, add_server.output

    show_server = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "servers",
            "show",
            "Local Dev Server",
        ],
    )
    assert show_server.exit_code == 0, show_server.output
    server_payload = json.loads(show_server.stdout)
    server_id = server_payload["server_id"]

    enable_many = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "servers",
            "enable-many",
            "Local Dev Server",
            "--target",
            "Codex::Cluster A",
            "--target",
            "Codex::Testing",
        ],
    )
    assert enable_many.exit_code == 0, enable_many.output
    assert "2 target cluster(s)" in enable_many.output

    default_cluster = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "clusters",
            "show",
            "Cluster A",
            "--app",
            "Codex",
        ],
    )
    testing_cluster = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "clusters",
            "show",
            "Testing",
            "--app",
            "Codex",
        ],
    )
    assert default_cluster.exit_code == 0, default_cluster.output
    assert testing_cluster.exit_code == 0, testing_cluster.output
    default_payload = json.loads(default_cluster.stdout)
    testing_payload = json.loads(testing_cluster.stdout)
    assert server_id in default_payload["enabled_server_ids"]
    assert server_id in testing_payload["enabled_server_ids"]


def test_sync_custom_app_handles_text_json_fields_and_writes_servers(
    runner, temp_db: Path, resources_dir: Path
) -> None:
    config_file = _config_file(temp_db, resources_dir)
    antigravity_config = temp_db.parent / "mcp.json"

    add_app = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "apps",
            "add-custom",
            "Antigravity",
            str(antigravity_config),
            "--config-key",
            "servers",
        ],
    )
    assert add_app.exit_code == 0, add_app.output

    add_server = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "servers",
            "add",
            "Local Dev Server",
            "--command",
            "python3",
            "--arg",
            "-m",
            "--arg",
            "my_local_server",
            "--env",
            "DEBUG=true",
            "--parameter",
            "scope=test",
        ],
    )
    assert add_server.exit_code == 0, add_server.output

    show_server = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "servers",
            "show",
            "Local Dev Server",
        ],
    )
    assert show_server.exit_code == 0, show_server.output
    server_payload = json.loads(show_server.stdout)
    server_id = server_payload["server_id"]

    enable_server = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "servers",
            "enable",
            "Local Dev Server",
            "--app",
            "Antigravity",
            "--cluster",
            "Cluster A",
        ],
    )
    assert enable_server.exit_code == 0, enable_server.output

    with sqlite3.connect(temp_db) as connection:
        connection.execute(
            """
            UPDATE ZADDEDSERVER
            SET ZARGS=?, ZENV=?, ZPARAMETERS=?
            WHERE ZID=?
            """,
            ('["-m", "my_local_server"]', '{"DEBUG": "true"}', '{"scope": "test"}', server_id),
        )
        connection.commit()

    sync_result = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "sync",
            "app",
            "Antigravity",
        ],
    )
    assert sync_result.exit_code == 0, sync_result.output
    normalized_output = sync_result.output.replace("\n", "")
    assert "Synced Antigravity -> " in normalized_output
    assert str(antigravity_config) in normalized_output

    output_payload = json.loads(antigravity_config.read_text(encoding="utf-8"))
    assert output_payload["servers"]
    assert output_payload["servers"][f"Local_Dev_Server_id_{server_id}"]["command"] == "python3"
    assert output_payload["servers"][f"Local_Dev_Server_id_{server_id}"]["args"] == [
        "-m",
        "my_local_server",
    ]
    assert output_payload["servers"][f"Local_Dev_Server_id_{server_id}"]["env"] == {"DEBUG": "true"}


def _config_file(temp_db: Path, resources_dir: Path) -> Path:
    config_path = temp_db.parent / "config.toml"
    config_path.write_text(
        f'db_path = "{temp_db}"\nresources_dir = "{resources_dir}"\nbackup_on_write = false\n',
        encoding="utf-8",
    )
    return config_path
