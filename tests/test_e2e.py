from __future__ import annotations

import json
import sqlite3
import tomllib
from pathlib import Path

import pytest

from mcpone_cli.cli import app
from mcpone_cli.store import encode_blob


def test_version_flag_outputs_package_version(runner) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "0.1.0"


def test_json_version_and_help_outputs_are_machine_readable(runner) -> None:
    version_result = runner.invoke(app, ["--json", "--version"])
    assert version_result.exit_code == 0, version_result.output
    assert json.loads(version_result.stdout) == {"version": "0.1.0"}

    root_help = runner.invoke(app, ["--json"])
    assert root_help.exit_code == 0, root_help.output
    root_payload = json.loads(root_help.stdout)
    assert root_payload["group"] == "mcpone-cli"
    assert any(command["name"] == "apps" for command in root_payload["commands"])

    group_help = runner.invoke(app, ["--json", "servers"])
    assert group_help.exit_code == 0, group_help.output
    group_payload = json.loads(group_help.stdout)
    assert group_payload["group"] == "servers"
    assert any(command["name"] == "list" for command in group_payload["commands"])


@pytest.mark.parametrize("group_name", ["apps", "clusters", "servers", "market", "sync", "import"])
def test_command_groups_show_help_without_subcommand(runner, group_name: str) -> None:
    result = runner.invoke(app, [group_name])
    assert "Usage:" in result.stdout
    assert "Missing command." not in result.stdout


@pytest.mark.parametrize(
    "command_path",
    [
        ["apps", "show"],
        ["apps", "add-custom"],
        ["apps", "set-active-cluster"],
        ["clusters", "show"],
        ["clusters", "create"],
        ["clusters", "rename"],
        ["clusters", "delete"],
        ["servers", "show"],
        ["servers", "add"],
        ["servers", "update"],
        ["servers", "delete"],
        ["servers", "enable"],
        ["servers", "enable-many"],
        ["servers", "disable"],
        ["market", "show"],
        ["market", "install"],
        ["sync", "app"],
        ["import", "app"],
        ["import", "file"],
    ],
)
def test_commands_show_help_without_required_args(runner, command_path: list[str]) -> None:
    result = runner.invoke(app, command_path)
    assert "Usage:" in result.stdout
    assert "Missing argument" not in result.stdout
    assert "Missing command." not in result.stdout


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

    _add_custom_app(
        runner, _config_file(temp_db, resources_dir), "Claude CLI", claude_config, "mcpServers"
    )

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

    server_id = _add_server(
        runner,
        config_file,
        "Local Dev Server",
        command="python3",
        args=["-m", "my_local_server"],
        env={"DEBUG": "true"},
    )

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

    default_payload = _invoke_json(
        runner,
        config_file,
        ["clusters", "show", "Cluster A", "--app", "Codex"],
    )
    testing_payload = _invoke_json(
        runner,
        config_file,
        ["clusters", "show", "Testing", "--app", "Codex"],
    )
    assert server_id in default_payload["enabled_server_ids"]
    assert server_id in testing_payload["enabled_server_ids"]


def test_clusters_list_shows_app_name_and_sorts_by_app(
    runner, temp_db: Path, resources_dir: Path
) -> None:
    config_file = _config_file(temp_db, resources_dir)
    other_config = temp_db.parent / "other.json"

    _add_custom_app(runner, config_file, "Alpha App", other_config, "mcpServers")

    create_cluster = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "clusters",
            "create",
            "Zeta",
            "--app",
            "Alpha App",
        ],
    )
    assert create_cluster.exit_code == 0, create_cluster.output

    list_result = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "clusters",
            "list",
        ],
    )
    assert list_result.exit_code == 0, list_result.output
    assert "App PK" not in list_result.output
    assert "Cluster ID" not in list_result.output
    assert "Alpha App" in list_result.output
    assert "Codex" in list_result.output
    assert list_result.output.index("Alpha App") < list_result.output.index("Codex")


