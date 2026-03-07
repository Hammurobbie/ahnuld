import numpy as np
import json
import os

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def compare_faces(embeddings):
    known_embeddings = []

    faces_dir = "face_embeddings"
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
            name = known_emb['name'].split('_')[0]
            if sim > threshold and name not in matches:
                matches.append(name)

    return matches if matches else False
