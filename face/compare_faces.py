from __future__ import annotations

import os
import json
from typing import Any

import numpy as np


def cosine_similarity(a: Any, b: Any) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def compare_faces(embeddings: list[Any]) -> list[str] | bool:
    known_embeddings = []

    base_dir = os.path.dirname(__file__)
    faces_dir = os.path.join(base_dir, "face_embeddings")
    for file in os.listdir(faces_dir):
        if file.endswith(".json"):
            json_path = os.path.join(faces_dir, file)
            with open(json_path, "r") as f:
                known_embeddings.append({"name": file, "emb": json.load(f)})

    threshold = 0.6
    matches = []

    for emb in embeddings:
        for known_emb in known_embeddings:
            sim = cosine_similarity(np.array(emb), np.array(known_emb["emb"]))
            name = known_emb["name"].split("_")[0]
            if sim > threshold and name not in matches:
                matches.append(name)

    return matches if matches else False
