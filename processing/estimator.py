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

        # Restriction à la bande respiratoire
        mask = (freqs >= config.F_LOW) & (freqs <= config.F_HIGH)
        if not mask.any():
            return None

        peak_freq = freqs[mask][np.argmax(spectrum[mask])]
        rate_rpm  = peak_freq * 60.0

        self._rate_history.append(rate_rpm)
        return float(np.mean(self._rate_history))
