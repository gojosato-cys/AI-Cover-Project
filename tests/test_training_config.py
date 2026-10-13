from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_MANIFEST = PROJECT_ROOT / "data" / "training" / "manifests" / "model_v1.json"
SMOKE_CONFIG = (
    PROJECT_ROOT
    / "configs"
    / "training"
    / "qwen2_5_7b_instruct_qlora_smoke_v1.json"
)
QLORA_REQUIREMENTS = (
    PROJECT_ROOT / "configs" / "training" / "requirements-qlora-wsl.txt"
)
QLORA_ENVIRONMENT = (
    PROJECT_ROOT / "configs" / "training" / "environment-qlora-wsl.json"
)


class TrainingConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MODEL_MANIFEST.read_text(encoding="utf-8"))
        cls.config = json.loads(SMOKE_CONFIG.read_text(encoding="utf-8"))
        cls.qlora_requirements = QLORA_REQUIREMENTS.read_text(encoding="utf-8")
        cls.qlora_environment = json.loads(
            QLORA_ENVIRONMENT.read_text(encoding="utf-8")
        )

    def test_manifest_locks_current_inference_model(self) -> None:
        inference = self.manifest["inference_model"]

        self.assertEqual(inference["architecture"], "qwen2")
        self.assertEqual(inference["model_name"], "Qwen2.5 7B Instruct")
        self.assertEqual(inference["quantization"], "Q4_K_M")
        self.assertEqual(len(inference["sha256"]), 64)

    def test_training_base_uses_instruct_safetensors(self) -> None:
        training_base = self.manifest["training_base"]

        self.assertEqual(training_base["repo_id"], "Qwen/Qwen2.5-7B-Instruct")
        self.assertEqual(training_base["format"], "safetensors")
        self.assertEqual(training_base["status"], "downloaded_verified")
        self.assertEqual(
            training_base["revision"],
            "a09a35458c702b33eeacc393d103063234e8bc28",
        )

    def test_smoke_config_is_deliberately_short_and_low_memory(self) -> None:
        self.assertEqual(self.config["training"]["max_steps"], 2)
        self.assertEqual(self.config["training"]["per_device_train_batch_size"], 1)
        self.assertTrue(self.config["training"]["gradient_checkpointing"])
        self.assertTrue(self.config["quantization"]["load_in_4bit"])
        self.assertEqual(self.config["quantization"]["quant_type"], "nf4")

    def test_smoke_config_requires_revision_before_training(self) -> None:
        self.assertEqual(
            self.config["base_model"]["base_model_revision"],
            self.manifest["training_base"]["revision"],
        )
        self.assertTrue(self.config["guards"]["require_pinned_base_revision"])

    def test_download_manifest_records_every_file(self) -> None:
        download = self.manifest["download"]

        self.assertEqual(download["file_count"], 13)
        self.assertEqual(len(download["files"]), 13)
        self.assertEqual(download["weight_bytes"], 15231271888)
        for metadata in download["files"].values():
            self.assertGreater(metadata["bytes"], 0)
            self.assertEqual(len(metadata["sha256"]), 64)

    def test_test_split_is_not_a_training_input(self) -> None:
        dataset = self.config["dataset"]

        self.assertIn("train_file", dataset)
        self.assertIn("validation_file", dataset)
        self.assertNotIn(dataset["test_file"], (dataset["train_file"], dataset["validation_file"]))
        self.assertTrue(self.config["guards"]["exclude_test_split_from_training"])

    def test_all_large_artifact_paths_are_on_d_drive(self) -> None:
        paths = [
            self.manifest["inference_model"]["path"],
            self.manifest["training_base"]["local_dir_windows"],
        ]

        self.assertTrue(all(path.casefold().startswith("d:\\") for path in paths))
        self.assertTrue(self.config["project_dir"].startswith("/mnt/d/"))

    def test_qlora_toolchain_is_fully_pinned(self) -> None:
        required_pins = {
            "torch==2.9.1+cu128",
            "transformers==4.57.6",
            "peft==0.18.1",
            "trl==0.24.0",
            "bitsandbytes==0.48.2",
            "datasets==4.4.2",
            "accelerate==1.12.0",
            "safetensors==0.7.0",
        }

        self.assertIn(
            "--extra-index-url https://download.pytorch.org/whl/cu128",
            self.qlora_requirements,
        )
        self.assertTrue(
            required_pins.issubset(set(self.qlora_requirements.splitlines()))
        )

    def test_qlora_environment_keeps_caches_on_d_drive(self) -> None:
        caches = self.qlora_environment["cache"].values()

        self.assertTrue(all(path.startswith("/mnt/d/") for path in caches))
        self.assertTrue(
            self.qlora_environment["python"]["storage"].casefold().startswith("d:\\")
        )

    def test_qlora_environment_records_runtime_checks_without_training(self) -> None:
        verification = self.qlora_environment["verification"]

        self.assertEqual(verification["pip_check"], "passed")
        self.assertEqual(verification["bitsandbytes_nf4_roundtrip"], "passed")
        self.assertTrue(self.qlora_environment["gpu"]["cuda_available"])
        self.assertTrue(self.qlora_environment["gpu"]["bf16_supported"])
        self.assertFalse(verification["base_model_loaded"])
        self.assertFalse(verification["training_started"])


if __name__ == "__main__":
    unittest.main()
