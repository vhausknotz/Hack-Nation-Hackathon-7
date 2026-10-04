"""Operate the cloud engine VM (owner-approved 2026-10-04, ceiling $45/month for the whole project).

    python tools/azure_engine_vm.py create     # deploy infra/engine/main.bicep (VM, disk, IP, NSG with no inbound)
    python tools/azure_engine_vm.py setup      # packages, Python env, systemd service, nightly backup
    python tools/azure_engine_vm.py migrate    # stop the PC engine, ship code + state, start the VM engine
    python tools/azure_engine_vm.py update     # ship current code only (keeps VM state), restart the service
    python tools/azure_engine_vm.py variants   # install the weekly ClinVar refresh timer and run it once now
    python tools/azure_engine_vm.py status | stop | start | logs

`stop` deallocates the VM: compute billing stops (disk and IP, about $6/month, remain). The engine's queue
lives in Azure Storage, so nothing is lost while it is stopped. Secrets (storage connection string, OpenAI
key) go only into /etc/atlas/engine.env on the VM (root, 0600), via Run Command; they are never printed.
"""
import argparse
import base64
import io
import json
import os
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.azure_mcp_operator import Operator  # noqa: E402

VM = "atlas-engine"
LOCAL = ROOT / "data/engine-vm"
REPO = "/opt/atlas/repo"
STATE_PATHS = ["data/ledger", "data/contributions", "data/build", "data/raw", "data/engine", "app/public/data"]
SKIP = {"data/engine/export", "data/engine/engine.lock", "data/engine/stop"}


