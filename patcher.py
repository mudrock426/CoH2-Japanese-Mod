"""
Company of Heroes 2 Japanese Localization Patcher (End-User Installer/Uninstaller)
Applies Japanese translations and Noto Sans JP fonts locally using the user's own
game files (RelicCoH2.English.ucs and UIHigh.sga) without redistributing game assets.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid

try:
    import winreg
except ImportError:
    winreg = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BACKUP_DIR_NAME = '.coh2_ja_backup'
TX_BACKUP_DIR_NAME = '.coh2_ja_tx_backup'
MANIFEST_NAME = 'coh2_ja_manifest.json'
JOURNAL_NAME = 'coh2_ja_journal.json'


def _require_inside(path: str, root: str, label: str = 'path') -> str:
    real_root = os.path.realpath(root)
    real_path = os.path.realpath(path)
    try:
        common = os.path.commonpath([real_root, real_path])
    except ValueError:
        print(f'ERROR: 不正なパス ({label}): {path}')
        sys.exit(1)
    if common != real_root or real_path == real_root:
        print(f'ERROR: ゲームフォルダ外のパスを検出したため中止しました ({label}): {path}')
        sys.exit(1)
    return real_path


def _fsync_file(f):
    f.flush()
    os.fsync(f.fileno())


def _write_bytes_atomic(dst_p: str, data: bytes, sync: bool = False):
    os.makedirs(os.path.dirname(dst_p), exist_ok=True)
    tmp_p = dst_p + '.ja_tmp'
    try:
        with open(tmp_p, 'wb') as f:
            f.write(data)
            if sync:
                _fsync_file(f)
        os.replace(tmp_p, dst_p)
    except Exception:
        if os.path.exists(tmp_p):
            try:
                os.remove(tmp_p)
            except OSError:
                pass
        raise


def _write_json_atomic(dst_p: str, obj: dict):
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode('utf-8')
    _write_bytes_atomic(dst_p, data, sync=True)


def _copy_atomic(src_p: str, dst_p: str):
    os.makedirs(os.path.dirname(dst_p), exist_ok=True)
    tmp_p = dst_p + '.ja_tmp'
    try:
        shutil.copy2(src_p, tmp_p)
        os.replace(tmp_p, dst_p)
    except Exception:
        if os.path.exists(tmp_p):
            try:
                os.remove(tmp_p)
            except OSError:
                pass
        raise


def _load_json_object(path: str, label: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            obj = json.load(f)
    except (OSError, ValueError) as e:
        print(f'ERROR: {label} ({path}) を読み込めませんでした ({e})。')
        print('元のファイルのバックアップを守るため、処理を中止しました。')
        sys.exit(1)
    if not isinstance(obj, dict):
        print(f'ERROR: {label} ({path}) の形式が不正です（JSON オブジェクトではありません）。')
        print('元のファイルのバックアップを守るため、処理を中止しました。')
        sys.exit(1)
    return obj


def _validate_str_list(obj: dict, key: str, root: str, label: str) -> list[str]:
    val = obj.get(key, [])
    if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
        print(f'ERROR: {label} の {key} が不正です。処理を中止しました。')
        sys.exit(1)
    return [_require_inside(x, root, f'{label}.{key}') for x in val]


def _validate_manifest(manifest: dict, game_dir: str) -> dict:
    _validate_str_list(manifest, 'installed_files', game_dir, MANIFEST_NAME)
    _validate_str_list(manifest, 'backed_up_files', game_dir, MANIFEST_NAME)
    if 'restoring' in manifest:
        _validate_str_list(manifest, 'restoring', game_dir, MANIFEST_NAME)
    if 'txid' in manifest and manifest['txid'] is not None and not isinstance(manifest['txid'], str):
        print(f'ERROR: {MANIFEST_NAME} の txid が不正です。')
        sys.exit(1)
    return manifest


def _validate_journal(journal: dict, game_dir: str) -> dict:
    txid = journal.get('txid')
    if not isinstance(txid, str) or not txid:
        print(f'ERROR: {JOURNAL_NAME} の txid が不正です。')
        sys.exit(1)
    _validate_str_list(journal, 'created', game_dir, JOURNAL_NAME)
    _validate_str_list(journal, 'backed_up', game_dir, JOURNAL_NAME)
    _validate_str_list(journal, 'tx_backed_up', game_dir, JOURNAL_NAME)
    backup_dir = os.path.join(game_dir, BACKUP_DIR_NAME)
    stale_baks = journal.get('stale_baks', [])
    if not isinstance(stale_baks, list) or not all(isinstance(x, str) for x in stale_baks):
        print(f'ERROR: {JOURNAL_NAME} の stale_baks が不正です。')
        sys.exit(1)
    for sb in stale_baks:
        _require_inside(sb, backup_dir, f'{JOURNAL_NAME}.stale_baks')
    return journal


def find_game_dir() -> str | None:
    candidates = []
    if winreg is not None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as k:
                steam_path, _ = winreg.QueryValueEx(k, 'SteamPath')
                if steam_path and isinstance(steam_path, str):
                    steam_path = steam_path.replace('/', '\\')
                    candidates.append(os.path.join(steam_path, 'steamapps', 'common', 'Company of Heroes 2'))
                    vdf = os.path.join(steam_path, 'steamapps', 'libraryfolders.vdf')
                    if os.path.isfile(vdf):
                        with open(vdf, 'r', encoding='utf-8', errors='ignore') as f:
                            for m in re.finditer(r'"path"\s+"([^"]+)"', f.read()):
                                lib = m.group(1).replace('\\\\', '\\')
                                candidates.append(os.path.join(lib, 'steamapps', 'common', 'Company of Heroes 2'))
        except OSError:
            pass
    candidates.extend([
        r'C:\Program Files (x86)\Steam\steamapps\common\Company of Heroes 2',
        r'D:\SteamLibrary\steamapps\common\Company of Heroes 2',
        r'E:\SteamLibrary\steamapps\common\Company of Heroes 2',
    ])
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, 'RelicCoH2.exe')):
            return c
    return None


def _cleanup_committed_tx(game_dir: str, journal: dict | None):
    backup_dir = os.path.join(game_dir, BACKUP_DIR_NAME)
    tx_backup_dir = os.path.join(game_dir, TX_BACKUP_DIR_NAME)
    journal_path = os.path.join(game_dir, JOURNAL_NAME)
    if journal:
        for sb in journal.get('stale_baks', []):
            _require_inside(sb, backup_dir, 'stale_baks')
            if os.path.exists(sb):
                try:
                    os.remove(sb)
                except OSError:
                    pass
    if os.path.isdir(tx_backup_dir):
        shutil.rmtree(tx_backup_dir, ignore_errors=True)
    if os.path.exists(journal_path):
        try:
            os.remove(journal_path)
        except OSError:
            pass


def _rollback_tx(game_dir: str, journal: dict):
    backup_dir = os.path.join(game_dir, BACKUP_DIR_NAME)
    tx_backup_dir = os.path.join(game_dir, TX_BACKUP_DIR_NAME)
    journal_path = os.path.join(game_dir, JOURNAL_NAME)

    if os.path.isdir(tx_backup_dir):
        for dp, _, fns in os.walk(tx_backup_dir):
            for fn in fns:
                tx_p = os.path.join(dp, fn)
                rel = os.path.relpath(tx_p, tx_backup_dir)
                dst_p = _require_inside(os.path.join(game_dir, rel), game_dir, 'tx_restore')
                os.makedirs(os.path.dirname(dst_p), exist_ok=True)
                os.replace(tx_p, dst_p)
        shutil.rmtree(tx_backup_dir, ignore_errors=True)

    for cp in journal.get('created', []):
        cp_real = _require_inside(cp, game_dir, 'journal.created')
        if os.path.exists(cp_real):
            try:
                os.remove(cp_real)
            except OSError:
                pass

    for bp in journal.get('backed_up', []):
        bp_real = _require_inside(bp, game_dir, 'journal.backed_up')
        rel = os.path.relpath(bp_real, game_dir)
        bak_p = _require_inside(os.path.join(backup_dir, rel), backup_dir, 'backup_restore')
        if os.path.exists(bak_p):
            os.makedirs(os.path.dirname(bp_real), exist_ok=True)
            os.replace(bak_p, bp_real)

    if os.path.exists(journal_path):
        try:
            os.remove(journal_path)
        except OSError:
            pass


def recover_interrupted_install(game_dir: str):
    manifest_path = os.path.join(game_dir, MANIFEST_NAME)
    journal_path = os.path.join(game_dir, JOURNAL_NAME)
    tx_backup_dir = os.path.join(game_dir, TX_BACKUP_DIR_NAME)

    manifest = None
    if os.path.exists(manifest_path):
        manifest = _validate_manifest(_load_json_object(manifest_path, MANIFEST_NAME), game_dir)

    if os.path.exists(journal_path):
        journal = _validate_journal(_load_json_object(journal_path, JOURNAL_NAME), game_dir)
        if manifest and manifest.get('txid') == journal.get('txid'):
            print('[!] 前回の処理は確定済みで後片付けのみ残っていたため、後片付けを完了します...')
            _cleanup_committed_tx(game_dir, journal)
        else:
            print('[!] 前回の処理が未確定のまま中断されていたため、元の状態へ復元します...')
            _rollback_tx(game_dir, journal)
    elif os.path.isdir(tx_backup_dir):
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        legacy_dir = os.path.join(game_dir, f'.coh2_ja_tx_backup_legacy_{ts}')
        os.replace(tx_backup_dir, legacy_dir)
        print(f'[!] 旧版の一時退避フォルダを保管しました: {legacy_dir}')


def _patch_coh2ui_gfx_bytes(orig_gfx: bytes, noto_bin_path: str) -> bytes:
    with open(noto_bin_path, 'rb') as f:
        magic = f.read(4)
        if magic != b'NJP1':
            raise ValueError('Invalid noto_fonts.bin header')
        reg_len, bold_len = struct.unpack('<II', f.read(8))
        payload_reg = f.read(reg_len)
        payload_bold = f.read(bold_len)

    pos = 8
    nbits = orig_gfx[pos] >> 3
    rect_bytes = (5 + 4 * nbits + 7) // 8
    header_end = pos + rect_bytes + 4

    def make_tag(ttype, tdata):
        tlen = len(tdata)
        if tlen < 0x3F:
            return struct.pack('<H', (ttype << 6) | tlen) + tdata
        return struct.pack('<HI', (ttype << 6) | 0x3F, tlen) + tdata

    chunks = [orig_gfx[:header_end]]
    cur = header_end
    while cur + 2 <= len(orig_gfx):
        tag_header = struct.unpack('<H', orig_gfx[cur:cur + 2])[0]
        cur += 2
        tag_type = tag_header >> 6
        tag_len = tag_header & 0x3F
        if tag_len == 0x3F:
            tag_len = struct.unpack('<I', orig_gfx[cur:cur + 4])[0]
            cur += 4
        tdata = orig_gfx[cur:cur + tag_len]
        cur += tag_len

        if tag_type == 75 and struct.unpack('<H', tdata[0:2])[0] != 4645:
            orig_flags = tdata[2]
            is_bold = bool(orig_flags & 0x01)
            new_flags = 0x8C | (orig_flags & 0x03)
            orig_name_len = tdata[4]
            orig_name = tdata[5:5 + orig_name_len]
            payload = payload_bold if is_bold else payload_reg
            new_tdata = tdata[0:2] + bytes([new_flags, 3, orig_name_len]) + orig_name + payload
            chunks.append(make_tag(tag_type, new_tdata))
        else:
            chunks.append(make_tag(tag_type, tdata))
        if tag_type == 0:
            break

    out_bytes = b''.join(chunks)
    return out_bytes[:4] + struct.pack('<I', len(out_bytes)) + out_bytes[8:]


def _build_local_gfx(game_dir: str, noto_bin_path: str) -> bytes:
    archive_exe = os.path.join(game_dir, 'Archive.exe')
    uihigh_sga = os.path.join(game_dir, 'CoH2', 'Archives', 'UIHigh.sga')
    if not os.path.isfile(archive_exe) or not os.path.isfile(uihigh_sga):
        raise FileNotFoundError('Archive.exe または CoH2\\Archives\\UIHigh.sga が見つかりません')

    tmp_dir = tempfile.mkdtemp(prefix='coh2_ja_gfx_')
    try:
        res = subprocess.run(
            [archive_exe, '-a', uihigh_sga, '-e', tmp_dir],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        gfx_path = os.path.join(tmp_dir, 'ui', 'bin', 'coh2ui.gfx')
        if res.returncode != 0 or not os.path.isfile(gfx_path):
            raise RuntimeError('UIHigh.sga からの coh2ui.gfx 抽出に失敗しました')
        with open(gfx_path, 'rb') as f:
            orig_gfx = f.read()
        return _patch_coh2ui_gfx_bytes(orig_gfx, noto_bin_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _build_local_ucs(orig_ucs_bytes: bytes, trans_path: str) -> bytes:
    with open(trans_path, 'r', encoding='utf-8') as f:
        translations = json.load(f)
    text = orig_ucs_bytes.decode('utf-16-le')
    nl = '\r\n' if '\r\n' in text else '\n'
    out_lines = []
    for line in text.split(nl):
        if '\t' in line:
            k, _ = line.split('\t', 1)
            clean_k = k.lstrip('\ufeff')
            if clean_k in translations:
                prefix = '\ufeff' if k.startswith('\ufeff') else ''
                line = f'{prefix}{clean_k}\t{translations[clean_k]}'
        out_lines.append(line)
    return nl.join(out_lines).encode('utf-16-le')


def install(game_dir: str):
    game_dir = os.path.realpath(game_dir)
    backup_dir = os.path.join(game_dir, BACKUP_DIR_NAME)
    tx_backup_dir = os.path.join(game_dir, TX_BACKUP_DIR_NAME)
    manifest_path = os.path.join(game_dir, MANIFEST_NAME)
    journal_path = os.path.join(game_dir, JOURNAL_NAME)

    # Step 1: Validate existing manifest/journal & recover interrupted run
    recover_interrupted_install(game_dir)

    prev_installed = set()
    backed_up = set()
    if os.path.exists(manifest_path):
        old_manifest = _validate_manifest(_load_json_object(manifest_path, MANIFEST_NAME), game_dir)
        prev_installed = set(os.path.realpath(p) for p in old_manifest.get('installed_files', []))
        backed_up = set(os.path.realpath(p) for p in old_manifest.get('backed_up_files', []))

    txid = str(uuid.uuid4())
    journal = {
        'txid': txid,
        'created': [],
        'backed_up': [],
        'tx_backed_up': [],
        'stale_baks': [],
    }
    _write_json_atomic(journal_path, journal)

    installed = set()

    def save_journal():
        _write_json_atomic(journal_path, journal)

    def prepare_write(dst_p: str):
        dst_real = _require_inside(dst_p, game_dir, 'install_target')
        if not os.path.exists(dst_real):
            if dst_real not in journal['created']:
                journal['created'].append(dst_real)
                save_journal()
            return dst_real

        if dst_real not in prev_installed and dst_real not in backed_up:
            rel = os.path.relpath(dst_real, game_dir)
            bak_p = _require_inside(os.path.join(backup_dir, rel), backup_dir, 'backup_target')
            if not os.path.exists(bak_p):
                _copy_atomic(dst_real, bak_p)
            backed_up.add(dst_real)
            if dst_real not in journal['backed_up']:
                journal['backed_up'].append(dst_real)
                save_journal()
        elif dst_real in prev_installed and dst_real not in journal['tx_backed_up']:
            rel = os.path.relpath(dst_real, game_dir)
            tx_p = _require_inside(os.path.join(tx_backup_dir, rel), tx_backup_dir, 'tx_target')
            _copy_atomic(dst_real, tx_p)
            journal['tx_backed_up'].append(dst_real)
            save_journal()
        return dst_real

    try:
        print('[1/3] 原本ファイルのバックアップとテキスト差分適用を準備しています...')
        dll_src = os.path.join(BASE_DIR, 'bin', 'd3dcompiler_46.dll')
        trans_src = os.path.join(BASE_DIR, 'data', 'translations.json')
        noto_src = os.path.join(BASE_DIR, 'data', 'noto_fonts.bin')

        # Target paths
        dll_dst = os.path.join(game_dir, 'd3dcompiler_46.dll')
        orig_dll_dst = os.path.join(game_dir, 'd3dcompiler_46_orig.dll')
        ucs_dst = os.path.join(game_dir, 'CoH2', 'Locale', 'English', 'RelicCoH2.English.ucs')
        gfx_dst = os.path.join(game_dir, 'coh2ui_redir.gfx')

        # Prepare original DLL copy for proxy forwarding
        dll_real = prepare_write(dll_dst)
        bak_dll = _require_inside(os.path.join(backup_dir, 'd3dcompiler_46.dll'), backup_dir, 'bak_dll')
        if not os.path.exists(bak_dll):
            raise FileNotFoundError('元の d3dcompiler_46.dll のバックアップが見つかりません')
        orig_dll_real = prepare_write(orig_dll_dst)
        _copy_atomic(bak_dll, orig_dll_real)
        installed.add(orig_dll_real)

        # Install proxy DLL
        _copy_atomic(dll_src, dll_real)
        installed.add(dll_real)

        # Patch UCS from backed-up original
        ucs_real = prepare_write(ucs_dst)
        bak_ucs = _require_inside(
            os.path.join(backup_dir, 'CoH2', 'Locale', 'English', 'RelicCoH2.English.ucs'),
            backup_dir, 'bak_ucs'
        )
        ucs_source_path = bak_ucs if os.path.exists(bak_ucs) else ucs_real
        with open(ucs_source_path, 'rb') as f:
            orig_ucs_bytes = f.read()
        print('[2/3] 日本語テキスト (.ucs) を構築しています...')
        new_ucs_bytes = _build_local_ucs(orig_ucs_bytes, trans_src)
        _write_bytes_atomic(ucs_real, new_ucs_bytes)
        installed.add(ucs_real)

        # Build local coh2ui_redir.gfx from user's UIHigh.sga + Noto Sans JP
        print('[3/3] ローカル UIHigh.sga から Noto Sans JP フォント適用済み UI を生成しています...')
        gfx_bytes = _build_local_gfx(game_dir, noto_src)
        gfx_real = prepare_write(gfx_dst)
        _write_bytes_atomic(gfx_real, gfx_bytes)
        installed.add(gfx_real)

        # Handle stale files from previous install
        for stale_p in sorted(prev_installed - installed):
            stale_real = _require_inside(stale_p, game_dir, 'stale_target')
            if os.path.exists(stale_real):
                prepare_write(stale_real)
                os.remove(stale_real)
            if stale_real in backed_up:
                rel = os.path.relpath(stale_real, game_dir)
                bak_p = _require_inside(os.path.join(backup_dir, rel), backup_dir, 'stale_bak')
                if os.path.exists(bak_p):
                    _copy_atomic(bak_p, stale_real)
                    journal['stale_baks'].append(bak_p)
                    save_journal()
                    backed_up.discard(stale_real)

        # Commit manifest
        _write_json_atomic(manifest_path, {
            'txid': txid,
            'game_dir': game_dir,
            'installed_files': sorted(installed),
            'backed_up_files': sorted(backed_up),
        })
    except Exception:
        _rollback_tx(game_dir, journal)
        raise

    # Cleanup after commit
    _cleanup_committed_tx(game_dir, journal)
    print(f'完了！{len(installed)} 個のファイルを適用しました。')
    print('Steam の言語設定が English になっていることを確認して起動してください。')


def uninstall(game_dir: str):
    game_dir = os.path.realpath(game_dir)
    backup_dir = os.path.join(game_dir, BACKUP_DIR_NAME)
    manifest_path = os.path.join(game_dir, MANIFEST_NAME)

    recover_interrupted_install(game_dir)

    if not os.path.exists(manifest_path):
        print('coh2_ja_manifest.json が見つかりません。アンインストール対象はありません。')
        return

    manifest = _validate_manifest(_load_json_object(manifest_path, MANIFEST_NAME), game_dir)
    files = set(_validate_str_list(manifest, 'installed_files', game_dir, MANIFEST_NAME))
    backed_up = set(_validate_str_list(manifest, 'backed_up_files', game_dir, MANIFEST_NAME))
    restoring = set(_validate_str_list(manifest, 'restoring', game_dir, MANIFEST_NAME)) if 'restoring' in manifest else set()

    remaining_files = set(files)
    remaining_backed_up = set(backed_up)
    missing = set()
    removed = 0
    restored = 0
    missing_backups = 0

    def save_progress():
        manifest['installed_files'] = sorted(remaining_files)
        manifest['backed_up_files'] = sorted(remaining_backed_up)
        manifest['restoring'] = sorted(restoring)
        _write_json_atomic(manifest_path, manifest)

    try:
        for p in sorted(files | backed_up):
            p_real = _require_inside(p, game_dir, 'uninstall_target')
            if p_real in backed_up:
                rel = os.path.relpath(p_real, game_dir)
                bak_p = _require_inside(os.path.join(backup_dir, rel), backup_dir, 'uninstall_backup')
                if not os.path.exists(bak_p):
                    if p_real in restoring:
                        # Already restored right before previous interruption
                        restored += 1
                        restoring.discard(p_real)
                        remaining_backed_up.discard(p_real)
                        remaining_files.discard(p_real)
                        continue
                    print(f'[WARNING] バックアップが見つかりません: {p_real}（現在のファイルを保護するため削除しません）')
                    missing_backups += 1
                    missing.add(p_real)
                    continue
                restoring.add(p_real)
                save_progress()
                os.makedirs(os.path.dirname(p_real), exist_ok=True)
                os.replace(bak_p, p_real)
                restored += 1
                restoring.discard(p_real)
                remaining_backed_up.discard(p_real)
                save_progress()
            elif os.path.exists(p_real):
                os.remove(p_real)
                removed += 1
            remaining_files.discard(p_real)
            save_progress()
    except Exception:
        try:
            save_progress()
        except OSError:
            pass
        raise

    if missing_backups == 0:
        if os.path.isdir(backup_dir):
            shutil.rmtree(backup_dir, ignore_errors=True)
        if os.path.exists(manifest_path):
            os.remove(manifest_path)
        print(f'アンインストール完了: {removed} 個のファイルを削除し、{restored} 個の原本ファイルを復元しました。')
    else:
        remaining_files &= missing
        remaining_backed_up &= missing
        save_progress()
        print(f'一部のみ復元しました（削除: {removed}, 復元: {restored}, バックアップ欠損: {missing_backups}）。')


def main():
    ap = argparse.ArgumentParser(description='Company of Heroes 2 Japanese Localization Patcher')
    ap.add_argument('action', choices=['install', 'uninstall'])
    ap.add_argument('--game-dir', help='Path to Company of Heroes 2 folder (auto-detected if omitted)')
    args = ap.parse_args()

    game_dir = args.game_dir or find_game_dir()
    if not game_dir:
        game_dir = input('Company of Heroes 2 フォルダのパスを入力してください: ').strip().strip('"')
    if not os.path.isfile(os.path.join(game_dir, 'RelicCoH2.exe')):
        print(f'ERROR: RelicCoH2.exe が見つかりません: {game_dir}')
        sys.exit(1)

    if args.action == 'install':
        install(game_dir)
    else:
        uninstall(game_dir)


if __name__ == '__main__':
    main()
