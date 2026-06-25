import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi
import config


def _butter_bandpass(low: float, high: float, fs: float, order: int):
    nyq = fs / 2.0
    sos = butter(order, [low / nyq, high / nyq], btype="band", output="sos")
    return sos


class RespiratoryFilter:
    """Filtre passe-bande Butterworth en temps-réel (mode streaming avec état persistant).

    Préserve l'état entre les appels pour ne pas introduire de discontinuités
    à chaque nouveau buffer — indispensable en traitement continu.

    Coupures volontairement larges (FILTER_LOW/HIGH) pour minimiser le retard de
    groupe sur la respiration lente. La sélection fine de la bande respiratoire
    est faite côté FFT (RateEstimator), pas ici.
    """

    def __init__(self):
        self._sos = _butter_bandpass(
            config.FILTER_LOW, config.FILTER_HIGH, config.DECIMATED_FS, config.FILTER_ORDER
        )
        self._zi = sosfilt_zi(self._sos)   # conditions initiales à zéro

    def apply(self, signal: np.ndarray) -> np.ndarray:
        filtered, self._zi = sosfilt(self._sos, signal, zi=self._zi)
        return filtered

    def reset(self):
        self._zi = sosfilt_zi(self._sos)


class CardiacFilter:
    """Filtre passe-bande cardiaque Butterworth 6e ordre (0.8–2.5 Hz), streaming.

    Appliqué sur la phase brute DC-removed (même entrée que RespiratoryFilter).
    Ordre 6 pour mieux rejeter les harmoniques respiratoires à 0.5–0.7 Hz.
    """

    def __init__(self):
        self._sos = _butter_bandpass(
            config.CARDIAC_F_LOW,
            config.CARDIAC_F_HIGH,
            config.DECIMATED_FS,
            config.CARDIAC_FILTER_ORDER,
        )
        self._zi = sosfilt_zi(self._sos)

    def apply(self, signal: np.ndarray) -> np.ndarray:
        filtered, self._zi = sosfilt(self._sos, signal, zi=self._zi)
        return filtered

    def reset(self):
        self._zi = sosfilt_zi(self._sos)
