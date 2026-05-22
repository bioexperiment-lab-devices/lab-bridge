# `SerialHop_config.yaml` reference

Every operator-facing setting lives in `SerialHop_config.yaml`, the YAML file next to `SerialHop.exe`. The Windows service reads the file at startup; restart the service from the control panel after editing.

## chisel

```yaml title="SerialHop_config.yaml (chisel section)"
chisel:
  host: <vps-host>
  port: 8080
  remote_port: 9001
  user: <lab-name>
  pass: <secret>
```

| Key | What it is | Set by |
|---|---|---|
| `host` | The lab-bridge VPS hostname or IP. | Server admin issues. |
| `port` | The chisel server's listen port on the VPS. | Server admin issues. |
| `remote_port` | The port on the VPS where this lab's REST API is published into `labnet`. Must match the value the admin minted. | Server admin issues. |
| `user` | Per-lab chisel username. Doubles as the lab name researchers use. | Server admin issues. |
| `pass` | Per-lab chisel password. | Server admin issues. |

## Log rotation

```yaml title="SerialHop_config.yaml (logging section)"
logging:
  max_size_mb: 10
  keep: 3
```

| Key | What it is | Default |
|---|---|---|
| `max_size_mb` | Roll a log file once it grows past this many MB. | 10 |
| `keep` | How many rotated files to keep (`SerialHop.log.1`, …). | 3 |

Logs live next to the binary as `SerialHop.log` (slog JSON) and `SerialHop_stderr.log` (chisel state + panic traces).

## What's out of scope here

This page covers operator-facing settings. Run modes (service vs control panel vs `--foreground`), build process, byte-level device protocol, and SerialHop internals live in the SerialHop repo at [`bioexperiment-lab-devices/serialhop`](https://github.com/bioexperiment-lab-devices/serialhop).
