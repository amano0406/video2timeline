from __future__ import annotations

import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile

from timeline_for_video_worker.discovery import display_path, video_file_from_path
from timeline_for_video_worker.items import download_items, list_items, refresh_items, remove_items
from timeline_for_video_worker.sampling import sample_video_files


FFPROBE_FIXTURE = {
    "streams": [
        {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
            "width": 640,
            "height": 360,
            "duration": "8.000000",
        },
        {
            "index": 1,
            "codec_type": "audio",
            "codec_name": "aac",
            "sample_rate": "48000",
            "channels": 2,
            "duration": "8.000000",
        },
    ],
    "format": {
        "format_name": "mov,mp4",
        "format_long_name": "QuickTime / MOV",
        "duration": "8.000000",
        "size": "5",
        "bit_rate": "40",
    },
}


def write_fake_ffprobe(directory: Path) -> str:
    script = directory / "fake_ffprobe.py"
    script.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "if '-version' in sys.argv:",
                "    print('ffprobe fake 1.0')",
                "else:",
                f"    print(json.dumps({FFPROBE_FIXTURE!r}))",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return f"{sys.executable} {script}"


def write_fake_ffmpeg(directory: Path) -> str:
    script = directory / "fake_ffmpeg.py"
    script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "if '-version' in sys.argv:",
                "    print('ffmpeg fake 1.0')",
                "    raise SystemExit(0)",
                "Path(sys.argv[-1]).write_bytes(b'jpeg')",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return f"{sys.executable} {script}"


