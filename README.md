# Company of Heroes 2 非公式日本語化MOD

**Company of Heroes 2（Steam／Windows 64-bit版）** 向けの非公式日本語化パッチです。
ゲーム内のテキストを日本語に差し替え、日本語フォントを表示できるようにします。
Relic EntertainmentおよびSEGAとは無関係の、非公式ファン制作物です。

> **重要：** このMODには自作の `d3dcompiler_46.dll`（プロキシDLL）が含まれ、ゲーム実行中に一部のコードをメモリ上で書き換えます。ゲームのバージョンによっては起動失敗・クラッシュが起こり得ます。**オンライン対戦やアンチチートへの影響は未検証であり、オンライン使用は推奨しません。** インストール前に必ず以下の注意事項をお読みください。

## 日本語化の内容

- 訳文 **86,079項目**：物語・会話、兵種・装備・戦闘、UIなど
- 日本語対応フォント：Noto Sans JPを用いたUI表示
- ゲーム本体の `.sga` アーカイブや `RelicCoH2.exe` は書き換えません
- 正規にインストールされたゲームから、必要な元データをローカルで読み取って加工します

翻訳はAIを活用して制作し、用語統一・校正・自動チェックを行っています。誤訳、不自然な文章、表示上の問題が残っている可能性があります。

## 対応環境

| 項目 | 必要条件 |
|---|---|
| OS | Windows 10 / 11（64-bit） |
| ゲーム | Steam版 Company of Heroes 2（64-bit） |
| Steamゲーム言語 | **English** |
| Python | **3.10以上**（[公式サイト](https://www.python.org/downloads/)） |

DLLは特定の64-bit版 `RelicCoH2.exe` を対象としています。作者が確認したゲームのビルド識別表示：`warnings.log: exe 0x00005f10:data 0x0e2b5016`。**この表示の一致だけで動作を保証するものではありません。** ゲーム更新後や異なるビルドでの動作は未検証です。

## インストール

1. **SteamとCoH2を終了**します。
2. Steamでゲームの言語を **English** に設定します。
3. Python 3.10以上をインストールします。
4. [Releases](../../releases) から配布ZIPをダウンロードし、**ZIP内のファイル・フォルダをすべて展開**します。
5. `install_ja.bat` をダブルクリックして実行します。必要に応じてゲームのインストール先を入力してください。
6. 処理完了後、まずはオフラインのキャンペーンで表示を確認してください。

元ファイルはゲームのインストール先に `.coh2_ja_backup` としてバックアップされ、変更内容は `coh2_ja_manifest.json` に記録されます。作業途中に作られる `.coh2_ja_tx_backup` や `coh2_ja_journal.json` は、復旧に必要な場合があるため手動で削除しないでください。

**注意：** `Code → Download ZIP` は開発用ファイル一式です。通常利用には上記 **Releasesの配布ZIP** を推奨します。

## アンインストール

1. CoH2を終了します。
2. 配布ZIPに入っている `uninstall_ja.bat` を実行します。
3. バックアップから元のファイルが復元されたことを確認します。

ゲームフォルダを移動した場合、バックアップを削除した場合、ゲームが更新された場合などには復旧が正常に完了しない可能性があります。エラー時は元ファイルやバックアップを手動で削除せず、ログを添えて報告してください。

## 技術的な仕組み・安全性

| 対象 | 処理 |
|---|---|
| `CoH2/Locale/English/RelicCoH2.English.ucs` | 所有者のローカル原本から日本語版テキストを生成して差し替え |
| `CoH2/Archives/UIHigh.sga` | 元アーカイブは**読み取りのみ**。UIデータをローカルで抽出・加工 |
| `coh2ui_redir.gfx` | 日本語フォント用にローカル生成 |
| `d3dcompiler_46.dll` | 自作プロキシDLLを配置し、元DLLを `d3dcompiler_46_orig.dll` として保持 |
| ゲーム実行中のメモリ | フォント用UI読み込み処理をフック（固定オフセット利用） |
| `RelicCoH2.exe` | **書き換えません** |

**DLLの制約：** `src/d3dcompiler_46_proxy.cpp` はゲーム実行ファイルの固定オフセットを参照します。命令列の一致確認はありますが、参照先アドレスの範囲確認は十分でなく、**非対応バージョンで必ず安全にスキップできるとは限りません**。また、ストリーム管理など、長時間動作時の問題がないことも実機では保証されていません。

ウイルス対策ソフトから警告された場合、**ゲームフォルダ全体を除外設定にはしないでください**。DLLのソースコードとハッシュを確認し、不審な場合は導入を中止して報告してください。

### DLLのハッシュ・ソースコード

- 配布DLL：`bin/d3dcompiler_46.dll`
- C++ソース：`src/d3dcompiler_46_proxy.cpp`
- SHA-256：`AE60B1C1C95B77426BE3F2256785949A8C466C7BC98108420AD094B8ECFE3B7F`
- Visual Studio 2022 の **x64 Native Tools Command Prompt** でのビルド例：

```bat
cl /nologo /O2 /LD src\d3dcompiler_46_proxy.cpp /Fe:bin\d3dcompiler_46.dll
```

上記のソース公開やハッシュは、ファイルの検証を助けるものであり、安全性の証明ではありません。ビルド環境の差によって、再ビルド結果のバイナリが完全一致するとは限りません。

## トラブルシューティング

**タイトルロゴで止まり、音だけ鳴る場合**：高リフレッシュレート環境でのゲーム側の問題が疑われる場合があります。Steamの起動オプションで次を試す方法があります。ただし、あらゆる環境での有効性は保証しません。

```
-refresh 60 -nomovies -window -fullwindow
```

まずMODをアンインストールし、元のゲームだけでも同じ現象が出るか確認すると切り分けに役立ちます。

## ファイル構成

```text
CoH2-Japanese-Mod/
├── README.md                      # GitHub向け説明
├── README.txt                     # ZIP向け説明
├── LICENSE                        # 自作プログラムのMITライセンス
├── licenses/OFL.txt               # Noto Sans JPのライセンス
├── .gitignore
├── install_ja.bat
├── uninstall_ja.bat
├── patcher.py
├── src/d3dcompiler_46_proxy.cpp
├── bin/d3dcompiler_46.dll
├── data/translations.json
├── data/noto_fonts.bin
└── tests/test_patcher.py
```

## 開発者向けテスト

```bat
python -B tests\test_patcher.py
```

このテストはファイルの導入・復旧処理を模擬するもので、実際のCoH2を起動して動作保証するものではありません。

## ライセンス・権利について

- `patcher.py`、`src/`、`tests/`、`.bat` 等の**自作プログラム**：MIT License（[LICENSE](LICENSE)）
- `data/noto_fonts.bin`：Noto Sans JP由来。SIL Open Font License 1.1（[licenses/OFL.txt](licenses/OFL.txt)）
- `data/translations.json`：本編テキストの翻訳を含みます。**MITライセンスの対象外**です。原作に由来する著作物の権利は各権利者に帰属します。

このMODは無料・非営利の非公式プロジェクトです。**無料公開や原本アーカイブの不添付は、翻訳文の再配布に関する許諾を意味しません。** 原作の権利者から削除要請等があれば適切に対応します。

## 不具合・翻訳修正の報告

GitHubのIssuesに、ゲームのバージョン、再現手順、エラー内容、該当する文字列IDや画面を添えてください。**個人情報、Steamアカウント情報、キー、ローカルのユーザー名が入ったログはそのまま公開しないでください。**
