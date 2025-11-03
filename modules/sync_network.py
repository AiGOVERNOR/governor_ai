import json, requests, os, time
from datetime import datetime

REGISTRY_PATH = os.path.expanduser("~/governor_ai/network/registry.json")

def ping_node(node):
    """Ping a node's /health endpoint and return status."""
    try:
        r = requests.get(f"{node['url'].rstrip('/')}/health", timeout=5)
        if r.status_code == 200 and "ok" in r.text.lower():
            return "active"
        return "unresponsive"
    except Exception:
        return "offline"

def sync_registry():
    """Ping all nodes and update registry.json dynamically."""
    if not os.path.exists(REGISTRY_PATH):
        print("Registry file not found.")
        return

    with open(REGISTRY_PATH, "r") as f:
        registry = json.load(f)

    for node in registry.get("nodes", []):
        status = ping_node(node)
        node["status"] = status
        node["last_ping"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"[{node['name']}] {status}")

    # Save updated registry
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)

    print("Registry sync complete.")

if __name__ == "__main__":
    sync_registry()