class ItemsTests(unittest.TestCase):
    def test_refresh_items_writes_item_contract_files_and_preserves_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input" / "clip.mp4"
            source.parent.mkdir()
            source.write_bytes(b"video")
            source_before = source.read_bytes()
            output_root = root / "output"
            fake_ffprobe = write_fake_ffprobe(root)
            fake_ffmpeg = write_fake_ffmpeg(root)
            video_file = video_file_from_path(source, str(source.parent))

            sample_result = sample_video_files(
                [video_file],
                str(output_root),
                ffprobe_bin=fake_ffprobe,
                ffmpeg_bin=fake_ffmpeg,
                max_items=1,
                samples_per_video=2,
            )
            self.assertTrue(sample_result["ok"])

            refresh_result = refresh_items(
                [video_file],
                str(output_root),
                ffprobe_bin=fake_ffprobe,
                max_items=1,
            )

            self.assertTrue(refresh_result["ok"])
            self.assertEqual(refresh_result["counts"]["refreshedItems"], 1)
            record = refresh_result["records"][0]
            item_root = Path(record["itemRoot"])
            video_record_path = item_root / "video_record.json"
            timeline_path = item_root / "timeline.json"
            convert_info_path = item_root / "convert_info.json"
            ffprobe_path = item_root / "raw_outputs" / "ffprobe.json"

            self.assertTrue(video_record_path.exists())
            self.assertTrue(timeline_path.exists())
            self.assertTrue(convert_info_path.exists())
            self.assertTrue(ffprobe_path.exists())
            self.assertEqual(source.read_bytes(), source_before)

            video_record = json.loads(video_record_path.read_text(encoding="utf-8"))
            timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
            convert_info = json.loads(convert_info_path.read_text(encoding="utf-8"))

            self.assertEqual(video_record["schema_version"], "timeline_for_video.video_record.v1")
            self.assertIs(video_record["asset"]["source_video_modified"], False)
            self.assertEqual(len(video_record["frames"]), 2)
            self.assertIn("visual", timeline["lanes"])
            self.assertIn("audio", timeline["lanes"])
            self.assertIn("frame_sample", {event["eventType"] for event in timeline["lanes"]["visual"]})
            self.assertIs(convert_info["source_video_modified"], False)
            self.assertEqual(convert_info["counts"]["frames"], 2)
            required_outputs = {"video_record", "timeline", "convert_info", "ffprobe_raw"}
            output_files = {entry["kind"]: entry for entry in convert_info["outputFiles"]}
            self.assertTrue(all(output_files[kind]["exists"] for kind in required_outputs))

    def test_list_items_reads_video_records_from_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "clip.mp4"
            source.write_bytes(b"video")
            output_root = root / "output"
            fake_ffprobe = write_fake_ffprobe(root)
            video_file = video_file_from_path(source, str(root))

            refresh_items([video_file], str(output_root), ffprobe_bin=fake_ffprobe, max_items=1)
            result = list_items(str(output_root))

            self.assertTrue(result["ok"])
            self.assertEqual(result["counts"]["items"], 1)
            self.assertTrue(result["items"][0]["itemId"].startswith("video-"))
            self.assertEqual(result["items"][0]["sourcePath"], display_path(source))

    def test_download_items_exports_generated_files_without_source_video(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input" / "clip.mp4"
            source.parent.mkdir()
            source.write_bytes(b"video")
            output_root = root / "output"
            fake_ffprobe = write_fake_ffprobe(root)
            fake_ffmpeg = write_fake_ffmpeg(root)
            video_file = video_file_from_path(source, str(source.parent))

            sample_video_files(
                [video_file],
                str(output_root),
                ffprobe_bin=fake_ffprobe,
                ffmpeg_bin=fake_ffmpeg,
                max_items=1,
                samples_per_video=2,
            )
            refresh_items([video_file], str(output_root), ffprobe_bin=fake_ffprobe, max_items=1)

            result = download_items(str(output_root))

            archive_path = Path(result["archivePath"])
            latest_path = Path(result["latestArchivePath"])
            manifest_path = Path(result["latestManifestPath"])
            self.assertTrue(archive_path.exists())
            self.assertTrue(latest_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertFalse(result["sourceVideosIncluded"])

            with zipfile.ZipFile(archive_path) as archive:
                names = archive.namelist()

            self.assertIn("manifest.json", names)
            self.assertTrue(any(name.endswith("video_record.json") for name in names))
            self.assertTrue(any(name.endswith("timeline.json") for name in names))
            self.assertTrue(any(name.endswith("contact_sheet.jpg") for name in names))
            self.assertFalse(any(name.casefold().endswith(".mp4") for name in names))

    def test_remove_items_deletes_generated_artifacts_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input" / "clip.mp4"
            source.parent.mkdir()
            source.write_bytes(b"video")
            output_root = root / "output"
            output_root.mkdir()
            user_video = output_root / "keep-source.mp4"
            user_video.write_bytes(b"user video")
            fake_ffprobe = write_fake_ffprobe(root)
            fake_ffmpeg = write_fake_ffmpeg(root)
            video_file = video_file_from_path(source, str(source.parent))

            sample_video_files(
                [video_file],
                str(output_root),
                ffprobe_bin=fake_ffprobe,
                ffmpeg_bin=fake_ffmpeg,
                max_items=1,
                samples_per_video=1,
            )
            refresh_result = refresh_items([video_file], str(output_root), ffprobe_bin=fake_ffprobe, max_items=1)
            download_items(str(output_root))
            item_root = Path(refresh_result["records"][0]["itemRoot"])

            dry_run = remove_items(str(output_root), dry_run=True)
            self.assertGreater(dry_run["counts"]["targetFiles"], 0)
            self.assertTrue((item_root / "video_record.json").exists())

            result = remove_items(str(output_root))

            self.assertTrue(result["ok"])
            self.assertFalse(result["sourceVideosRemoved"])
            self.assertFalse((item_root / "video_record.json").exists())
            self.assertFalse((output_root / "latest" / "items.zip").exists())
            self.assertTrue(source.exists())
            self.assertEqual(source.read_bytes(), b"video")
            self.assertTrue(user_video.exists())
            self.assertEqual(user_video.read_bytes(), b"user video")


if __name__ == "__main__":
    unittest.main()
