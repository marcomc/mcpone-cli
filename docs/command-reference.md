# Command Reference

## Global

```bash
mcpone-cli --config /path/to/config.toml <group> <command>
```

Global option:

- `--config`: override the default runtime config file
- `--json`: emit machine-readable JSON instead of Rich tables or status text

Example:

```bash
mcpone-cli --json apps matrix Codex
```

## apps

### `apps list`

Lists all apps from `ZADDEDAPP`.

### `apps show <app-ref>`

Shows one app as JSON.

`<app-ref>` can be:

- app name
- app ID

### `apps matrix <app-ref>`

Shows a GUI-style server matrix for one app.

- rows: servers
- columns: clusters for the app
- cell `Y`: the server is enabled in that cluster
- active cluster: marked in the column header

Option:

- `--enabled-only`: hide servers that are not enabled in any cluster for the app

### `apps add-custom <name> <config-path>`

Creates a custom app record and a default `Cluster A`.

Options:

- `--config-key`
- `--ai-agent-id`
- `--explanation`

### `apps set-active-cluster <app-ref> <cluster-ref>`

Sets `ZADDEDAPP.ZACTIVECLUSTERID`.

## clusters

### `clusters list --app <app>`

Lists clusters, optionally scoped to one app.

The table shows the owning app name and is sorted by app name, then cluster name.

### `clusters show <cluster-ref> --app <app>`

Shows cluster JSON including enabled server IDs.

### `clusters create <name> --app <app>`

Creates a cluster for the given app.

### `clusters rename <cluster-ref> <new-name> --app <app>`

Renames a cluster.

### `clusters delete <cluster-ref> --app <app>`

Deletes a cluster.

If the cluster was active, the app's active cluster is cleared.

## servers

### `servers list`

Lists all added servers from `ZADDEDSERVER`.

Option:

- `--source`

### `servers show <server-ref>`

Shows one server as JSON.

`<server-ref>` can be:

- server name
- server ID

### `servers add <name>`

Adds a new server record.

Options:

- `--command`
- `--arg`
- `--env KEY=VALUE`
- `--header KEY=VALUE`
- `--parameter KEY=VALUE`
- `--url`
- `--type`
- `--source`
- `--version`
- `--server-id`

### `servers update <server-ref>`

Updates one server record.

Options mirror `servers add`.

### `servers delete <server-ref>`

Deletes the server and removes its ID from all clusters.

### `servers enable <server-ref>... --app <app> --cluster <cluster>`

Adds one or more server IDs to the cluster's enabled server array.

### `servers enable-many <server-ref>... --target <app::cluster>`

Adds one or more servers to multiple target app clusters in one command.

Repeat `--target` as needed.

Accepted target formats:

- `APP::CLUSTER`
- `APP/CLUSTER`

### `servers disable <server-ref>... --app <app> --cluster <cluster>`

Removes one or more server IDs from the cluster's enabled server array.

## market

### `market list`

Lists the bundled market catalog shipped with McpOne.

Option:

- `--category`

### `market show <tool-ref>`

Shows one market entry as JSON.

`<tool-ref>` can be:

- tool name
- catalog ID

### `market install <tool-ref> --app <app> --cluster <cluster>`

Materializes one market connection into a McpOne added server and enables it.

Options:

- `--connection`
- `--param KEY=VALUE`
- `--version`

## import

### `import app <app-ref>`

Imports server definitions from the app's configured config file and key.

### `import file <app-ref> --path <file> --key <root-key>`

Imports from an explicit file and root key.

## sync

### `sync app <app-ref>`

Writes the active cluster's enabled servers to the app's target config file.

### `sync all`

Syncs every app with a configured target path, root key, and active cluster.

## doctor

### `doctor`

Prints a quick diagnostic table:

- DB path
- DB existence
- resource directory
- resource directory existence
- market tool count
- app count
