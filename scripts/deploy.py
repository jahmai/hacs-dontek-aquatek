#!/usr/bin/env python3
"""Deploy the Dontek Aquatek integration to Home Assistant via SSH/SCP.

Works on Windows and WSL2. The HA host is stored in local/deploy.conf
(gitignored) so you only need to enter it once.

Usage:
    python scripts/deploy.py                  # use saved host
    python scripts/deploy.py 192.168.1.10    # specify host (and save it)
    python scripts/deploy.py --no-restart    # upload only, skip restart
    python scripts/deploy.py --key ~/.ssh/my_key
"""

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

REMOTE_USER = "root"
REMOTE_PATH = "/config/custom_components/dontek_aquatek"
REPO_ROOT = Path(__file__).parent.parent
LOCAL_COMPONENT = REPO_ROOT / "custom_components" / "dontek_aquatek"
DEPLOY_CONF = REPO_ROOT / "local" / "deploy.conf"

# SSH key search order per platform
WINDOWS_KEY = Path.home() / ".ssh" / "ha_claude_key"
WSL_WIN_KEY  = Path("/mnt/c/Users") / os.environ.get("USERNAME", "") / ".ssh" / "ha_claude_key"


def is_wsl() -> bool:
    try:
        return "microsoft" in platform.uname().release.lower()
    except Exception:
        return False


def default_key() -> Path:
    if platform.system() == "Windows":
        return WINDOWS_KEY
    # WSL2 or native Linux — prefer a key in the WSL home dir, fall back to
    # the Windows-side key mounted at /mnt/c/...
    wsl_home_key = Path.home() / ".ssh" / "ha_claude_key"
    if wsl_home_key.exists():
        return wsl_home_key
    if is_wsl() and WSL_WIN_KEY.exists():
        return WSL_WIN_KEY
    return wsl_home_key  # return it even if missing so the error is clear


def run(cmd: list, check: bool = True) -> int:
    print("  $", " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd)
    if check and result.returncode != 0:
        print(f"Command failed (exit {result.returncode})")
        sys.exit(result.returncode)
    return result.returncode


def resolve_host(arg: str | None) -> str:
    if arg:
        host = arg.strip()
        DEPLOY_CONF.parent.mkdir(exist_ok=True)
        DEPLOY_CONF.write_text(host)
        print(f"  Saved host to {DEPLOY_CONF}")
        return host
    if DEPLOY_CONF.exists():
        return DEPLOY_CONF.read_text().strip()
    host = input("HA host (IP or hostname): ").strip()
    DEPLOY_CONF.parent.mkdir(exist_ok=True)
    DEPLOY_CONF.write_text(host)
    print(f"  Saved host to {DEPLOY_CONF}")
    return host


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy integration to Home Assistant")
    parser.add_argument("host", nargs="?", help="HA host IP or hostname (saved for next run)")
    parser.add_argument("--key", help="Path to SSH private key")
    parser.add_argument("--user", default=REMOTE_USER, help=f"SSH user (default: {REMOTE_USER})")
    parser.add_argument("--no-restart", action="store_true", help="Upload files but skip HA restart")
    args = parser.parse_args()

    host = resolve_host(args.host)
    key = Path(args.key).expanduser() if args.key else default_key()

    if not key.exists():
        print(f"SSH key not found: {key}")
        print("Pass --key <path> or place the key at the expected location.")
        sys.exit(1)

    # SSH is strict about key file permissions on Linux/WSL
    if platform.system() != "Windows":
        os.chmod(key, 0o600)

    target = f"{args.user}@{host}"
    ssh_opts = ["-i", str(key), "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes"]

    print(f"\nTarget : {target}:{REMOTE_PATH}")
    print(f"SSH key: {key}\n")

    # Ensure the remote directory exists
    run(["ssh"] + ssh_opts + [target, f"mkdir -p {REMOTE_PATH}"])

    # Collect files to upload: all .py files + manifest.json
    files = list(LOCAL_COMPONENT.glob("*.py"))
    manifest = LOCAL_COMPONENT / "manifest.json"
    if manifest.exists():
        files.append(manifest)

    print(f"Uploading {len(files)} file(s)...")
    run(["scp"] + ssh_opts + [str(f) for f in files] + [f"{target}:{REMOTE_PATH}/"])

    if args.no_restart:
        print("\nSkipped restart (--no-restart). Done.")
        return

    print("\nRestarting Home Assistant core...")
    run(["ssh"] + ssh_opts + [target, "ha core restart"])
    print("Restart initiated — check HA logs or the UI for startup status.")


if __name__ == "__main__":
    main()