def test_human_outputs_prefer_app_and_cluster_names_while_json_keeps_ids(
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
    assert "Created cluster Testing for Codex" in create_cluster.output

    set_active = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "apps",
            "set-active-cluster",
            "Codex",
            "Testing",
        ],
    )
    assert set_active.exit_code == 0, set_active.output
    assert "active cluster -> Testing" in set_active.output
    assert "CLUSTERA" not in set_active.output

    apps_list_result = runner.invoke(
        app,
        ["--config", str(config_file), "apps", "list"],
    )
    assert apps_list_result.exit_code == 0, apps_list_result.output
    assert "App ID" not in apps_list_result.output
    assert "Testing" in apps_list_result.output
    assert "APP1" not in apps_list_result.output

    app_show_result = runner.invoke(
        app,
        ["--config", str(config_file), "apps", "show", "Codex"],
    )
    assert app_show_result.exit_code == 0, app_show_result.output
    assert "Active Cluster" in app_show_result.output
    assert "Testing" in app_show_result.output
    assert "APP1" not in app_show_result.output

    cluster_show_result = runner.invoke(
        app,
        ["--config", str(config_file), "clusters", "show", "Testing", "--app", "Codex"],
    )
    assert cluster_show_result.exit_code == 0, cluster_show_result.output
    assert "App" in cluster_show_result.output
    assert "Codex" in cluster_show_result.output
    assert "CLUSTERA" not in cluster_show_result.output

    json_apps = _invoke_json(runner, config_file, ["apps", "list"])
    assert json_apps["apps"][0]["app_id"] == "APP1"

    json_clusters = _invoke_json(runner, config_file, ["clusters", "list"])
    assert json_clusters["clusters"][0]["cluster_id"]


def test_human_outputs_prefer_server_and_market_names_while_json_keeps_ids(
    runner, temp_db: Path, resources_dir: Path
) -> None:
    config_file = _config_file(temp_db, resources_dir)

    add_server_result = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "servers",
            "add",
            "Context7",
            "--command",
            "npx",
            "--arg",
            "-y",
            "--arg",
            "@upstash/context7-mcp@latest",
        ],
    )
    assert add_server_result.exit_code == 0, add_server_result.output
    assert "Added server Context7" in add_server_result.output
    assert "(" not in add_server_result.output
    server_id = _invoke_json(runner, config_file, ["servers", "show", "Context7"])["server_id"]

    servers_list_result = runner.invoke(
        app,
        ["--config", str(config_file), "servers", "list"],
    )
    assert servers_list_result.exit_code == 0, servers_list_result.output
    assert " ID " not in servers_list_result.output
    assert "Context7" in servers_list_result.output

    server_show_result = runner.invoke(
        app,
        ["--config", str(config_file), "servers", "show", "Context7"],
    )
    assert server_show_result.exit_code == 0, server_show_result.output
    assert "Field" in server_show_result.output
    assert server_id not in server_show_result.output

    update_server_result = runner.invoke(
        app,
        ["--config", str(config_file), "servers", "update", "Context7", "--source", "custom"],
    )
    assert update_server_result.exit_code == 0, update_server_result.output
    assert "Updated server Context7" in update_server_result.output
    assert "(" not in update_server_result.output

    market_show_result = runner.invoke(
        app,
        ["--config", str(config_file), "market", "show", "Context7"],
    )
    assert market_show_result.exit_code == 0, market_show_result.output
    assert "Catalog ID" not in market_show_result.output
    assert "Context7" in market_show_result.output

    install_result = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
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
    assert install_result.exit_code == 0, install_result.output
    assert "Installed Context7 into Codex/Cluster A" in install_result.output
    assert "(" not in install_result.output

    json_servers = _invoke_json(runner, config_file, ["servers", "list"])
    assert json_servers["servers"][0]["server_id"]

    json_market = _invoke_json(runner, config_file, ["market", "show", "Context7"])
    assert json_market["catalog_id"] == "wotv5q80be"


