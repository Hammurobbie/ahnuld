"""Score 48 kHz mic audio with the hey-arnold model."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort

_MEL_WINDOW = 76
_MEL_STRIDE = 8
_MIN_EMBEDDINGS = 16
_SAMPLES_16K = 32000  # 2 seconds


class HeyArnoldWake:
    def __init__(self, model_dir: str | Path) -> None:
        model_dir = Path(model_dir)
        self._mel = self._session(model_dir / "melspectrogram.onnx")
        self._embed = self._session(model_dir / "embedding_model.onnx")
        self._cls = self._session(model_dir / "hey_arnold.onnx")
        self._window = np.zeros(_SAMPLES_16K, dtype=np.float32)
        self._filled = 0
        self._pending = np.zeros(0, dtype=np.int16)
        self._since_score = 0

    def reset(self) -> None:
        self._window.fill(0.0)
        self._filled = 0
        self._pending = np.zeros(0, dtype=np.int16)
        self._since_score = 0

    @staticmethod
    def _session(path: Path) -> tuple[ort.InferenceSession, str]:
        if not path.exists():
            raise FileNotFoundError(path)
        # The default pool uses every core and holds the fan at full speed.
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(
            str(path),
            providers=["CPUExecutionProvider"],
            sess_options=options,
        )
        return session, session.get_inputs()[0].name

    def push_48k(self, pcm: bytes, score_every: int = 8000) -> float | None:
        samples = np.frombuffer(pcm, dtype=np.int16)
        pending = np.concatenate([self._pending, samples])
        usable = (len(pending) // 3) * 3
        self._pending = pending[usable:]
        if usable == 0:
            return None
        down = pending[:usable].reshape(-1, 3).mean(axis=1).astype(np.float32) / 32768.0
        self._push_16k(down)
        self._since_score += len(down)
        if self._filled < _SAMPLES_16K or self._since_score < score_every:
            return None
        self._since_score = 0
        return self.score_16k(self._window)

    def _push_16k(self, samples: np.ndarray) -> None:
        n = len(samples)
        if n >= _SAMPLES_16K:
            self._window[:] = samples[-_SAMPLES_16K:]
            self._filled = _SAMPLES_16K
            return
        if self._filled < _SAMPLES_16K:
            take = min(n, _SAMPLES_16K - self._filled)
            self._window[self._filled : self._filled + take] = samples[:take]
            self._filled += take
            samples = samples[take:]
            n = len(samples)
            if n == 0:
                return
        self._window[:-n] = self._window[n:]
        self._window[-n:] = samples

    def score_16k(self, audio: np.ndarray) -> float:
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        audio = np.asarray(audio, dtype=np.float32).reshape(1, -1)
        mel_session, mel_input = self._mel
        mel = mel_session.run(None, {mel_input: audio})[0]
        if mel.ndim == 4:
            mel = mel[:, 0, :, :]
        mel = mel[0] / 10.0 + 2.0
        if mel.shape[0] < _MEL_WINDOW:
            return 0.0

        windows = []
        for start in range(0, mel.shape[0] - _MEL_WINDOW + 1, _MEL_STRIDE):
            windows.append(mel[start : start + _MEL_WINDOW])
        if len(windows) < _MIN_EMBEDDINGS:
            return 0.0
        batch = np.stack(windows[-_MIN_EMBEDDINGS:], axis=0)[..., np.newaxis].astype(np.float32)
        embed_session, embed_input = self._embed
        embeddings = embed_session.run(None, {embed_input: batch})[0]
        embeddings = np.squeeze(embeddings, axis=(1, 2))
        cls_session, cls_input = self._cls
        score = cls_session.run(None, {cls_input: embeddings[np.newaxis].astype(np.float32)})
        return float(score[0][0, 0])
