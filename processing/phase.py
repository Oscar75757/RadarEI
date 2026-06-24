import numpy as np
import config


def decimate(iq: np.ndarray, factor: int = config.DECIMATION) -> np.ndarray:
    """Moyenne par blocs de `factor` samples (décimation simple sans anti-repliement).
    Suffisant ici car le signal utile est à < 1 Hz, très loin du repliement."""
    n = len(iq) - (len(iq) % factor)
    return iq[:n].reshape(-1, factor).mean(axis=1)


def extract_phase(iq: np.ndarray) -> np.ndarray:
    """Extrait la phase instantanée du signal IQ et la déroule (unwrap).

    Le mouvement thoracique module la phase : φ(t) = 4π·d(t)/λ
    arctan2 est limité à [-π, π] → np.unwrap corrige les sauts de 2π.
    """
    phase = np.angle(iq)           # arctan2(Q, I) ∈ [-π, π]
    return np.unwrap(phase)        # signal continu sans discontinuités


def remove_dc(signal: np.ndarray) -> np.ndarray:
    """Supprime la composante continue (réflexions statiques : murs, lit, équipements)."""
    return signal - np.mean(signal)


class Downconverter:
    """Descente numérique du ton IF de +F_IF vers 0 Hz (streaming continu).

    Le TX émet à fc + F_IF ; l'écho revient à +F_IF en bande de base. On le
    multiplie par e^{-j2π·F_IF·t} pour le ramener à DC. Le clutter statique et
    l'offset DC du récepteur (qui étaient à 0 Hz) se retrouvent alors à -F_IF.

    L'oscillateur local doit avoir une phase CONTINUE entre buffers (sinon on
    injecte des sauts de phase). On maintient donc un compteur d'échantillons
    global `_n` : tant que le flux RX est contigu, la dérotation est exacte.
    """

    def __init__(self, f_if: float = config.F_IF, fs: float = config.SAMPLE_RATE):
        self.f_if = f_if
        self.fs   = fs
        self._n   = 0

    def process(self, iq: np.ndarray) -> np.ndarray:
        n  = np.arange(self._n, self._n + len(iq))
        lo = np.exp(-2j * np.pi * self.f_if * n / self.fs).astype(np.complex64)
        self._n += len(iq)
        return iq * lo

    def reset(self):
        self._n = 0


class PhaseTracker:
    """Extraction de phase CONTINUE entre buffers successifs (streaming).

    np.unwrap traite chaque buffer isolément : à la frontière entre deux buffers,
    un saut de 2π peut apparaître. On raccorde ici la phase d'un buffer au dernier
    échantillon du précédent pour obtenir un signal continu sur toute la durée.
    """

    def __init__(self):
        self._last = None

    def process(self, iq: np.ndarray) -> np.ndarray:
        unwrapped = np.unwrap(np.angle(iq))
        if self._last is not None:
            # Aligne le 1er échantillon sur la continuité du buffer précédent
            offset = np.round((self._last - unwrapped[0]) / (2 * np.pi)) * 2 * np.pi
            unwrapped = unwrapped + offset
        self._last = unwrapped[-1]
        return unwrapped

    def reset(self):
        self._last = None
