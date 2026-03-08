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


@pytest.mark.parametrize("group_name", ["apps", "clusters", "servers", "market", "sync", "import"])
def test_command_groups_show_help_without_subcommand(runner, group_name: str) -> None:
    result = runner.invoke(app, [group_name])
    assert "Usage:" in result.stdout
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
    assert "Alpha App" in list_result.output
    assert "Codex" in list_result.output
    assert list_result.output.index("Alpha App") < list_result.output.index("Codex")


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


def _config_file(temp_db: Path, resources_dir: Path) -> Path:
    config_path = temp_db.parent / "config.toml"
    config_path.write_text(
        f'db_path = "{temp_db}"\nresources_dir = "{resources_dir}"\nbackup_on_write = false\n',
        encoding="utf-8",
    )
    return config_path
