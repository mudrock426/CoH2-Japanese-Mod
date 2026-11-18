================================================================
Company of Heroes 2 日本語化 MOD (v1.0)
================================================================

■ 概要
Steam (64-bit) 版 Company of Heroes 2 を日本語化します。
- 翻訳収録数: 86,079 項目（物語・会話 / 兵種・装備・戦闘 / UI・その他）
- 日本語フォント: Noto Sans JP（2,425グリフ）
- ゲーム本体の原本ファイル（英語原文・UIアーカイブ）は同梱せず、
  導入時にお手元のゲームデータへローカルで安全に適用する設計です。

■ 動作環境・事前準備
- OS: Windows 10 / 11 (64-bit)
- ゲーム: Steam 64-bit 版 Company of Heroes 2（言語設定: English）
  確認済みビルド: RelicCoH2.exe (warnings.log: exe 0x00005f10:data 0x0e2b5016)
  ※ DLL はゲーム内の固定位置を参照します。ゲーム更新や対応外ビルドでは、
     フックの失敗に加え、起動時のクラッシュが起こる可能性があります。
     対応外バージョンで安全に動作する保証はありません。
- ランタイム: Python 3.10 以上（https://www.python.org/ または Microsoft Store）
- オンライン対戦（Automatch）での動作やアカウントへの影響は未確認です。
  安全性を確認できていないため、オンライン使用は推奨しません。

■ 導入方法
1. この ZIP を任意のフォルダにすべて展開してください。
2. Steam で Company of Heroes 2 の言語設定が「English」になっている
   ことを確認してください。
3. 「install_ja.bat」を実行してください。
   （元のファイルは自動的に .coh2_ja_backup へバックアップされます）

■ アンインストール（元の英語に戻す）方法
「uninstall_ja.bat」を実行すると、バックアップから元のファイルが復元され、
追加ファイル・バックアップ・マニフェストがすべて削除されます。

■ 同梱 DLL（bin\d3dcompiler_46.dll）の検証・ビルド情報
- SHA-256: AE60B1C1C95B77426BE3F2256785949A8C466C7BC98108420AD094B8ECFE3B7F
- ソースコード: src\d3dcompiler_46_proxy.cpp
- ビルド方法 (Visual Studio 2022 x64 Native Tools コマンドプロンプト):
  cl /nologo /O2 /LD src\d3dcompiler_46_proxy.cpp /Fe:bin\d3dcompiler_46.dll
- セキュリティソフトで誤検知が疑われる場合は、ゲームフォルダ全体を例外設定に
  するのではなく、同梱のソースコード・ハッシュ値をご確認のうえ詳細をご報告ください。

■ トラブルシューティング
Q. 起動時にタイトルロゴ画面のまま進まない（音だけ鳴る）
A. 144Hz 等の高リフレッシュレートモニターで発生する CoH2 本体の
   既知の不具合です。Steam の起動オプションに以下を追加してください：
   -refresh 60 -nomovies -window -fullwindow

■ ライセンス
- プログラム・スクリプト（patcher.py, d3dcompiler_46_proxy.cpp, tests）:
  MIT License（LICENSE.txt を参照）
- 収録フォントデータ（data\noto_fonts.bin）:
  Noto Sans JP (SIL Open Font License 1.1, licenses\OFL.txt を参照)
================================================================
