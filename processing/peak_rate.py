import collections
import numpy as np
import config


class PeakRateEstimator:
    """Rythme respiratoire par INTERVALLE ENTRE PICS d'inspiration (méthode
    temporelle, pour l'AFFICHAGE — levier 4).

    Se met à jour à chaque respiration (quasi temps-réel), contrairement à la
    FFT qui moyenne sur une fenêtre. Le rythme est moyenné sur les
    PEAK_RATE_NPEAKS derniers pics pour limiter les fluctuations.

    Détection de pic par hystérésis (type Schmitt sur la pente) : on confirme un
    pic quand le signal redescend de `delta` sous le maximum candidat, ce qui
    évite de compter le bruit. `delta` s'adapte à l'amplitude respiratoire.
    Comme un retard de groupe constant décale tous les pics de la même durée,
    l'INTERVALLE — donc le rythme — reste exact même sur le signal filtré.
    """

    def __init__(self):
        self.fs = config.DECIMATED_FS
        self._peak_times  = collections.deque(maxlen=config.PEAK_RATE_NPEAKS)
        self._n           = 0           # compteur d'échantillons global
        self._mode        = "rising"    # on cherche d'abord un pic
        self._cand_val    = -np.inf     # maximum candidat (pic)
        self._cand_t      = 0.0
        self._cand_min    = np.inf       # minimum candidat (creux)
        self._last_peak_t = -np.inf

    def update(self, samples: np.ndarray, amplitude: float) -> None:
        """Consomme un buffer de signal filtré et met à jour la liste des pics."""
        delta = max(config.PEAK_MIN_DELTA, config.PEAK_HYSTERESIS_FRAC * amplitude)
        for x in samples:
            t = self._n / self.fs
            self._n += 1

            if self._mode == "rising":
                if x > self._cand_val:
                    self._cand_val, self._cand_t = x, t
                elif x < self._cand_val - delta:
                    # le signal est redescendu : pic confirmé au candidat
                    if self._cand_t - self._last_peak_t >= config.PEAK_REFRACTORY_S:
                        self._peak_times.append(self._cand_t)
                        self._last_peak_t = self._cand_t
                    self._mode, self._cand_min = "falling", x
            else:  # "falling" : on cherche le creux avant le prochain pic
                if x < self._cand_min:
                    self._cand_min = x
                elif x > self._cand_min + delta:
                    self._mode, self._cand_val, self._cand_t = "rising", x, t

    def rate(self) -> float | None:
        """Rythme courant (resp/min), ou None si pas de pic récent."""
        if len(self._peak_times) < 2:
            return None
        now = self._n / self.fs
        if now - self._peak_times[-1] > config.PEAK_STALE_S:
            return None   # plus de respiration récente (apnée, ou signal perdu)
        span = self._peak_times[-1] - self._peak_times[0]
        if span <= 0:
            return None
        n_intervals = len(self._peak_times) - 1
        return 60.0 * n_intervals / span
