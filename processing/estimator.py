import collections
import numpy as np
import config


class RateEstimator:
    """Estime le rythme respiratoire (resp/min) par FFT sur fenêtre glissante.

    Accumule les échantillons filtrés et calcule la FFT dès qu'une fenêtre
    complète est disponible. Le résultat est lissé sur les N dernières estimations.
    """

    def __init__(self):
        self._window_n  = int(config.WINDOW_S * config.DECIMATED_FS)
        self._hop_n     = int(self._window_n * (1 - config.OVERLAP))
        self._buf       = collections.deque(maxlen=self._window_n)
        self._samples_since_last = 0
        self._rate_history = collections.deque(maxlen=config.SMOOTHING_N)

    def push(self, samples: np.ndarray) -> float | None:
        """Ajoute des échantillons. Retourne le rythme lissé (rpm) si disponible, sinon None."""
        for s in samples:
            self._buf.append(s)
        self._samples_since_last += len(samples)

        if len(self._buf) < self._window_n:
            return None   # fenêtre pas encore remplie

        if self._samples_since_last < self._hop_n:
            return None   # pas encore le moment de recalculer

        self._samples_since_last = 0
        return self._estimate()

    def _estimate(self) -> float | None:
        signal = np.array(self._buf)
        signal -= signal.mean()

        window  = np.hanning(len(signal))
        spectrum = np.abs(np.fft.rfft(signal * window))
        freqs    = np.fft.rfftfreq(len(signal), d=1.0 / config.DECIMATED_FS)
        df       = freqs[1] - freqs[0]

        # Restriction à la bande respiratoire
        band = np.where((freqs >= config.F_LOW) & (freqs <= config.F_HIGH))[0]
        if band.size == 0:
            return None

        # Indice du pic dans le spectre complet
        k = band[np.argmax(spectrum[band])]

        # Interpolation parabolique : estime la fréquence ENTRE les points FFT
        # (récupère la précision perdue avec une fenêtre courte).
        if 0 < k < len(spectrum) - 1:
            a, b, c = spectrum[k - 1], spectrum[k], spectrum[k + 1]
            denom = a - 2 * b + c
            delta = 0.5 * (a - c) / denom if denom != 0 else 0.0
            delta = float(np.clip(delta, -0.5, 0.5))
        else:
            delta = 0.0

        peak_freq = freqs[k] + delta * df
        rate_rpm  = peak_freq * 60.0

        self._rate_history.append(rate_rpm)
        return float(np.mean(self._rate_history))
