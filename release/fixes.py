# Applied to the reconstructed baseline by build.py.
# The production scope policy correctly rejects Windows AppData. Only the
# legacy test fixture was placing its temporary folder there.
p=APP/'tests/test_ai_organize.py'
s=p.read_text(encoding='utf-8')
s=s.replace('from pathlib import Path','from pathlib import Path\nfrom localstudy.config import WORKSPACE_ROOT',1)
old='        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)'
assert s.count(old)==1
s=s.replace(old,"        base=WORKSPACE_ROOT/'practice'/'_legacy_academic_tests'\n        base.mkdir(parents=True,exist_ok=True)\n        self.temp=TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup)")
p.write_text(s,encoding='utf-8',newline='\n')
