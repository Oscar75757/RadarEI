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


def oscillation_amplitude(signal: np.ndarray) -> float:
    """Amplitude d'oscillation CRÊTE-À-CRÊTE (p95 − p5) après détrend LINÉAIRE.

    Sert à détecter l'apnée RAPIDEMENT, sur la phase BRUTE plutôt que sur la
    sortie du passe-haut : la phase brute se fige instantanément quand la
    respiration s'arrête (pas de décroissance lente du filtre). Le détrend
    linéaire retire la dérive du corps sur la fenêtre, sans queue temporelle.

    On utilise l'écart crête-à-crête (percentiles 95−5, robuste aux pics) et
    NON l'écart-type : l'écart-type d'une sinusoïde ondule fortement quand la
    fenêtre ne contient pas un nombre entier de périodes, ce qui faisait
    faussement passer l'amplitude sous le seuil pendant une respiration normale.
    Le crête-à-crête, lui, est stable dès que la fenêtre couvre ~une période.
    """
    n = len(signal)
    if n < 2:
        return 0.0
    x = np.arange(n)
    slope, intercept = np.polyfit(x, signal, 1)
    detrended = signal - (slope * x + intercept)
    return float(np.percentile(detrended, 95) - np.percentile(detrended, 5))


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


class ClutterCanceller:
    """Annule le vecteur statique S (couplage TX→RX + réflexions fixes) qui SURVIT
    à la descente IF.

    Le couplage direct entre antennes est émis au ton fc+F_IF, exactement comme
    l'écho utile : il se retrouve à 0 Hz après la descente IF et n'est donc PAS
    éliminé par la décimation (qui n'enlève que ce qui est à -F_IF). Ce S s'ajoute
    à l'écho mobile du thorax M·e^{jφ}. Quand |S| domine, la phase mesurée vaut
    ≈ ∠S + (|M|/|S|)·sin(φ − ∠S) : la respiration n'apparaît qu'en PROJECTION, de
    signe ET d'amplitude réglés par cos(φ_moy − ∠S) — donc par la distance du
    patient modulo λ. D'où l'inversion aléatoire inspiration/expiration d'une
    session à l'autre, et les « points morts » (cos ≈ 0 → signal très faible).

    On estime S par une moyenne complexe glissante (EMA) à constante de temps
    LONGUE devant la respiration, puis on la soustrait. La phase redevient le vrai
    déplacement géométrique : signe déterministe (fixé par la seule géométrie
    d'antenne) et amplitude pleine. τ doit rester ≫ période respiratoire, sinon
    l'EMA « mange » la respiration elle-même.
    """

    def __init__(self, tau_s: float = config.CLUTTER_TAU_S,
                 fs: float = config.DECIMATED_FS):
        self.alpha = 1.0 - np.exp(-1.0 / (tau_s * fs)) if tau_s > 0 else None
        self._dc   = None

    def process(self, iq: np.ndarray) -> np.ndarray:
        if self.alpha is None:        # désactivé : passe-plat
            return iq
        out = np.empty_like(iq)
        dc, a = self._dc, self.alpha
        for i in range(len(iq)):
            s = iq[i]
            dc = s if dc is None else dc + a * (s - dc)
            out[i] = s - dc
        self._dc = dc
        return out

    def reset(self):
        self._dc = None


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