def test_apps_matrix_shows_cluster_grid_for_one_app(
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

    _add_server(
        runner,
        config_file,
        "Context7",
        command="npx",
        args=["-y", "@upstash/context7-mcp@latest"],
    )
    _add_server(
        runner,
        config_file,
        "Docker MCP Toolkit",
        command="docker",
        args=["mcp", "gateway", "run"],
    )
    _enable_servers(runner, config_file, "Codex", "Cluster A", ["Context7"])
    _enable_servers(runner, config_file, "Codex", "Testing", ["Docker MCP Toolkit"])

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "apps",
            "matrix",
            "Codex",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Server" in result.output
    assert "Cluster A (active)" in result.output
    assert "Testing" in result.output
    assert "Context7" in result.output
    assert "Docker MCP Toolkit" in result.output


def test_apps_matrix_enabled_only_filters_disabled_servers(
    runner, temp_db: Path, resources_dir: Path
) -> None:
    config_file = _config_file(temp_db, resources_dir)

    _add_server(
        runner,
        config_file,
        "Enabled Server",
        command="python3",
        args=["-m", "enabled_server"],
    )
    _add_server(
        runner,
        config_file,
        "Disabled Server",
        command="python3",
        args=["-m", "disabled_server"],
    )
    _enable_servers(runner, config_file, "Codex", "Cluster A", ["Enabled Server"])

    result = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "apps",
            "matrix",
            "Codex",
            "--enabled-only",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Enabled Server" in result.output
    assert "Disabled Server" not in result.output


def test_json_read_commands_return_structured_payloads(
    runner, temp_db: Path, resources_dir: Path
) -> None:
    config_file = _config_file(temp_db, resources_dir)
    _add_server(
        runner,
        config_file,
        "Context7",
        command="npx",
        args=["-y", "@upstash/context7-mcp@latest"],
    )
    _enable_servers(runner, config_file, "Codex", "Cluster A", ["Context7"])

    apps_payload = _invoke_json(runner, config_file, ["apps", "list"])
    assert apps_payload["count"] == 1
    assert apps_payload["apps"][0]["name"] == "Codex"

    app_payload = _invoke_json(runner, config_file, ["apps", "show", "Codex"])
    assert app_payload["name"] == "Codex"

    matrix_payload = _invoke_json(runner, config_file, ["apps", "matrix", "Codex"])
    assert matrix_payload["app"]["name"] == "Codex"
    assert matrix_payload["clusters"][0]["name"] == "Cluster A"
    assert matrix_payload["servers"][0]["name"] == "Context7"

    clusters_payload = _invoke_json(runner, config_file, ["clusters", "list"])
    assert clusters_payload["count"] == 1
    assert clusters_payload["clusters"][0]["app_name"] == "Codex"

    cluster_payload = _invoke_json(
        runner, config_file, ["clusters", "show", "Cluster A", "--app", "Codex"]
    )
    assert cluster_payload["name"] == "Cluster A"
    assert cluster_payload["enabled_server_ids"]

    servers_payload = _invoke_json(runner, config_file, ["servers", "list"])
    assert servers_payload["count"] == 1
    assert servers_payload["servers"][0]["name"] == "Context7"

    server_payload = _invoke_json(runner, config_file, ["servers", "show", "Context7"])
    assert server_payload["name"] == "Context7"
    assert server_payload["command"] == "npx"

    market_payload = _invoke_json(runner, config_file, ["market", "list"])
    assert market_payload["count"] == 1
    assert market_payload["tools"][0]["name"] == "Context7"

    market_show_payload = _invoke_json(runner, config_file, ["market", "show", "Context7"])
    assert market_show_payload["name"] == "Context7"

    doctor_payload = _invoke_json(runner, config_file, ["doctor"])
    assert doctor_payload["checks"]["db_exists"] is True


def test_json_write_and_sync_commands_return_structured_payloads(
    runner, temp_db: Path, resources_dir: Path
) -> None:
    config_file = _config_file(temp_db, resources_dir)
    custom_target = temp_db.parent / "custom.json"
    import_target = temp_db.parent / "import.json"
    import_target.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "GitHub[id=PX649D]": {
                        "command": "docker",
                        "args": ["run", "-i", "--rm", "ghcr.io/github/github-mcp-server:latest"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    add_app_payload = _invoke_json(
        runner,
        config_file,
        ["apps", "add-custom", "Custom App", str(custom_target), "--config-key", "mcpServers"],
    )
    assert add_app_payload["action"] == "apps.add-custom"
    assert add_app_payload["app"]["name"] == "Custom App"

    create_cluster_payload = _invoke_json(
        runner, config_file, ["clusters", "create", "Testing", "--app", "Codex"]
    )
    assert create_cluster_payload["action"] == "clusters.create"
    assert create_cluster_payload["cluster"]["name"] == "Testing"

    rename_cluster_payload = _invoke_json(
        runner,
        config_file,
        ["clusters", "rename", "Testing", "Renamed", "--app", "Codex"],
    )
    assert rename_cluster_payload["cluster"]["name"] == "Renamed"

    set_active_payload = _invoke_json(
        runner,
        config_file,
        ["apps", "set-active-cluster", "Codex", "Renamed"],
    )
    assert set_active_payload["app"]["active_cluster_id"]

    add_server_payload = _invoke_json(
        runner,
        config_file,
        [
            "servers",
            "add",
            "Local Dev Server",
            "--command",
            "python3",
            "--arg",
            "-m",
            "--arg",
            "my_server",
        ],
    )
    assert add_server_payload["action"] == "servers.add"
    assert add_server_payload["server"]["name"] == "Local Dev Server"

    update_server_payload = _invoke_json(
        runner,
        config_file,
        ["servers", "update", "Local Dev Server", "--source", "custom"],
    )
    assert update_server_payload["server"]["source"] == "custom"

    enable_payload = _invoke_json(
        runner,
        config_file,
        ["servers", "enable", "Local Dev Server", "--app", "Codex", "--cluster", "Renamed"],
    )
    assert enable_payload["action"] == "servers.enable"
    assert "Local Dev Server" in enable_payload["server_refs"]

    create_second_cluster = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "clusters",
            "create",
            "Bulk Target",
            "--app",
            "Codex",
        ],
    )
    assert create_second_cluster.exit_code == 0, create_second_cluster.output

    enable_many_payload = _invoke_json(
        runner,
        config_file,
        [
            "servers",
            "enable-many",
            "Local Dev Server",
            "--target",
            "Codex::Renamed",
            "--target",
            "Codex::Bulk Target",
        ],
    )
    assert enable_many_payload["count"] == 2

    disable_payload = _invoke_json(
        runner,
        config_file,
        ["servers", "disable", "Local Dev Server", "--app", "Codex", "--cluster", "Bulk Target"],
    )
    assert disable_payload["action"] == "servers.disable"

    install_payload = _invoke_json(
        runner,
        config_file,
        [
            "market",
            "install",
            "Context7",
            "--app",
            "Codex",
            "--cluster",
            "Renamed",
            "--param",
            "CONTEXT7_API_KEY=test-key",
        ],
    )
    assert install_payload["action"] == "market.install"
    assert install_payload["tool"]["name"] == "Context7"

    sync_app_payload = _invoke_json(runner, config_file, ["sync", "app", "Codex"])
    assert sync_app_payload["action"] == "sync.app"
    assert sync_app_payload["app"]["name"] == "Codex"

    sync_all_payload = _invoke_json(runner, config_file, ["sync", "all"])
    assert sync_all_payload["count"] >= 1

    import_app_setup = _invoke_json(
        runner,
        config_file,
        ["apps", "add-custom", "Import App", str(import_target), "--config-key", "mcpServers"],
    )
    assert import_app_setup["app"]["name"] == "Import App"

    import_app_payload = _invoke_json(runner, config_file, ["import", "app", "Import App"])
    assert import_app_payload["action"] == "import.app"
    assert import_app_payload["imported_count"] == 1

    import_file_payload = _invoke_json(
        runner,
        config_file,
        ["import", "file", "Custom App", "--path", str(import_target), "--key", "mcpServers"],
    )
    assert import_file_payload["action"] == "import.file"
    assert import_file_payload["path"] == str(import_target)

    delete_server_payload = _invoke_json(
        runner, config_file, ["servers", "delete", "Local Dev Server"]
    )
    assert delete_server_payload["server_ref"] == "Local Dev Server"

    delete_cluster_payload = _invoke_json(
        runner, config_file, ["clusters", "delete", "Bulk Target", "--app", "Codex"]
    )
    assert delete_cluster_payload["cluster_ref"] == "Bulk Target"


@pytest.mark.parametrize(
    (
        "storage_mode",
        "args_value",
        "env_value",
        "parameters_value",
        "expected_args",
        "expected_env",
    ),
    [
        (
            "blob",
            encode_blob(["-m", "my_local_server"]),
            encode_blob({"DEBUG": "true"}),
            encode_blob({"scope": "test"}),
            ["-m", "my_local_server"],
            {"DEBUG": "true"},
        ),
        (
            "text",
            '["-m", "my_local_server"]',
            '{"DEBUG": "true"}',
            '{"scope": "test"}',
            ["-m", "my_local_server"],
            {"DEBUG": "true"},
        ),
        (
            "malformed",
            "{not-json",
            "{not-json",
            "{not-json",
            None,
            None,
        ),
    ],
)
def test_sync_custom_app_handles_json_field_storage_variants(
    runner,
    temp_db: Path,
    resources_dir: Path,
    storage_mode: str,
    args_value: bytes | str,
    env_value: bytes | str,
    parameters_value: bytes | str,
    expected_args: list[str] | None,
    expected_env: dict[str, str] | None,
) -> None:
    del storage_mode
    config_file = _config_file(temp_db, resources_dir)
    antigravity_config = temp_db.parent / "mcp.json"

    _add_custom_app(runner, config_file, "Antigravity", antigravity_config, "servers")
    server_id = _add_server(
        runner,
        config_file,
        "Local Dev Server",
        command="python3",
        args=["-m", "my_local_server"],
        env={"DEBUG": "true"},
        parameters={"scope": "test"},
    )
    _enable_servers(runner, config_file, "Antigravity", "Cluster A", ["Local Dev Server"])

    with sqlite3.connect(temp_db) as connection:
        connection.execute(
            """
            UPDATE ZADDEDSERVER
            SET ZARGS=?, ZENV=?, ZPARAMETERS=?
            WHERE ZID=?
            """,
            (args_value, env_value, parameters_value, server_id),
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

    output_payload = _read_config(antigravity_config)
    server_payload = output_payload["servers"][f"Local_Dev_Server_id_{server_id}"]
    assert server_payload["command"] == "python3"
    if expected_args is None:
        assert "args" not in server_payload
    else:
        assert server_payload["args"] == expected_args
    if expected_env is None:
        assert "env" not in server_payload
    else:
        assert server_payload["env"] == expected_env


@pytest.mark.parametrize(
    ("filename", "config_key", "server_name", "expected_entry_key"),
    [
        ("client.json", "mcpServers", "Bracketed Server", "Bracketed Server[id={server_id}]"),
        ("client.toml", "mcp_servers", "Sanitized Toml", "Sanitized_Toml_id_{server_id}"),
        ("mcp.json", "servers", "Sanitized Json", "Sanitized_Json_id_{server_id}"),
    ],
)
def test_sync_respects_target_format_and_config_key(
    runner,
    temp_db: Path,
    resources_dir: Path,
    filename: str,
    config_key: str,
    server_name: str,
    expected_entry_key: str,
) -> None:
    config_file = _config_file(temp_db, resources_dir)
    target_path = temp_db.parent / filename
    app_name = f"App {filename}"

    _add_custom_app(runner, config_file, app_name, target_path, config_key)
    server_id = _add_server(
        runner,
        config_file,
        server_name,
        command="python3",
        args=["-m", "test_server"],
    )
    _enable_servers(runner, config_file, app_name, "Cluster A", [server_name])

    sync_result = runner.invoke(
        app,
        ["--config", str(config_file), "sync", "app", app_name],
    )
    assert sync_result.exit_code == 0, sync_result.output

    output_payload = _read_config(target_path)
    entry_key = expected_entry_key.format(server_id=server_id)
    assert config_key in output_payload
    assert entry_key in output_payload[config_key]


def test_sync_serializes_stdio_and_http_servers(runner, temp_db: Path, resources_dir: Path) -> None:
    config_file = _config_file(temp_db, resources_dir)
    target_path = temp_db.parent / "transport.json"
    app_name = "Transport App"

    _add_custom_app(runner, config_file, app_name, target_path, "mcpServers")
    stdio_id = _add_server(
        runner,
        config_file,
        "STDIO Server",
        command="python3",
        args=["-m", "stdio_server"],
        env={"DEBUG": "true"},
    )
    http_id = _add_server(
        runner,
        config_file,
        "HTTP Server",
        url="https://example.com/mcp",
        headers={"AUTHORIZATION": "Bearer test-token"},
        server_type="STREAMABLE_HTTP",
    )
    _enable_servers(runner, config_file, app_name, "Cluster A", ["STDIO Server", "HTTP Server"])

    sync_result = runner.invoke(
        app,
        ["--config", str(config_file), "sync", "app", app_name],
    )
    assert sync_result.exit_code == 0, sync_result.output

    output_payload = _read_config(target_path)["mcpServers"]
    assert output_payload[f"STDIO Server[id={stdio_id}]"] == {
        "command": "python3",
        "args": ["-m", "stdio_server"],
        "env": {"DEBUG": "true"},
    }
    assert output_payload[f"HTTP Server[id={http_id}]"] == {
        "url": "https://example.com/mcp",
        "headers": {"AUTHORIZATION": "Bearer test-token"},
    }


def test_sync_sanitizes_gemini_server_keys(runner, temp_db: Path, resources_dir: Path) -> None:
    config_file = _config_file(temp_db, resources_dir)
    target_path = temp_db.parent / "settings.json"
    app_name = "Gemini CLI"

    _add_custom_app(runner, config_file, app_name, target_path, "mcpServers")
    server_id = _add_server(
        runner,
        config_file,
        "Docker MCP Toolkit",
        command="docker",
        args=["mcp", "gateway", "run"],
    )
    _enable_servers(runner, config_file, app_name, "Cluster A", ["Docker MCP Toolkit"])

    sync_result = runner.invoke(
        app,
        ["--config", str(config_file), "sync", "app", app_name],
    )
    assert sync_result.exit_code == 0, sync_result.output

    output_payload = _read_config(target_path)["mcpServers"]
    assert f"Docker_MCP_Toolkit_id_{server_id}" in output_payload
    assert f"Docker MCP Toolkit[id={server_id}]" not in output_payload


def test_sync_adds_copilot_tools_and_sanitized_keys(
    runner, temp_db: Path, resources_dir: Path
) -> None:
    config_file = _config_file(temp_db, resources_dir)
    target_path = temp_db.parent / "mcp-config.json"
    app_name = "Copilot"

    _add_custom_app(runner, config_file, app_name, target_path, "mcpServers")
    server_id = _add_server(
        runner,
        config_file,
        "Context7",
        command="npx",
        args=["-y", "@upstash/context7-mcp@latest"],
    )
    _enable_servers(runner, config_file, app_name, "Cluster A", ["Context7"])

    sync_result = runner.invoke(
        app,
        ["--config", str(config_file), "sync", "app", app_name],
    )
    assert sync_result.exit_code == 0, sync_result.output

    output_payload = _read_config(target_path)["mcpServers"]
    assert output_payload[f"Context7_id_{server_id}"]["tools"] == ["*"]
    assert f"Context7[id={server_id}]" not in output_payload


def test_import_sync_round_trip_consistency(runner, temp_db: Path, resources_dir: Path) -> None:
    config_file = _config_file(temp_db, resources_dir)
    target_path = temp_db.parent / "roundtrip.json"
    original_payload = {
        "mcpServers": {
            "GitHub[id=PX649D]": {
                "command": "docker",
                "args": ["run", "-i", "--rm", "ghcr.io/github/github-mcp-server:latest"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "token"},
            },
            "Remote Docs[id=DOC123]": {
                "url": "https://example.com/mcp",
                "headers": {"AUTHORIZATION": "Bearer token"},
            },
        }
    }
    target_path.write_text(json.dumps(original_payload, indent=2), encoding="utf-8")

    _add_custom_app(runner, config_file, "Roundtrip App", target_path, "mcpServers")

    import_result = runner.invoke(
        app,
        ["--config", str(config_file), "import", "app", "Roundtrip App"],
    )
    assert import_result.exit_code == 0, import_result.output
    assert "Imported 2 server" in import_result.output

    _enable_servers(
        runner,
        config_file,
        "Roundtrip App",
        "Cluster A",
        ["PX649D", "DOC123"],
    )

    sync_result = runner.invoke(
        app,
        ["--config", str(config_file), "sync", "app", "Roundtrip App"],
    )
    assert sync_result.exit_code == 0, sync_result.output

    roundtrip_payload = _read_config(target_path)
    assert roundtrip_payload == original_payload


def _read_config(path: Path) -> dict[str, object]:
    if path.suffix.lower() == ".toml":
        with path.open("rb") as handle:
            return tomllib.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def _add_custom_app(
    runner,
    config_file: Path,
    app_name: str,
    target_path: Path,
    config_key: str,
) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "apps",
            "add-custom",
            app_name,
            str(target_path),
            "--config-key",
            config_key,
        ],
    )
    assert result.exit_code == 0, result.output


