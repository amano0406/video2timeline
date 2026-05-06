# TimelineForVideo

`TimelineForVideo` は、動画ファイルを読み取り専用入力として扱い、
レビュー用のタイムライン証跡パッケージをローカルで生成する
Docker-first CLIです。

旧実装はv1の前提ではありません。このリポジトリはクリーンリビルドです。

## クイックスタート

Windows PowerShellで実行します。

```powershell
cd C:\apps\TimelineForVideo
.\start.ps1
.\cli.ps1 health
.\cli.ps1 settings init
.\cli.ps1 settings save --input-root C:\TimelineData\input-video --output-root C:\TimelineData\video
.\cli.ps1 doctor
.\cli.ps1 files list
.\cli.ps1 sample frames --max-items 1 --samples-per-video 5
.\cli.ps1 items refresh --max-items 1
.\cli.ps1 items list
.\cli.ps1 items download
.\cli.ps1 items remove --dry-run
```

停止:

```powershell
.\stop.ps1
```

## 安全方針

- source videoを変更しません。
- source videoをコピーしません。
- ZIPにsource videoを含めません。
- `items remove` は既知の生成ファイルだけを削除し、source videoは削除しません。
- v1ではOCR、scene detection、face/person recognition、外部API、文字起こし、diarizationを実装しません。

## 出力

主な出力は `outputRoot` 配下に作成されます。

```text
<outputRoot>/
  items/
    <item-id>/
      video_record.json
      timeline.json
      convert_info.json
      raw_outputs/
        ffprobe.json
        frame_samples.json
      artifacts/
        contact_sheet.jpg
        frames/
  downloads/
  latest/
```

詳細は `docs/` を参照してください。
