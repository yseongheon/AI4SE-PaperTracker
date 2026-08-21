"""在服务器上按序执行机构数据回填（幂等可重跑）。

顺序：seed 别名库 → Crossref 回填(A会) → arXiv 回填 → canonicalize 统一改写 → 验证。
"""
import os
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("8.166.134.107", username="root", password=os.environ["SERVER_PASS"], timeout=25)


def run(cmd, timeout=1800):
    print(f"\n$ {cmd}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out.strip():
        print(out.rstrip())
    if err.strip():
        print("[stderr]", err.rstrip())
    status = stdout.channel.recv_exit_status()
    if status != 0:
        raise RuntimeError(f"FAILED ({status}): {cmd}\n{err}")
    return out


PY = "/opt/ai4se-papertracker/backend/.venv/bin/python"
BASE = "/opt/ai4se-papertracker/backend"

print("===== 0. 确认脚本存在 =====")
run(f"ls {BASE}/scripts/ | grep -E 'affiliation|canonical|alias'")

print("\n===== 1. seed_institution_aliases（别名库，幂等） =====")
run(f"cd {BASE} && {PY} -m scripts.seed_institution_aliases")

print("\n===== 2. run_backfill_affiliations_crossref（A 会论文，Crossref DOI） =====")
run(f"cd {BASE} && {PY} -m scripts.run_backfill_affiliations_crossref")

print("\n===== 3. run_backfill_affiliations（全库 arXiv 机构，约 20 个请求） =====")
run(f"cd {BASE} && {PY} -m scripts.run_backfill_affiliations")

print("\n===== 4. canonicalize_affiliations（存量值按别名库统一改写） =====")
run(f"cd {BASE} && {PY} -m scripts.canonicalize_affiliations")

print("\n===== 5. 验证：机构覆盖统计 =====")
run(f"{BASE}/.venv/bin/python -c \"from app.db import SessionLocal; from app.models import PaperAuthor; from app.services import institution_service; db=SessionLocal(); total=db.query(PaperAuthor).count(); aff=db.query(PaperAuthor).filter(PaperAuthor.affiliation.isnot(None)).count(); print(f'paper_authors total={total} with_affiliation={aff} coverage={aff/total*100:.1f}%')\"", timeout=120)
run(f"cd {BASE} && {PY} -c \"from app.db import SessionLocal; from app.models import InstitutionAlias; db=SessionLocal(); print('institution_aliases rows:', db.query(InstitutionAlias).count())\"")

cli.close()
print("\nBACKFILL DONE")
