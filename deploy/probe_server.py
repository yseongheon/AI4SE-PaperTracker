"""只读探查服务器部署状态（不修改任何东西）。"""
import os
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("8.166.134.107", username="root", password=os.environ["SERVER_PASS"], timeout=20)


def run(cmd):
    _, stdout, stderr = cli.exec_command(cmd, timeout=120)
    out = stdout.read().decode(errors="replace").strip()
    err = stderr.read().decode(errors="replace").strip()
    print(f"$ {cmd}\n{out}\n{err}\n---")
    return out


print("== 1. 项目目录 ==")
run("ls /opt/ai4se-papertracker/ && echo '-- backend:' && ls /opt/ai4se-papertracker/backend/ | head -20")
print("== 2. systemd 服务单元 ==")
run("systemctl cat papertracker.service 2>/dev/null | head -30")
print("== 3. alembic 当前版本 ==")
run("cd /opt/ai4se-papertracker/backend && python -m uv run alembic current 2>&1 | tail -5")
print("== 4. 数据库状态 ==")
run("ls -lh /opt/ai4se-papertracker/data/ 2>/dev/null")
print("== 5. 后端进程/端口 ==")
run("ps aux | grep -E 'uvicorn|uv ' | grep -v grep | head -5; echo '-- port 8000:'; ss -tlnp 2>/dev/null | grep 8000 || netstat -tlnp 2>/dev/null | grep 8000")
print("== 6. 现有前端 dist 时间 ==")
run("ls -la /opt/ai4se-papertracker/frontend/dist/ 2>/dev/null | head -5")

cli.close()
print("PROBE DONE")
