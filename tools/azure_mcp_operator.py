"""Explicit MCP operator commands; Azure credentials stay in process memory.

Uses the existing Az PowerShell login and ignored deployment metadata. Never
prints management response bodies, access tokens, settings or storage keys.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests
from azure.identity import AzurePowerShellCredential

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Operator:
    def __init__(self):
        self.config = json.loads((ROOT / "data/build/mcp-deployment.json").read_text(encoding="utf-8-sig"))
        c = self.config
        if c["resourceGroup"] != "rare-disease-atlas-mcp":
            raise ValueError("Only the dedicated MCP resource group is permitted")
        self.credential = AzurePowerShellCredential(tenant_id=c["tenantId"])
        self.scope = f'/subscriptions/{c["subscriptionId"]}/resourceGroups/{c["resourceGroup"]}'
        self.site = self.scope + '/providers/Microsoft.Web/sites/' + c["appName"]

    def headers(self):
        return {"Authorization": "Bearer " + self.credential.get_token("https://management.azure.com/.default").token}

    def arm(self, method, path, **kwargs):
        response = requests.request(method, "https://management.azure.com" + path,
                                    headers=self.headers(), timeout=60, allow_redirects=False, **kwargs)
        if response.status_code not in (200, 201, 202, 204):
            raise RuntimeError(f"Azure management request failed: HTTP {response.status_code}")
        return response.json() if response.content else {}

    def host(self):
        return self.arm("GET", self.site + "?api-version=2024-04-01")["properties"]["defaultHostName"]

    def store(self):
        from atlas_mcp.cloud import configured_store
        c = self.config
        key_path = self.scope + '/providers/Microsoft.Storage/storageAccounts/' + c["storageName"] + '/listKeys?api-version=2023-05-01'
        key = self.arm("POST", key_path)["keys"][0]["value"]
        # Operator-selected configuration only. Never persist this environment.
        os.environ["ATLAS_STORAGE_CONNECTION_STRING"] = f'DefaultEndpointsProtocol=https;AccountName={c["storageName"]};AccountKey={key};EndpointSuffix=core.windows.net'
        try:
            return configured_store()
        finally:
            os.environ.pop("ATLAS_STORAGE_CONNECTION_STRING", None)

    def deploy(self):
        from tools.package_mcp import package
        archive = ROOT / "data/build/mcp-function.zip"
        package(archive)
        host = self.host()
        scm = host.replace(".azurewebsites.net", ".scm.azurewebsites.net")
        with archive.open("rb") as stream:
            response = requests.post(f"https://{scm}/api/publish?RemoteBuild=true&Deployer=atlas_operator",
                                     data=stream, headers={**self.headers(), "Content-Type": "application/zip"},
                                     timeout=60, allow_redirects=False)
        if response.status_code != 202:
            raise RuntimeError(f"Package deployment returned HTTP {response.status_code}; inspect sanitized deployment status")
        return {"package_deployment": "accepted", "endpoint": f"https://{host}/mcp"}

    def set_github(self):
        """Copy GITHUB_CLIENT_ID/SECRET from the ignored .env into protected app settings. Never printed."""
        values = {}
        for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
            key, _, value = line.partition("=")
            if key.strip() in ("GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET") and value.strip():
                values[key.strip()] = value.strip().strip('"').strip("'")
        if len(values) != 2:
            raise ValueError("Add GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to .env first")
        current = self.arm("POST", self.site + "/config/appsettings/list?api-version=2024-04-01")
        props = {**current.get("properties", {}), **values}
        self.arm("PUT", self.site + "/config/appsettings?api-version=2024-04-01", json={"properties": props})
        return {"github_sign_in": "configured", "settings_updated": sorted(values)}

    def deployment_status(self):
        host = self.host().replace(".azurewebsites.net", ".scm.azurewebsites.net")
        response = requests.get(f"https://{host}/api/deployments/latest", headers=self.headers(), timeout=30, allow_redirects=False)
        if response.status_code != 200:
            return {"deployment_status_http": response.status_code}
        value = response.json()
        return {k: value.get(k) for k in ("id", "status", "complete", "active", "start_time", "end_time")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("deploy", "deployment-status", "set-github", "initialize", "publish", "enroll", "drain"))
    args = parser.parse_args()
    operator = Operator()
    if args.command == "deploy":
        result = operator.deploy()
    elif args.command == "deployment-status":
        result = operator.deployment_status()
    elif args.command == "set-github":
        result = operator.set_github()
    else:
        from atlas_mcp.cloud_store import CloudIntake
        store = operator.store()
        if args.command == "initialize":
            store.initialize()
            result = {"initialized": True}
        elif args.command == "publish":
            from atlas_mcp.cloud_publish import publish
            result = publish(store, ROOT / "data/ledger/ledger.db", ROOT / "data/build")
        elif args.command == "enroll":
            c = operator.config
            principal = f'https://login.microsoftonline.com/{c["tenantId"]}/v2.0|{c["operatorPrincipalId"]}'
            p = CloudIntake(store).enroll("lead-codex", "gpt-6", "openai", principal, False, 100)
            result = {k: p[k] for k in ("id", "model", "model_family", "allow_review", "daily_quota")}
        else:
            from atlas_mcp.cloud_worker import pull_and_drain
            result = pull_and_drain(CloudIntake(store), ROOT / "data/contributions/cloud-bridge", ROOT / "data/ledger/ledger.db", limit=25)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
