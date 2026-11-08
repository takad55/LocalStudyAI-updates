"""Build v1.1 from the released v1.0 archive and hash-locked reviewable diff."""
from pathlib import Path, PurePosixPath
import base64
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import zipfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'build'
BASE_SHA = '99c5c9f064f6a635ea32afb8b53d7ca92c5cf69b53594303b97b7768a65cb131'
BASE_URL = 'https://github.com/takad55/LocalStudyAI-updates/releases/download/v1.0.0/LocalStudyAI_v1.0.0.lsai'
BUNDLE_SHA = '1dabc5b4f8eb2bd615b9f00c985dc23941cea1a1c8ff979bf0cfd26695f1435a'
VERSION = 'v1.1.0'


def safe_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe package path')
    return path


def make():
    OUT.mkdir(parents=True, exist_ok=True)
    cache = os.environ.get('LOCALSTUDY_BASE_ARCHIVE')
    if cache:
        raw = Path(cache).read_bytes()
    else:
        with urlopen(Request(BASE_URL, headers={'User-Agent': 'LocalStudyAI-reproducible-build'}), timeout=60) as response:
            raw = response.read(20 * 1024 * 1024 + 1)
    if hashlib.sha256(raw).hexdigest() != BASE_SHA:
        raise RuntimeError('Published v1.0 checksum mismatch')
    (OUT / 'base_v1.lsai').write_bytes(raw)
    baseline, app = OUT / 'baseline', OUT / 'app'
    for directory in (baseline, app):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            for relative, expected in manifest['files'].items():
                pp = safe_path(relative)
                content = archive.read('payload/' + relative)
                if hashlib.sha256(content).hexdigest() != expected:
                    raise RuntimeError('Baseline member digest mismatch')
                dest = directory.joinpath(*pp.parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
    encoded = ''.join(p.read_text('ascii').strip() for p in sorted(ROOT.glob('source.*.b64')))
    payload = base64.b64decode(encoded, validate=True)
    if hashlib.sha256(payload).hexdigest() != BUNDLE_SHA:
        raise RuntimeError('Source bundle digest mismatch')
    expected_members = {'changes.patch', 'evaluate.py', 'browser_check.py', 'migration_check.py', 'NOTES.md'}
    with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
        if set(bundle.namelist()) != expected_members or sum(i.file_size for i in bundle.infolist()) > 300000:
            raise RuntimeError('Unexpected source bundle members')
        for name in bundle.namelist():
            content = bundle.read(name)
            content.decode('utf-8')
            (ROOT / name).write_bytes(content)
    patch = (ROOT / 'changes.patch').relative_to(ROOT.parent).as_posix()
    subprocess.run(['git', 'apply', '--check', '--directory=build/app', patch], cwd=ROOT.parent, check=True)
    subprocess.run(['git', 'apply', '--directory=build/app', patch], cwd=ROOT.parent, check=True)
    assert (app / 'VERSION.txt').read_text('utf-8').strip() == VERSION
    assert (app / 'requirements.txt').read_bytes() == (baseline / 'requirements.txt').read_bytes(), 'Runtime dependencies changed'
    files = {}
    permitted = {'VERSION.txt', 'requirements.txt', 'config.json', 'README_はじめに.md', 'README_更新案内.md'}
    for source in sorted(app.rglob('*')):
        if not source.is_file() or '__pycache__' in source.parts or source.suffix == '.pyc':
            continue
        rel = source.relative_to(app).as_posix()
        safe_path(rel)
        if rel.split('/')[0] not in {'localstudy', 'tests', 'samples'} and rel not in permitted:
            raise RuntimeError('Unexpected release member: ' + rel)
        files[rel] = source.read_bytes()
    if len(files) > 250:
        raise RuntimeError('Updater file limit exceeded')
    manifest = {'format': 'localstudy-release-v1', 'app': 'LocalStudyAI', 'version': VERSION,
                'note': '既存機能の分類精度・関連語検索・読取キャッシュとメモリ効率を改善。追加モデル・常駐処理・実行時依存なし。承認と履歴を維持。',
                'files': {p: hashlib.sha256(data).hexdigest() for p, data in files.items()}}
    package = OUT / f'LocalStudyAI_{VERSION}.lsai'
    entries = {'manifest.json': json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'),
               **{'payload/' + p: data for p, data in files.items()}}
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in entries.items():
            info = zipfile.ZipInfo(name, (2026, 11, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, content)
    shutil.copy2(ROOT / 'NOTES.md', OUT / 'NOTES.md')
    shutil.copy2(ROOT / 'changes.patch', OUT / 'changes.patch')
    report = {'version': VERSION, 'files': len(files), 'bytes': package.stat().st_size,
              'sha256': hashlib.sha256(package.read_bytes()).hexdigest(), 'base_sha256': BASE_SHA,
              'source_bundle_sha256': BUNDLE_SHA, 'runtime_dependencies_unchanged': True}
    (OUT / 'build_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    make()
