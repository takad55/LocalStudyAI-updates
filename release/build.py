"""Reproducible release build; source and fixtures only, never user workspace."""
from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import os
import shutil
import stat
import zipfile
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'build'
APP=OUT/'app'
BASE_SHA='3bb35f76ab54cfdffe2dc6a67d553bc35a1926f3044824b971102dde5f68fcfe'
BASE_URL='https://github.com/takad55/LocalStudyAI-updates/releases/download/v0.4.0/LocalStudyAI_v0.4.0.lsai'
VERSION='v1.0.0'


def replace_once(path,old,new):
    value=path.read_text(encoding='utf-8')
    if value.count(old)!=1:raise RuntimeError(f'Unexpected base structure: {path.name}: {old[:60]!r}')
    path.write_text(value.replace(old,new,1),encoding='utf-8',newline='\n')


def make():
    OUT.mkdir(parents=True,exist_ok=True)
    cached=os.environ.get('LOCALSTUDY_BASE_ARCHIVE')
    if cached: raw=Path(cached).read_bytes()
    else:
        with urlopen(Request(BASE_URL,headers={'User-Agent':'LocalStudyAI-reproducible-build'}),timeout=45) as response:raw=response.read(20*1024*1024+1)
    if hashlib.sha256(raw).hexdigest()!=BASE_SHA:raise RuntimeError('Baseline checksum mismatch; refusing build')
    if APP.exists():shutil.rmtree(APP)
    APP.mkdir()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        manifest=json.loads(z.read('manifest.json'))
        for relative,digest in manifest['files'].items():
            pp=PurePosixPath(relative)
            if pp.is_absolute() or '..' in pp.parts or '\\' in relative:raise RuntimeError('Invalid baseline path')
            data=z.read('payload/'+relative)
            if hashlib.sha256(data).hexdigest()!=digest:raise RuntimeError('Baseline member checksum mismatch')
            dest=APP.joinpath(*pp.parts);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    for source in sorted((ROOT/'overlay').rglob('*')):
        if not source.is_file():continue
        relative=source.relative_to(ROOT/'overlay')
        if '__pycache__' in relative.parts or source.suffix=='.pyc':continue
        dest=APP/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(source.read_bytes())
    web=APP/'localstudy/webapp.py'
    replace_once(web,'from localstudy import update_manager, remote_updates','from localstudy import update_manager, remote_updates\nfrom localstudy.workbench import Workbench, public_report')
    replace_once(web,'        self.pending_legacy = None\n','        self.pending_legacy = None\n        self.workbench = Workbench(self)\n')
    replace_once(web,'        self.scope = scope\n','        self.scope = scope\n        self.workbench.report = None\n')
    replace_once(web,'    def refresh(self):\n','    def refresh(self):\n        self.workbench.report = None\n')
    replace_once(web,"            'version': VERSION, 'token': self.token, 'root': selected,","            'version': VERSION, 'token': self.token, 'root': selected,\n            'workbench': {'report': public_report(self.workbench.report)},")
    replace_once(web,"        if name == 'choose':", "        if name.startswith('wb_'):\n            return self.workbench.run(name, args)\n        if self.workbench.jobs.active() and name not in ('history', 'history_details', 'ollama_status', 'open'):\n            raise ClientInputError('調査中です。完了または中断後に操作してください。')\n        if name == 'choose':")
    replace_once(web,"'/assets/styles.css': ('styles.css', 'text/css; charset=utf-8')", "'/assets/styles.css': ('styles.css', 'text/css; charset=utf-8'),\n                 '/assets/workbench.js': ('workbench.js', 'text/javascript; charset=utf-8'),\n                 '/assets/workbench.css': ('workbench.css', 'text/css; charset=utf-8')")
    replace_once(web,'                with self.server.app.lock:\n                    Thread(target=self.server.shutdown',"                with self.server.app.lock:\n                    if self.server.app.workbench.jobs.active():\n                        raise ClientInputError('調査を中断して停止を確認してから終了してください。')\n                    Thread(target=self.server.shutdown")
    html=APP/'localstudy/webui/index.html'
    replace_once(html,'  <script src="/assets/app.js" defer></script>','  <script src="/assets/app.js" defer></script>\n  <script src="/assets/workbench.js" defer></script>\n  <link rel="stylesheet" href="/assets/workbench.css">')
    js=APP/'localstudy/webui/app.js'
    replace_once(js,'  renderFiles();renderPlan();renderDuplicates();','  renderFiles();renderPlan();renderDuplicates();\n  if(window.renderWorkbench)window.renderWorkbench();')
    # Keep legacy screens accessible; update obsolete limitations in the settings copy.
    text=html.read_text('utf-8').replace('未使用ファイルの判定・ChatGPTへの自動送信・kibaco連携は未実装です。','不要候補の確認・相談文の作成は「まとめて整理」で利用できます。ChatGPTへの自動送信・kibaco連携は対象外です。')
    html.write_text(text,encoding='utf-8',newline='\n')
    (APP/'VERSION.txt').write_text(VERSION+'\n',encoding='utf-8',newline='\n')
    if (ROOT/'fixes.py').is_file():
        namespace={'APP':APP}
        exec(compile((ROOT/'fixes.py').read_text('utf-8'),'release/fixes.py','exec'),namespace)
    files={}
    for p in sorted(APP.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
        rel=p.relative_to(APP).as_posix()
        if rel.split('/')[0] not in {'localstudy','tests','samples'} and rel not in {'VERSION.txt','requirements.txt','config.json','README_はじめに.md','README_更新案内.md'}:raise RuntimeError('Unexpected package file: '+rel)
        files[rel]=p.read_bytes()
    if len(files)>250:raise RuntimeError('Updater member limit exceeded')
    doc={'format':'localstudy-release-v1','app':'LocalStudyAI','version':VERSION,'note':'統合整理画面、不要候補、講義回別分類、資料横断検索・出典付き回答・一括要約、相談文と回答取り込み、進捗・中断。既存の承認付き操作・履歴・更新を維持。','files':{p:hashlib.sha256(data).hexdigest() for p,data in files.items()}}
    output=OUT/f'LocalStudyAI_{VERSION}.lsai'
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        entries={'manifest.json':json.dumps(doc,ensure_ascii=False,indent=2).encode('utf-8'),**{'payload/'+p:data for p,data in files.items()}}
        for p,data in entries.items():
            info=zipfile.ZipInfo(p,(2026,11,9,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(stat.S_IFREG|0o644)<<16
            z.writestr(info,data)
    print('Built',output.name,'files',len(files),'bytes',output.stat().st_size,'sha256',hashlib.sha256(output.read_bytes()).hexdigest())

if __name__=='__main__':make()
