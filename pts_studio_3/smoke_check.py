import json,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
out=root/'smoke_report.json'
out.unlink(missing_ok=True)
exe=sys.argv[1] if len(sys.argv)>1 else None
command=[exe,'--smoke-test'] if exe else [sys.executable,str(root/'app.pyw'),'--smoke-test']
env=dict(os.environ,PTS_SMOKE_REPORT=str(out))
p=subprocess.run(command,env=env,timeout=60)
if p.returncode:raise RuntimeError(f'GUI process failed: {p.returncode}')
report=json.loads(out.read_text(encoding='utf-8'))
assert report['success'] and report['cells']==256 and report['graph_window'] and report['xdf_loaded'] and report['legacy_0x90'] and report['blank_without_xdf'] and report['native_xdf'],report
print(json.dumps(report,ensure_ascii=True))
