import os
import re
import subprocess
import sys

new_token = os.environ.get("NEW_OPERATOR_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else "")
if not new_token:
    raise ValueError("Provide new token via NEW_OPERATOR_TOKEN environment variable or argument.")

path = "/etc/systemd/system/inneros-verified-ops.service"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace or add INNEROS_OPS_TOKEN and AUTH_TOKEN
content = re.sub(r"Environment=INNEROS_OPS_TOKEN=.*", f"Environment=INNEROS_OPS_TOKEN={new_token}", content)
if "Environment=AUTH_TOKEN=" in content:
    content = re.sub(r"Environment=AUTH_TOKEN=.*", f"Environment=AUTH_TOKEN={new_token}", content)
else:
    content = content.replace(f"Environment=INNEROS_OPS_TOKEN={new_token}", f"Environment=INNEROS_OPS_TOKEN={new_token}\nEnvironment=AUTH_TOKEN={new_token}")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

subprocess.run(["chmod", "600", path], check=True)
subprocess.run(["systemctl", "daemon-reload"], check=True)
subprocess.run(["systemctl", "restart", "inneros-verified-ops.service"], check=True)
print("Updated systemd service with new token, restricted permissions to 600, reloaded daemon, and restarted service.")

