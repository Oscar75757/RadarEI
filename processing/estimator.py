import collections
import numpy as np
import config


class RateEstimator:
    """Estime un rythme physiologique par FFT sur fenêtre glissante.

    Utilisable pour la respiration (défaut) ou le cardiaque en passant
    les paramètres de bande explicitement. Rétro-compatible : RateEstimator()
    sans arguments garde le comportement respiratoire original.
    """

    def __init__(
        self,
        f_low: float | None = None,
        f_high: float | None = None,
        window_s: float | None = None,
        smoothing_n: int | None = None,
    ):
        self._f_low  = f_low       if f_low       is not None else config.F_LOW
        self._f_high = f_high      if f_high      is not None else config.F_HIGH
        window_s     = window_s    if window_s    is not None else config.WINDOW_S
        smoothing_n  = smoothing_n if smoothing_n is not None else config.SMOOTHING_N

        self._window_n  = int(window_s * config.DECIMATED_FS)
        self._hop_n     = int(self._window_n * (1 - config.OVERLAP))
        self._buf       = collections.deque(maxlen=self._window_n)
        self._samples_since_last = 0
        self._rate_history = collections.deque(maxlen=smoothing_n)

    def push(self, samples: np.ndarray) -> float | None:
        """Ajoute des échantillons. Retourne le rythme lissé si disponible, sinon None."""
        for s in samples:
            self._buf.append(s)
        self._samples_since_last += len(samples)

        if len(self._buf) < self._window_n:
            return None

        if self._samples_since_last < self._hop_n:
            return None

        self._samples_since_last = 0
        return self._estimate()

    def _estimate(self) -> float | None:
        signal = np.array(self._buf)
        signal -= signal.mean()

        window   = np.hanning(len(signal))
        spectrum = np.abs(np.fft.rfft(signal * window))
        freqs    = np.fft.rfftfreq(len(signal), d=1.0 / config.DECIMATED_FS)
        df       = freqs[1] - freqs[0]

        band = np.where((freqs >= self._f_low) & (freqs <= self._f_high))[0]
        if band.size == 0:
            return None

        k = band[np.argmax(spectrum[band])]

        # Interpolation parabolique : précision sub-bin (Oscar)
        if 0 < k < len(spectrum) - 1:
            a, b, c = spectrum[k - 1], spectrum[k], spectrum[k + 1]
            denom = a - 2 * b + c
            delta = 0.5 * (a - c) / denom if denom != 0 else 0.0
            delta = float(np.clip(delta, -0.5, 0.5))
        else:
            delta = 0.0

        peak_freq = freqs[k] + delta * df
        rate      = peak_freq * 60.0

        self._rate_history.append(rate)
        return float(np.mean(self._rate_history))
