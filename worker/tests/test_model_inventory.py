from __future__ import annotations

import unittest
from unittest.mock import patch

from timeline_for_video_worker.model_inventory import build_model_inventory


def ok_runtime(command_name: str) -> dict[str, object]:
    return {
        "ok": True,
        "command": [command_name, "-version"],
        "versionLine": f"{command_name} fake 1.0",
        "error": None,
    }


def audio_status(*, token_configured: bool = False) -> dict[str, object]:
    modules = {
        "pyannote.audio": True,
        "torch": True,
        "torchaudio": True,
        "onnxruntime": True,
        "huggingface_hub": True,
        "lhotse": True,
        "numpy": True,
    }
    return {
        "ready": token_configured,
        "tokenConfigured": token_configured,
        "modules": modules,
        "diarization": {
            "backend": "pyannote.audio",
            "modelId": "pyannote/speaker-diarization-community-1",
            "ready": token_configured,
        },
        "acousticUnits": {
            "backend": "zipa-large-crctc-300k-onnx-v1",
            "modelId": "anyspeech/zipa-large-crctc-300k",
            "unitType": "phone_like",
            "ready": True,
        },
    }


class ModelInventoryTests(unittest.TestCase):
    def test_inventory_required_components_are_ready_without_audio_token(self) -> None:
        with patch("timeline_for_video_worker.model_inventory.ffprobe_version", return_value=ok_runtime("ffprobe")):
            with patch("timeline_for_video_worker.model_inventory.ffmpeg_version", return_value=ok_runtime("ffmpeg")):
                with patch(
                    "timeline_for_video_worker.model_inventory.ocr_runtime_status",
                    return_value={
                        "ok": True,
                        "mode": "auto",
                        "model": "tesseract:jpn+eng",
                        "languages": ["eng", "jpn"],
                        "message": "ready",
                    },
                ):
                    with patch(
                        "timeline_for_video_worker.model_inventory.audio_model_runtime_status",
                        return_value=audio_status(token_configured=False),
                    ):
                        payload = build_model_inventory(settings={"audioModelMode": "auto"})

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["counts"]["requiredComponents"], 6)
        self.assertEqual(payload["counts"]["readyRequiredComponents"], 6)
        self.assertEqual(payload["counts"]["audioModelComponents"], 2)
        self.assertEqual(payload["counts"]["readyAudioModelComponents"], 1)
        self.assertFalse(payload["sourceVideoSafety"]["sourceVideoModified"])
        self.assertFalse(payload["sourceVideoSafety"]["sourceVideosIncludedInZip"])
        self.assertFalse(payload["sourceVideoSafety"]["generatedAudioIncludedInZip"])
        self.assertFalse(payload["sourceVideoSafety"]["externalAnalysisApiUsed"])
        components = {component["id"]: component for component in payload["components"]}
        self.assertTrue(components["frame_visual_features"]["runtime"]["ready"])
        self.assertFalse(components["speaker_diarization"]["runtime"]["details"]["componentReady"])
        self.assertTrue(components["acoustic_units"]["runtime"]["details"]["componentReady"])
        self.assertFalse(components["acoustic_units"]["runtime"]["details"]["audioModelsReady"])

    def test_inventory_marks_local_runtime_failure_as_not_ok(self) -> None:
        failed_ffmpeg = {
            "ok": False,
            "command": ["ffmpeg", "-version"],
            "versionLine": None,
            "error": "missing ffmpeg",
        }
        with patch("timeline_for_video_worker.model_inventory.ffprobe_version", return_value=ok_runtime("ffprobe")):
            with patch("timeline_for_video_worker.model_inventory.ffmpeg_version", return_value=failed_ffmpeg):
                with patch(
                    "timeline_for_video_worker.model_inventory.ocr_runtime_status",
                    return_value={
                        "ok": True,
                        "mode": "off",
                        "model": None,
                        "languages": [],
                        "message": "disabled",
                    },
                ):
                    with patch(
                        "timeline_for_video_worker.model_inventory.audio_model_runtime_status",
                        return_value=audio_status(token_configured=False),
                    ):
                        payload = build_model_inventory(settings={"audioModelMode": "auto"})

        self.assertFalse(payload["ok"])
        components = {component["id"]: component for component in payload["components"]}
        self.assertFalse(components["bounded_frame_sampling"]["runtime"]["ready"])
        self.assertFalse(components["audio_derivative"]["runtime"]["ready"])
        self.assertFalse(components["speech_candidate_detection"]["runtime"]["ready"])


if __name__ == "__main__":
    unittest.main()