class EngineVM:
    def __init__(self):
        self.op = Operator()
        self.vm = self.op.scope + "/providers/Microsoft.Compute/virtualMachines/" + VM

    # ---- infrastructure ---------------------------------------------------------------------------
    def ssh_key(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        LOCAL.mkdir(parents=True, exist_ok=True)
        private = LOCAL / "emergency_ed25519"
        if not private.exists():
            key = Ed25519PrivateKey.generate()
            private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()))
            (LOCAL / "emergency_ed25519.pub").write_bytes(key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH))
        return (LOCAL / "emergency_ed25519.pub").read_text().strip()

    def create(self):
        subprocess.run([str(ROOT / "data/build/bicep.exe"), "build", str(ROOT / "infra/engine/main.bicep"), "--outfile", str(LOCAL / "main.json")], check=True)
        template = json.loads((LOCAL / "main.json").read_text(encoding="utf-8"))
        body = {"properties": {"mode": "Incremental", "template": template, "parameters": {"sshPublicKey": {"value": self.ssh_key()}}}}
        name = "atlas-engine-" + datetime.now().strftime("%Y%m%d%H%M")
        self.op.arm("PUT", self.op.scope + f"/providers/Microsoft.Resources/deployments/{name}?api-version=2021-04-01", json=body)
        for _ in range(90):
            time.sleep(20)
            state = self.op.arm("GET", self.op.scope + f"/providers/Microsoft.Resources/deployments/{name}?api-version=2021-04-01")["properties"]["provisioningState"]
            if state in ("Succeeded", "Failed", "Canceled"):
                return {"deployment": name, "state": state}
        return {"deployment": name, "state": "still running"}

    def power(self):
        view = self.op.arm("GET", self.vm + "/instanceView?api-version=2024-03-01")
        return next((s["displayStatus"] for s in view.get("statuses", []) if s["code"].startswith("PowerState/")), "unknown")

    def action(self, verb):
        self.op.arm("POST", self.vm + f"/{verb}?api-version=2024-03-01")
        return {"requested": verb}

    # ---- remote execution ----------------------------------------------------------------------------
    def run(self, script, timeout=3000):
        """Run a shell script as root through Azure Run Command (no inbound network access needed)."""
        body = {"commandId": "RunShellScript", "script": [script]}
        import requests
        r = requests.post("https://management.azure.com" + self.vm + "/runCommand?api-version=2024-03-01", json=body,
                          headers=self.op.headers(), timeout=60, allow_redirects=False)
        if r.status_code not in (200, 202):
            raise RuntimeError(f"Run Command was not accepted: HTTP {r.status_code}")
        poll = r.headers.get("Azure-AsyncOperation") or r.headers.get("Location")
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(10)
            s = requests.get(poll, headers=self.op.headers(), timeout=60)
            if s.status_code != 200 or not s.content:
                continue
            body = s.json()
            if body.get("status") in ("InProgress", "Running"):
                continue
            values = (body.get("properties") or {}).get("output", {}).get("value") or body.get("value") or []
            if body.get("status") in ("Failed", "Canceled") and not values:
                raise RuntimeError(f"Run Command {body.get('status')}: {str(body.get('error'))[:300]}")
            return "\n".join(v.get("message", "") for v in values)
        raise RuntimeError("Run Command timed out")

    # ---- shipping code and state through private blob storage -------------------------------------
    def upload(self, name, data):
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas
        store = self.op.store()
        container = store.container
        container.upload_blob("engine-transfer/" + name, data, overwrite=True, max_concurrency=8)
        key = self.op.arm("POST", self.op.scope + "/providers/Microsoft.Storage/storageAccounts/" + self.op.config["storageName"] + "/listKeys?api-version=2023-05-01")["keys"][0]["value"]
        sas = generate_blob_sas(container.account_name, container.container_name, "engine-transfer/" + name, account_key=key,
                                permission=BlobSasPermissions(read=True), expiry=datetime.now(timezone.utc) + timedelta(hours=2))
        return f"{container.url}/engine-transfer/{name}?{sas}"

    def code_bundle(self):
        return subprocess.run(["git", "archive", "--format=tar.gz", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout

    def state_bundle(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz", compresslevel=3) as tar:
            for rel in STATE_PATHS:
                path = ROOT / rel
                if not path.exists():
                    continue
                def keep(info, rel=rel):
                    name = info.name.replace("\\", "/")
                    return None if any(name == s or name.startswith(s + "/") for s in SKIP) or name.endswith((".lock", "-shm", "-wal")) else info
                tar.add(path, arcname=rel, filter=keep)
        return buffer.getvalue()

    def secrets_script(self):
        c = self.op.config
        storage_key = self.op.arm("POST", self.op.scope + "/providers/Microsoft.Storage/storageAccounts/" + c["storageName"] + "/listKeys?api-version=2023-05-01")["keys"][0]["value"]
        oai = "/subscriptions/" + c["subscriptionId"] + "/resourceGroups/valiprintify/providers/Microsoft.CognitiveServices/accounts/valiOpenAI"
        oai_key = self.op.arm("POST", oai + "/listKeys?api-version=2024-10-01")["key1"]
        env = (f"ATLAS_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName={c['storageName']};AccountKey={storage_key};EndpointSuffix=core.windows.net\n"
               f"AZURE_OPENAI_API_KEY={oai_key}\nATLAS_ENGINE_HOST=azure-vm\nPYTHONUNBUFFERED=1\n")
        encoded = base64.b64encode(env.encode()).decode()
        return f"install -d -m 700 /etc/atlas && echo {encoded} | base64 -d > /etc/atlas/engine.env && chmod 600 /etc/atlas/engine.env && echo secrets-written"

    def setup(self):
        script = r"""set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq python3-venv python3-pip curl git > /dev/null
id -u atlas >/dev/null 2>&1 || useradd -m atlas
install -d -o atlas -g atlas /opt/atlas /opt/atlas/repo
if ! swapon --show | grep -q swapfile; then fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab; fi
cat > /etc/systemd/system/atlas-engine.service <<'UNIT'
[Unit]
Description=Rare Disease Atlas engine (intake -> kernel -> review -> live publication)
After=network-online.target
Wants=network-online.target
[Service]
User=atlas
WorkingDirectory=/opt/atlas/repo
EnvironmentFile=/etc/atlas/engine.env
ExecStart=/opt/atlas/venv/bin/python tools/atlas_engine.py
Restart=always
RestartSec=30
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/atlas-backup.service <<'UNIT'
[Unit]
Description=Nightly backup of the atlas ledger and engine state to private blob storage
[Service]
Type=oneshot
User=atlas
WorkingDirectory=/opt/atlas/repo
EnvironmentFile=/etc/atlas/engine.env
ExecStart=/opt/atlas/venv/bin/python tools/engine_backup.py
UNIT
cat > /etc/systemd/system/atlas-backup.timer <<'UNIT'
[Unit]
Description=Nightly atlas backup
[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
echo setup-done
"""
        return self.run(script) + "\n" + self.run(self.secrets_script())

    def ship(self, with_state):
        code = self.upload("code.tar.gz", self.code_bundle())
        steps = [f"curl -fsS '{code}' -o /tmp/code.tar.gz", f"tar -xzf /tmp/code.tar.gz -C {REPO}"]
        if with_state:
            state = self.upload("state.tar.gz", self.state_bundle())
            steps += [f"curl -fsS '{state}' -o /tmp/state.tar.gz", f"tar -xzf /tmp/state.tar.gz -C {REPO}"]
        steps += [f"chown -R atlas:atlas {REPO}", "rm -f /tmp/code.tar.gz /tmp/state.tar.gz",
                  "[ -x /opt/atlas/venv/bin/python ] || sudo -u atlas python3 -m venv /opt/atlas/venv",
                  f"sudo -u atlas /opt/atlas/venv/bin/pip install -q -r {REPO}/pipeline/requirements.txt -r {REPO}/atlas_mcp/requirements-cloud.txt 2>&1 | tail -2",
                  "echo shipped"]
        script = "set -e\n" + "\n".join(steps)
        out = self.run(script)
        self.op.store().container.delete_blobs("engine-transfer/code.tar.gz", *(["engine-transfer/state.tar.gz"] if with_state else []))
        return out

    def migrate(self):
        stop = ROOT / "data/engine/stop"
        stop.touch()
        for _ in range(120):  # the PC engine finishes its current pass, then exits
            log = (ROOT / "data/engine/engine.log").read_text(encoding="utf-8").splitlines()
            if log and log[-1].endswith("engine stopped"):
                break
            time.sleep(5)
        else:
            raise RuntimeError("The PC engine did not stop; nothing was shipped")
        stop.unlink()
        out = self.ship(with_state=True)
        out += self.run("systemctl enable --now atlas-engine atlas-backup.timer && sleep 20 && systemctl is-active atlas-engine && journalctl -u atlas-engine -n 15 --no-pager")
        (ROOT / "data/engine/MOVED_TO_CLOUD.txt").write_text("The engine runs on the Azure VM 'atlas-engine' since " + datetime.now().isoformat(timespec="minutes")
                                                            + ". Do not start tools/atlas_engine.py on this PC unless the VM is stopped and its state copied back.\n", encoding="utf-8")
        return out

    def scouts(self):
        """Install and start the Luna scouts service; set the referee's monthly cap to the owner's budget."""
        script = r"""set -e
cat > /etc/systemd/system/atlas-scouts.service <<'UNIT'
[Unit]
Description=Rare Disease Atlas Luna scouts (slow, budget-capped contributors)
After=network-online.target atlas-engine.service
[Service]
User=atlas
WorkingDirectory=/opt/atlas/repo
EnvironmentFile=/etc/atlas/engine.env
ExecStart=/opt/atlas/venv/bin/python tools/luna_scout.py
Restart=always
RestartSec=60
[Install]
WantedBy=multi-user.target
UNIT
sudo -u atlas /opt/atlas/venv/bin/python - <<'PY'
import json, pathlib
p = pathlib.Path('/opt/atlas/repo/data/engine/config.json')
c = json.loads(p.read_text())
c.update(daily_usd_cap=1.0, monthly_usd_cap=12.0)
p.write_text(json.dumps(c, indent=1))
print('referee caps', c['daily_usd_cap'], c['monthly_usd_cap'])
PY
systemctl daemon-reload
systemctl restart atlas-engine
systemctl enable --now atlas-scouts
sleep 30
systemctl is-active atlas-scouts
journalctl -u atlas-scouts -n 6 --no-pager
"""
        return self.run(script)

    def variants(self):
        """Weekly ClinVar refresh (pipeline/variants.py --upload) as a systemd timer; starts a first run now."""
        script = r"""set -e
cat > /etc/systemd/system/atlas-variants.service <<'UNIT'
[Unit]
Description=Weekly ClinVar variant refresh for the atlas (per-gene look-up files + condition counts)
After=network-online.target
[Service]
Type=oneshot
User=atlas
WorkingDirectory=/opt/atlas/repo
EnvironmentFile=/etc/atlas/engine.env
ExecStart=/opt/atlas/venv/bin/python pipeline/variants.py --upload
UNIT
cat > /etc/systemd/system/atlas-variants.timer <<'UNIT'
[Unit]
Description=Weekly ClinVar refresh (ClinVar publishes weekly)
[Timer]
OnCalendar=Mon *-*-* 04:30:00
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now atlas-variants.timer
systemctl start --no-block atlas-variants.service
sleep 5
systemctl is-active atlas-variants.service || true
"""
        return self.run(script)

    def site(self):
        """Full website release from the cloud's current data: VM exports, PC builds the frontend and deploys."""
        import shutil
        import tarfile
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas
        store = self.op.store()
        container = store.container
        key = self.op.arm("POST", self.op.scope + "/providers/Microsoft.Storage/storageAccounts/" + self.op.config["storageName"] + "/listKeys?api-version=2023-05-01")["keys"][0]["value"]
        sas = generate_blob_sas(container.account_name, container.container_name, "engine-transfer/site.tar.gz", account_key=key,
                                permission=BlobSasPermissions(write=True, create=True, read=True), expiry=datetime.now(timezone.utc) + timedelta(hours=2))
        url = f"{container.url}/engine-transfer/site.tar.gz?{sas}"
        out = self.run(f"""set -e
cd {REPO}
rm -rf data/engine/site-export
sudo -u atlas env ATLAS_EXPORT_OUT=data/engine/site-export /opt/atlas/venv/bin/python pipeline/export_app.py | tail -1
tar -czf /tmp/site.tar.gz -C data/engine/site-export .
curl -fsS -X PUT -H 'x-ms-blob-type: BlockBlob' --data-binary @/tmp/site.tar.gz '{url}'
rm -f /tmp/site.tar.gz
echo uploaded""")
        LOCAL.mkdir(parents=True, exist_ok=True)
        archive = LOCAL / "site.tar.gz"
        with archive.open("wb") as f:
            container.download_blob("engine-transfer/site.tar.gz").readinto(f)
        container.delete_blob("engine-transfer/site.tar.gz")
        target = ROOT / "app/public/data"
        staging = ROOT / "app/public/data.new"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        with tarfile.open(archive) as tar:
            tar.extractall(staging, filter="data")
        shutil.rmtree(target, ignore_errors=True)
        staging.rename(target)
        npm = "npm.cmd" if os.name == "nt" else "npm"
        subprocess.run([npm, "--prefix", str(ROOT / "app"), "run", "build"], check=True, capture_output=True)
        from tools.deploy_website import deploy
        return out + "\n" + json.dumps(deploy())

    def update(self):
        out = self.ship(with_state=False)
        return out + self.run("systemctl restart atlas-engine && (systemctl is-enabled atlas-scouts >/dev/null 2>&1 && systemctl restart atlas-scouts || true) && sleep 15 && systemctl is-active atlas-engine && journalctl -u atlas-engine -n 8 --no-pager")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("create", "setup", "migrate", "update", "scouts", "variants", "site", "status", "stop", "start", "logs"))
    args = parser.parse_args()
    vm = EngineVM()
    if args.command == "create":
        print(json.dumps(vm.create(), indent=1))
    elif args.command == "setup":
        print(vm.setup())
    elif args.command == "migrate":
        print(vm.migrate())
    elif args.command == "update":
        print(vm.update())
    elif args.command == "scouts":
        print(vm.scouts())
    elif args.command == "variants":
        print(vm.variants())
    elif args.command == "site":
        print(vm.site())
    elif args.command == "status":
        print(json.dumps({"vm": VM, "power": vm.power()}, indent=1))
    elif args.command == "stop":
        print(json.dumps(vm.action("deallocate")))
    elif args.command == "start":
        print(json.dumps(vm.action("start")))
    else:
        print(vm.run("journalctl -u atlas-engine -n 40 --no-pager; tail -5 /opt/atlas/repo/data/engine/status.json 2>/dev/null"))


if __name__ == "__main__":
    main()
