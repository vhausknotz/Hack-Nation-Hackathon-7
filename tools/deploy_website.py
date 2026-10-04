"""Deploy the built atlas to its existing free Static Web App.

The deployment credential exists only in a child-process environment. No token
is stored in a file, command argument, Git, or printed CLI output.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.azure_mcp_operator import Operator


def deploy():
    if not (ROOT / "app/dist/index.html").is_file():
        raise ValueError("Build the app before deploying")
    operator = Operator()
    site = (f'/subscriptions/{operator.config["subscriptionId"]}/resourceGroups/rare-disease-atlas'
            '/providers/Microsoft.Web/staticSites/rare-disease-atlas')
    response = operator.arm("POST", site + "/listSecrets?api-version=2022-03-01")
    token = response["properties"]["apiKey"]
    env = {**os.environ, "SWA_CLI_DEPLOYMENT_TOKEN": token}
    try:
        result = subprocess.run(["npx.cmd" if os.name == "nt" else "npx", "--yes", "@azure/static-web-apps-cli",
                                 "deploy", "./dist", "--env", "production", "--no-use-keychain"],
                                cwd=ROOT / "app", env=env, capture_output=True, text=True, timeout=600)
        if result.returncode:
            raise RuntimeError(f"Static website deployment failed (exit {result.returncode}); credential-bearing output suppressed")
        return {"deployed": True, "url": "https://salmon-island-04aa8f603.1.azurestaticapps.net"}
    finally:
        env.pop("SWA_CLI_DEPLOYMENT_TOKEN", None)


if __name__ == "__main__":
    import json
    print(json.dumps(deploy()))