def _add_server(
    runner,
    config_file: Path,
    name: str,
    *,
    command: str | None = None,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    parameters: dict[str, str] | None = None,
    url: str | None = None,
    server_type: str | None = None,
) -> str:
    command_args = [
        "--config",
        str(config_file),
        "servers",
        "add",
        name,
    ]
    if command is not None:
        command_args.extend(["--command", command])
    for arg in args or []:
        command_args.extend(["--arg", arg])
    for key, value in (env or {}).items():
        command_args.extend(["--env", f"{key}={value}"])
    for key, value in (headers or {}).items():
        command_args.extend(["--header", f"{key}={value}"])
    for key, value in (parameters or {}).items():
        command_args.extend(["--parameter", f"{key}={value}"])
    if url is not None:
        command_args.extend(["--url", url])
    if server_type is not None:
        command_args.extend(["--type", server_type])

    result = runner.invoke(app, command_args)
    assert result.exit_code == 0, result.output

    show_result = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "--json",
            "servers",
            "show",
            name,
        ],
    )
    assert show_result.exit_code == 0, show_result.output
    return json.loads(show_result.stdout)["server_id"]


def _enable_servers(
    runner,
    config_file: Path,
    app_name: str,
    cluster_name: str,
    server_refs: list[str],
) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            str(config_file),
            "servers",
            "enable",
            *server_refs,
            "--app",
            app_name,
            "--cluster",
            cluster_name,
        ],
    )
    assert result.exit_code == 0, result.output


def _invoke_json(runner, config_file: Path, command: list[str]) -> dict[str, object]:
    result = runner.invoke(app, ["--config", str(config_file), "--json", *command])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def _config_file(temp_db: Path, resources_dir: Path) -> Path:
    config_path = temp_db.parent / "config.toml"
    config_path.write_text(
        f'db_path = "{temp_db}"\nresources_dir = "{resources_dir}"\nbackup_on_write = false\n',
        encoding="utf-8",
    )
    return config_path
