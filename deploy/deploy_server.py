"""部署到阿里云服务器：前端 dist + 后端代码 + alembic 迁移 + 重启服务。

前提：本地已生成 deploy/frontend-dist.tar.gz 与 deploy/backend-code.tar.gz。
密码从环境变量 SERVER_PASS 读取（不写死在脚本里）。
"""
import os
import time
import paramiko

HOST, USER = "8.166.134.107", "root"
BASE = "/opt/ai4se-papertracker"
PASS = os.environ["SERVER_PASS"]

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASS, timeout=25)


def run(cmd, check=True, timeout=600):
    print(f"\n$ {cmd}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out.strip():
        print(out.rstrip())
    if err.strip():
        print("[stderr]", err.rstrip())
    status = stdout.channel.recv_exit_status()
    if check and status != 0:
        raise RuntimeError(f"FAILED ({status}): {cmd}\n{err}")
    return out, status


print("========== 1. 备份服务器数据库 + 记录迁移版本 ==========")
run(f"cp {BASE}/data/papers.db {BASE}/data/papers.db.bak.$(date +%Y%m%d_%H%M%S) && ls -la {BASE}/data/*.bak.* | tail -2")
run(f"cd {BASE}/backend && .venv/bin/python -m alembic current 2>&1 | tail -3")

print("========== 2. 上传两个部署包 ==========")
sftp = cli.open_sftp()
for local, remote in [
    ("deploy/frontend-dist.tar.gz", f"{BASE}/frontend-dist.tar.gz"),
    ("deploy/backend-code.tar.gz", f"{BASE}/backend-code.tar.gz"),
]:
    sftp.put(local, remote)
    print(f"uploaded {local} -> {remote}")
sftp.close()

print("========== 3. 解包前端 ==========")
run(f"cd {BASE} && rm -rf frontend/dist && tar xzf frontend-dist.tar.gz -C frontend && ls frontend/dist | head")

print("========== 4. 解包后端代码 ==========")
run(f"cd {BASE} && tar xzf backend-code.tar.gz -C backend && ls backend/app | head -5")

print("========== 5. 跑数据库迁移（alembic upgrade head） ==========")
run(f"cd {BASE}/backend && .venv/bin/python -m alembic upgrade head")
run(f"cd {BASE}/backend && .venv/bin/python -m alembic current 2>&1 | tail -3")

print("========== 6. 重启服务 ==========")
run(f"systemctl restart papertracker")
time.sleep(8)
run(f"systemctl is-active papertracker")
run(f"ps aux | grep uvicorn | grep -v grep | head -2", check=False)

print("========== 7. 本机回环验证 ==========")
run(f"curl -s -o /dev/null -w 'health: %{http_code}\\n' http://127.0.0.1:8000/api/health", check=False)
run(f"curl -s 'http://127.0.0.1:8000/api/stats/institutions?page=1&page_size=3' | head -c 300; echo", check=False)

cli.close()
print("\nDEPLOY SCRIPT DONE")
