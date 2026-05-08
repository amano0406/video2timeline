from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from timeline_for_video_worker.audio_models import (
    acoustic_unit_spans,
    diarization_activity_spans,
    iter_chunks,
    run_diarization,
    run_audio_reference_models,
    speaker_for_interval,
)


class AudioModelTests(unittest.TestCase):
    def test_missing_token_is_structured_and_nonfatal_in_auto_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "normalized_audio.wav"
            audio_path.write_bytes(b"wav")

            with patch.dict(
                "os.environ",
                {"TIMELINE_FOR_VIDEO_HUGGING_FACE_TOKEN": "", "HUGGING_FACE_HUB_TOKEN": "", "HF_TOKEN": ""},
                clear=False,
            ):
                result = run_audio_reference_models(
                    audio_path=audio_path,
                    speech_candidates=[{"startSec": 0.0, "endSec": 1.0, "durationSec": 1.0}],
                    source_name="clip.mp4",
                    settings={"audioModelMode": "auto", "computeMode": "cpu", "huggingFaceToken": ""},
                )

            self.assertTrue(result["ok"])
            self.assertEqual(result["diarization"]["status"], "not_configured")
            self.assertEqual(result["acousticUnits"]["status"], "not_configured")
            self.assertIn("hugging_face_token_missing", result["warnings"])

    def test_missing_token_is_failure_in_required_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "normalized_audio.wav"
            audio_path.write_bytes(b"wav")

            with patch.dict(
                "os.environ",
                {"TIMELINE_FOR_VIDEO_HUGGING_FACE_TOKEN": "", "HUGGING_FACE_HUB_TOKEN": "", "HF_TOKEN": ""},
                clear=False,
            ):
                result = run_audio_reference_models(
                    audio_path=audio_path,
                    speech_candidates=[],
                    source_name="clip.mp4",
                    settings={"audioModelMode": "required", "computeMode": "cpu", "huggingFaceToken": ""},
                )

            self.assertFalse(result["ok"])
            self.assertEqual(result["diarization"]["status"], "not_configured")

    def test_gpu_compute_mode_fails_instead_of_falling_back_to_cpu(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "normalized_audio.wav"
            audio_path.write_bytes(b"wav")
            runtime = {
                "ready": False,
                "computeMode": "gpu",
                "compute": {
                    "ready": False,
                    "mode": "gpu",
                    "workerFlavor": "cpu",
                    "torchCudaAvailable": False,
                    "onnxProviders": ["CPUExecutionProvider"],
                    "warnings": [
                        "computeMode gpu requires the GPU worker flavor.",
                        "CUDAExecutionProvider is not available to ONNX Runtime.",
                    ],
                },
                "tokenConfigured": True,
                "modules": {
                    "pyannote.audio": True,
                    "torch": True,
                    "torchaudio": True,
                    "onnxruntime": True,
                    "huggingface_hub": True,
                    "lhotse": True,
                    "numpy": True,
                },
                "diarization": {"ready": False},
                "acousticUnits": {"ready": False},
            }

            with patch("timeline_for_video_worker.audio_models.audio_model_runtime_status", return_value=runtime):
                with patch("timeline_for_video_worker.audio_models.load_huggingface_token", return_value="token"):
                    result = run_audio_reference_models(
                        audio_path=audio_path,
                        speech_candidates=[],
                        source_name="clip.mp4",
                        settings={"audioModelMode": "required", "computeMode": "gpu", "huggingFaceToken": "token"},
                    )

            self.assertFalse(result["ok"])
            self.assertEqual(result["diarization"]["status"], "compute_runtime_unavailable")
            self.assertEqual(result["acousticUnits"]["status"], "compute_runtime_unavailable")
            self.assertTrue(any("GPU worker flavor" in warning for warning in result["warnings"]))

    def test_speaker_for_interval_prefers_overlap(self) -> None:
        speaker = speaker_for_interval(
            1.0,
            3.0,
            [
                {"startSec": 0.0, "endSec": 1.2, "speaker": "SPEAKER_00"},
                {"startSec": 1.5, "endSec": 4.0, "speaker": "SPEAKER_01"},
            ],
        )

        self.assertEqual(speaker, "SPEAKER_01")

    def test_iter_chunks_is_bounded(self) -> None:
        self.assertEqual(iter_chunks(0.0, 5.0, 2.0), [(0.0, 2.0), (2.0, 4.0), (4.0, 5.0)])

    def test_diarization_activity_spans_pad_and_merge_candidates(self) -> None:
        spans = diarization_activity_spans(
            [
                {"startSec": 10.0, "endSec": 12.0},
                {"startSec": 13.0, "endSec": 14.0},
                {"startSec": 30.0, "endSec": 31.0},
            ]
        )

        self.assertEqual(spans, [(9.0, 15.0), (29.0, 32.0)])

    def test_acoustic_unit_spans_merge_and_bound_candidates(self) -> None:
        spans = acoustic_unit_spans(
            [
                {"startSec": 0.2, "endSec": 0.25},
                {"startSec": 10.0, "endSec": 10.4},
                {"startSec": 11.0, "endSec": 11.2},
            ],
            duration_seconds=12.0,
        )

        self.assertEqual(spans, [{"startSec": 0.0, "endSec": 1.25}, {"startSec": 9.0, "endSec": 12.0}])

    def test_required_mode_accepts_no_turns_without_fallback_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "normalized_audio.wav"
            audio_path.write_bytes(b"wav")
            runtime = {
                "ready": True,
                "computeMode": "cpu",
                "compute": {
                    "ready": True,
                    "mode": "cpu",
                    "workerFlavor": "cpu",
                    "torchCudaAvailable": None,
                    "onnxProviders": [],
                    "warnings": [],
                },
                "tokenConfigured": True,
                "modules": {
                    "pyannote.audio": True,
                    "torch": True,
                    "torchaudio": True,
                    "onnxruntime": True,
                    "huggingface_hub": True,
                    "lhotse": True,
                    "numpy": True,
                },
                "diarization": {"ready": True},
                "acousticUnits": {"ready": True},
            }

            with patch("timeline_for_video_worker.audio_models.audio_model_runtime_status", return_value=runtime):
                with patch("timeline_for_video_worker.audio_models.load_huggingface_token", return_value="token"):
                    with patch(
                        "timeline_for_video_worker.audio_models.run_diarization",
                        return_value={
                            "status": "no_speaker_turns",
                            "backend": "pyannote.audio",
                            "model_id": "pyannote/speaker-diarization-community-1",
                            "turns": [],
                            "turn_count": 0,
                            "warning_count": 1,
                            "warnings": ["Speaker diarization completed, but no speaker turns were found."],
                            "error": None,
                        },
                    ):
                        with patch(
                            "timeline_for_video_worker.audio_models.run_acoustic_units",
                            return_value={
                                "status": "no_turns",
                                "backend": "zipa-large-crctc-300k-onnx-v1",
                                "model_id": "anyspeech/zipa-large-crctc-300k",
                                "unit_type": "phone_like",
                                "turns": [],
                                "turn_count": 0,
                                "warning_count": 1,
                                "warnings": ["Acoustic unit extraction produced no turns."],
                                "error": None,
                            },
                        ):
                            result = run_audio_reference_models(
                                audio_path=audio_path,
                                speech_candidates=[],
                                source_name="silent.mp4",
                                settings={"audioModelMode": "required", "computeMode": "cpu", "huggingFaceToken": "token"},
                            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["diarization"]["turns"], [])
            self.assertEqual(result["acousticUnits"]["turns"], [])
            self.assertEqual(result["text"]["segments"], [])

    def test_run_diarization_uses_preloaded_audio_input(self) -> None:
        class FakeSegment:
            start = 1.0
            end = 2.5

        class FakeAnnotation:
            def itertracks(self, yield_label: bool = False):
                yield FakeSegment(), None, "SPEAKER_00"

        class FakePipeline:
            def __init__(self) -> None:
                self.received = None

            def __call__(self, payload):
                self.received = payload
                return FakeAnnotation()

        pipeline = FakePipeline()
        audio_input = {"waveform": object(), "sample_rate": 16000}

        with patch("timeline_for_video_worker.audio_models.load_diarization_pipeline", return_value=pipeline):
            with patch("timeline_for_video_worker.audio_models.load_diarization_audio_input", return_value=audio_input):
                result = run_diarization(
                    Path("normalized_audio.wav"),
                    token="token",
                    compute_mode="cpu",
                    source_name="clip.mp4",
                )

        self.assertIs(pipeline.received, audio_input)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["turn_count"], 1)
        self.assertEqual(result["turns"][0]["speaker"], "SPEAKER_00")

    def test_run_diarization_offsets_speech_candidate_spans(self) -> None:
        class FakeSegment:
            start = 1.0
            end = 2.5

        class FakeAnnotation:
            def itertracks(self, yield_label: bool = False):
                yield FakeSegment(), None, "SPEAKER_00"

        class FakePipeline:
            def __init__(self) -> None:
                self.received = []

            def __call__(self, payload):
                self.received.append(payload)
                return FakeAnnotation()

        pipeline = FakePipeline()
        audio_input = {"waveform": object(), "sample_rate": 16000}

        with patch("timeline_for_video_worker.audio_models.load_diarization_pipeline", return_value=pipeline):
            with patch("timeline_for_video_worker.audio_models.load_diarization_audio_input", return_value=audio_input):
                result = run_diarization(
                    Path("normalized_audio.wav"),
                    token="token",
                    compute_mode="cpu",
                    source_name="clip.mp4",
                    speech_candidates=[{"startSec": 10.0, "endSec": 12.0}],
                )

        self.assertEqual(len(pipeline.received), 1)
        self.assertEqual(result["scope"]["mode"], "speech_candidates")
        self.assertEqual(result["scope"]["activeSec"], 4.0)
        self.assertEqual(result["turns"][0]["start"], 10.0)
        self.assertEqual(result["turns"][0]["end"], 11.5)


if __name__ == "__main__":
    unittest.main()
