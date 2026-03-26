# video2timeline

手元にある動画ファイルを、ChatGPT などの LLM で読みやすいタイムライン資料に変換するローカルアプリです。

[English README](README.md) | [サンプルタイムライン](docs/examples/sample-timeline.ja.md) | [第三者ライセンス](THIRD_PARTY_NOTICES.md) | [モデルと実行環境](MODEL_AND_RUNTIME_NOTES.md) | [安全性メモ](docs/SECURITY_AND_SAFETY.md) | [公開前チェック](docs/PUBLIC_RELEASE_CHECKLIST.md) | [ライセンス](LICENSE)

このアプリの目的は、今まで手元に溜まっていた動画ファイルを、あとから LLM で整理・分析しやすいテキスト資料に変えることです。

例えば次のような用途を想定しています。

- 会議の振り返り
- 家族や友人との会話の見直し
- スマホ動画や画面録画の整理
- ChatGPT に渡す ZIP 資料の作成

## スクリーンショット

### Settings

![Settings](docs/screenshots/settings.png)

### New Job

![New Job](docs/screenshots/new-job.png)

### Jobs

![Jobs](docs/screenshots/jobs.png)

### Run Details

![Run Details](docs/screenshots/run-details.png)

## できること

1 回のジョブで、主に次のものを作ります。

- 動画ごとの `timeline.md`
- 生の文字起こし (`raw.json`, `raw.md`)
- 画面メモと画面差分
- 元動画時刻を保つための `cut_map.json`
- LLM 向けの `batch-*.md` と `timeline_index.jsonl`

基本の流れは次のとおりです。

1. ローカルで実行する
2. 出力を確認する
3. 完了したジョブを ZIP でダウンロードする
4. その ZIP を ChatGPT などへアップロードする

## サンプルタイムライン

公開用サンプルは、実際に生成したタイムラインから名前などを伏せて作っています。

全文: [docs/examples/sample-timeline.ja.md](docs/examples/sample-timeline.ja.md)

## 主な特徴

- 通常はローカル処理です
- CPU と GPU の両方に対応しています
- 無音カットを使っても、最終タイムラインは元の動画時刻に合わせます
- OCR と画面説明は、画面変化が大きいときだけ出します
- 話者分離は Hugging Face token と承認があるときだけ有効になります
- GUI は 1 件ずつ安全に実行する設計です

## 使い方

- 通常利用は GUI が主です
- CLI もありますが、主に自動化や詳細確認向けです

## 必要なもの

- Windows または macOS
- Docker Desktop
- 初回のモデル取得用インターネット接続
- `pyannote` の話者分離を使うなら Hugging Face token
- `pyannote` の承認
- GPU を使うなら NVIDIA GPU と Docker GPU 対応

## クイックスタート

Windows:

```powershell
.\start.bat
```

macOS:

```bash
./start.command
```

その後の流れ:

1. `start.bat` / `start.command` が `.env` を自動作成します
2. `http://localhost:38090` を開きます
3. 最初に `Settings` を開きます
4. `CPU` または `GPU` を選びます
5. 必要なら Hugging Face token を保存します
6. 必要なモデルの承認を行います
7. 動画ファイルまたはフォルダを選びます
8. ジョブを開始します
9. 完了した ZIP をダウンロードします

`start.bat` / `start.command` は、最初に Microsoft Edge、Google Chrome、Brave、Chromium のアプリモードで開こうとします。見つからない場合は通常の既定ブラウザで開きます。

停止:

```powershell
.\stop.bat
```

アンインストール:

```powershell
.\uninstall.bat
```

`uninstall` は確認付きです。Docker のコンテナ、イメージ、ネットワーク、一時ボリュームを削除します。保存済みの Hugging Face token と設定を含む `app-data` ボリュームは別確認で削除できます。必要なら `.env` も追加で削除できます。

## 対応入力形式

主な対応形式:

- `.mp4`
- `.mov`
- `.m4v`
- `.avi`
- `.mkv`
- `.webm`

実際の読み込み可否は、ランタイム内の `ffmpeg` に依存します。

## 言語

アプリの言語は `Settings` で変更できます。

現在の対応言語:

- `ja`
- `en`
- `zh-CN`
- `zh-TW`
- `ko`
- `es`
- `fr`
- `de`
- `pt`

初回起動時の既定値は英語です。変更内容は cookie に保存されます。

## CLI

worker 側には CLI もあります。

主なコマンド:

- `settings status`
- `settings save`
- `jobs create`
- `jobs list`
- `jobs show`
- `jobs run`
- `jobs archive`
- `scan`
- `compare-images`
- `run-job`
- `daemon`

例:

```powershell
$env:PYTHONPATH=".\worker\src"
python -m video2timeline_worker settings status
python -m video2timeline_worker settings save --token hf_xxx --terms-confirmed
python -m video2timeline_worker jobs create --file C:\path\to\clip.mp4
python -m video2timeline_worker jobs create --directory C:\path\to\folder
python -m video2timeline_worker jobs list
python -m video2timeline_worker jobs archive --job-id run-YYYYMMDD-HHMMSS-xxxx
```

GUI と同じように ZIP 化したい場合は、完了後に `jobs archive` を使います。
