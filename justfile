SERVICE_NAME := "peyote-gui.service"
UNIT_DIR := env_var_or_default("XDG_CONFIG_HOME", env_var("HOME") / ".config") / "systemd/user"

# List available recipes
default:
    @just --list

# Install the Web GUI as a systemd user service and start it (default port 8080)
install-service port="8080":
    #!/usr/bin/env bash
    set -euo pipefail
    UV_BIN="$(command -v uv)"
    if [ -z "$UV_BIN" ]; then
        echo "error: uv not found on PATH" >&2
        exit 1
    fi
    mkdir -p "{{UNIT_DIR}}"
    cat > "{{UNIT_DIR}}/{{SERVICE_NAME}}" <<EOF
    [Unit]
    Description=Peyote Pattern Designer Web GUI
    After=network.target

    [Service]
    Type=simple
    WorkingDirectory={{justfile_directory()}}
    ExecStart=$UV_BIN run peyote-gui --port {{port}}
    Restart=on-failure
    RestartSec=5

    [Install]
    WantedBy=default.target
    EOF
    systemctl --user daemon-reload
    systemctl --user enable --now {{SERVICE_NAME}}
    echo "Installed: {{UNIT_DIR}}/{{SERVICE_NAME}}"
    echo "Listening on http://localhost:{{port}}"

# Stop, disable, and remove the systemd user service
uninstall-service:
    #!/usr/bin/env bash
    set -euo pipefail
    systemctl --user disable --now {{SERVICE_NAME}} 2>/dev/null || true
    rm -f "{{UNIT_DIR}}/{{SERVICE_NAME}}"
    systemctl --user daemon-reload
    echo "Removed {{SERVICE_NAME}}"

# Show service status
service-status:
    systemctl --user status {{SERVICE_NAME}}

# Follow service logs
service-logs:
    journalctl --user -u {{SERVICE_NAME}} -f
