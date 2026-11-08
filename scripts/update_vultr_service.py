import subprocess

path = "/etc/systemd/system/inneros-verified-ops.service"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old_str = "Environment=INNEROS_OPS_TOKEN=inneros-ops-token-bellini-2026"
new_str = (
    "Environment=INNEROS_OPS_TOKEN=sec_ops_vultr_58085a2638f64246547b956c617e6492\n"
    "Environment=AUTH_TOKEN=sec_ops_vultr_58085a2638f64246547b956c617e6492"
)

if old_str in content:
    content = content.replace(old_str, new_str)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated service file with rotated token.")
else:
    print("Service file already updated or pattern not found.")

subprocess.run(["systemctl", "daemon-reload"], check=True)
subprocess.run(["systemctl", "restart", "inneros-verified-ops.service"], check=True)
print("Daemon reloaded and service restarted.")
