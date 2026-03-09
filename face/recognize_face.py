from __future__ import annotations

import os
from typing import Any

import cv2
import onnxruntime as ort
from insightface.app import FaceAnalysis

# No ONNX logging (daemon: avoid log buffer growth); reduce thread usage
ort.set_default_logger_severity(4)  # 4 = fatal only, no info/warning
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"


class recognize_face:
    _app_instance: Any = None  # singleton to reuse across calls

    def __init__(self) -> None:
        if recognize_face._app_instance is None:
            # Create FaceAnalysis once
            recognize_face._app_instance = FaceAnalysis(name="buffalo_l")
            recognize_face._app_instance.prepare(ctx_id=0, det_size=(640, 640))
        self.app = recognize_face._app_instance

    def extract_embedding(self, frame: Any) -> list[list[float]] | None:
        """
        Convert frame to RGB and extract embeddings.
        Returns a list of embeddings (one per face) or None if no faces found.
        """
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        faces = self.app.get(img)
        embeddings = [face.embedding.tolist() for face in faces]
        return embeddings if embeddings else None
