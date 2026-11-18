"""Automated safety, crash-recovery, and transaction tests for CoH2 patcher.py."""
import importlib.util, json, os, shutil, struct, sys, tempfile, types

patcher_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'patcher.py')

def load(base):
    spec = importlib.util.spec_from_file_location('coh2_patcher_t', patcher_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.BASE_DIR = base
    return m

def make_minimal_gfx():
    # Minimal valid GFX header (8 bytes) + RECT(1 byte=0) + FrameRate(2) + FrameCount(2) + DefineFont3(id=78) + EndTag(0)
    header = b'GFX\x0e' + b'\x00\x00\x00\x00' + b'\x00' + b'\x00\x00\x01\x00'
    font_payload = struct.pack('<HBBB', 78, 0x8C, 1, 2) + b'PT' + b'\x00' * 10
    font_tag = struct.pack('<HI', (75 << 6) | 0x3F, len(font_payload)) + font_payload
    end_tag = struct.pack('<H', 0)
    raw = header + font_tag + end_tag
    return raw[:4] + struct.pack('<I', len(raw)) + raw[8:]

def setup(trans_dict=None):
    root = tempfile.mkdtemp()
    base = os.path.join(root, 'mod')
    game = os.path.join(root, 'game')
    os.makedirs(os.path.join(base, 'bin'))
    os.makedirs(os.path.join(base, 'data'))
    os.makedirs(os.path.join(game, 'CoH2', 'Locale', 'English'))
    os.makedirs(os.path.join(game, 'CoH2', 'Archives'))

    open(os.path.join(base, 'bin', 'd3dcompiler_46.dll'), 'wb').write(b'PROXY_DLL')
    json.dump(trans_dict or {'1': 'テスト'}, open(os.path.join(base, 'data', 'translations.json'), 'w', encoding='utf-8'))
    with open(os.path.join(base, 'data', 'noto_fonts.bin'), 'wb') as f:
        f.write(b'NJP1' + struct.pack('<II', 4, 4) + b'REGU' + b'BOLD')

    open(os.path.join(game, 'RelicCoH2.exe'), 'wb').write(b'EXE')
    open(os.path.join(game, 'd3dcompiler_46.dll'), 'wb').write(b'ORIG_DLL')
    open(os.path.join(game, 'CoH2', 'Locale', 'English', 'RelicCoH2.English.ucs'), 'wb').write(
        '\ufeff1\tTest\r\n2\tKeep\r\n'.encode('utf-16-le')
    )
    return base, game

def stub_gfx(m):
    orig = make_minimal_gfx()
    m._build_local_gfx = lambda gd, nb: m._patch_coh2ui_gfx_bytes(orig, nb)

class PowerLoss(BaseException): pass

results = {}

# 1. Normal install -> verify -> uninstall restores originals
base, game = setup({'1': '日本語テスト'})
m = load(base); stub_gfx(m); m.install(game)
ucs_now = open(os.path.join(game, 'CoH2', 'Locale', 'English', 'RelicCoH2.English.ucs'), 'rb').read().decode('utf-16-le')
dll_now = open(os.path.join(game, 'd3dcompiler_46.dll'), 'rb').read()
ok1 = ('1\t日本語テスト' in ucs_now) and ('2\tKeep' in ucs_now) and (dll_now == b'PROXY_DLL')
m = load(base); m.uninstall(game)
ucs_rest = open(os.path.join(game, 'CoH2', 'Locale', 'English', 'RelicCoH2.English.ucs'), 'rb').read().decode('utf-16-le')
dll_rest = open(os.path.join(game, 'd3dcompiler_46.dll'), 'rb').read()
results['1 normal install + uninstall'] = (
    ok1 and dll_rest == b'ORIG_DLL' and '1\tTest' in ucs_rest and not os.path.exists(os.path.join(game, 'coh2ui_redir.gfx')),
    {'ok1': ok1, 'dll_rest': dll_rest}
)

# 2. Corrupt manifest must exit(1) without overwriting original backup
base, game = setup()
m = load(base); stub_gfx(m); m.install(game)
open(os.path.join(game, 'coh2_ja_manifest.json'), 'w').write('{broken')
m = load(base); stub_gfx(m)
exited = False
try: m.install(game)
except SystemExit as e: exited = (e.code == 1)
bak_dll = open(os.path.join(game, '.coh2_ja_backup', 'd3dcompiler_46.dll'), 'rb').read()
results['2 corrupt manifest -> exit(1), backup intact'] = (exited and bak_dll == b'ORIG_DLL', {'exited': exited, 'bak_dll': bak_dll})

# 3. Non-object manifest -> exit(1)
open(os.path.join(game, 'coh2_ja_manifest.json'), 'w').write('[1,2,3]')
m = load(base); stub_gfx(m)
exited3 = False
try: m.install(game)
except SystemExit as e: exited3 = (e.code == 1)
results['3 non-object manifest -> exit(1)'] = (exited3, {'exited': exited3})

# 4. Path outside game_dir refused in uninstall
base, game = setup()
m = load(base); stub_gfx(m); m.install(game)
victim = os.path.join(os.path.dirname(game), 'OUTSIDE.txt')
open(victim, 'w').write('keep')
mp = os.path.join(game, 'coh2_ja_manifest.json')
mf = json.load(open(mp, encoding='utf-8'))
mf['installed_files'].append(victim)
json.dump(mf, open(mp, 'w', encoding='utf-8'))
m = load(base)
try: m.uninstall(game)
except SystemExit: pass
results['4a uninstall refuses outside path'] = (os.path.exists(victim), {'victim_exists': os.path.exists(victim)})

# 4b. ..\ traversal refused
mf['installed_files'][-1] = os.path.join(game, '..', 'OUTSIDE.txt')
json.dump(mf, open(mp, 'w', encoding='utf-8'))
m = load(base)
try: m.uninstall(game)
except SystemExit: pass
results['4b uninstall refuses ..\\ traversal'] = (os.path.exists(victim), {'victim_exists': os.path.exists(victim)})

# 5. PowerLoss during install before manifest commit -> rerun + uninstall restores originals
base, game = setup()
m = load(base); stub_gfx(m)
real_wb = m._write_bytes_atomic
def crash_gfx(dst, data, sync=False):
    if dst.endswith('coh2ui_redir.gfx'): raise PowerLoss()
    return real_wb(dst, data, sync=sync)
m._write_bytes_atomic = crash_gfx
try: m.install(game)
except PowerLoss: pass
m = load(base); stub_gfx(m); m.install(game)
m = load(base); m.uninstall(game)
dll_rest5 = open(os.path.join(game, 'd3dcompiler_46.dll'), 'rb').read()
results['5 crash mid-install then rerun+uninstall'] = (dll_rest5 == b'ORIG_DLL', {'dll_rest': dll_rest5})

# 6. PowerLoss right after manifest commit (before cleanup) -> rerun keeps user state & uninstall restores
base, game = setup()
m = load(base); stub_gfx(m)
real_rm = shutil.rmtree
def crash_cleanup(p, *a, **k):
    if '.coh2_ja_tx_backup' in p: raise PowerLoss()
    return real_rm(p, *a, **k)
m.shutil = types.SimpleNamespace(copy2=shutil.copy2, rmtree=crash_cleanup)
try: m.install(game)
except PowerLoss: pass
m = load(base); stub_gfx(m); m.install(game)
m = load(base); m.uninstall(game)
dll_rest6 = open(os.path.join(game, 'd3dcompiler_46.dll'), 'rb').read()
results['6 crash after commit then rerun+uninstall'] = (dll_rest6 == b'ORIG_DLL', {'dll_rest': dll_rest6})

# 7. PowerLoss during uninstall right after restoring backup -> retry completes cleanly
base, game = setup()
m = load(base); stub_gfx(m); m.install(game)
m = load(base)
real_rep = os.replace
cnt = {'n': 0}
def crash_uninst(s, d):
    r = real_rep(s, d)
    if '.coh2_ja_backup' in s:
        cnt['n'] += 1
        if cnt['n'] == 1: raise PowerLoss()
    return r
m.os = types.SimpleNamespace(**{k: getattr(os, k) for k in dir(os) if not k.startswith('__')})
m.os.replace = crash_uninst
try: m.uninstall(game)
except PowerLoss: pass
m = load(base); m.uninstall(game)
dll_rest7 = open(os.path.join(game, 'd3dcompiler_46.dll'), 'rb').read()
results['7 crash mid-uninstall then retry completes'] = (
    dll_rest7 == b'ORIG_DLL' and not os.path.exists(os.path.join(game, 'coh2_ja_manifest.json')),
    {'dll_rest': dll_rest7}
)

# 8. Legacy tx folder (no journal) preserved as _legacy_*
base, game = setup()
m = load(base); stub_gfx(m); m.install(game)
leg = os.path.join(game, '.coh2_ja_tx_backup', 'old')
os.makedirs(leg); open(os.path.join(leg, 'KEEP.txt'), 'w').write('legacy')
m = load(base); stub_gfx(m); m.install(game)
kept = [os.path.join(r, f) for r, _, fs in os.walk(game) for f in fs if f == 'KEEP.txt']
results['8 legacy tx_backup preserved'] = (len(kept) == 1, {'kept': kept})

all_ok = True
for k, (ok, d) in results.items():
    print('PASS' if ok else 'FAIL', k, d)
    if not ok: all_ok = False
sys.exit(0 if all_ok else 1)
