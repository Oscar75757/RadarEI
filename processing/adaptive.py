import collections
import numpy as np
import config


class AdaptiveApneaThreshold:
    """Seuil d'apnée auto-calibré, PUREMENT RELATIF à la respiration du patient.

        seuil = fraction × baseline

    `baseline` est l'amplitude respiratoire « habituelle », suivie par une moyenne
    exponentielle (EMA) lente qui s'adapte EN PERMANENCE (pas de gel). Choix de
    conception :

    - Relatif (aucun plancher absolu en rad) → indépendant de l'antenne, de la
      distance et du gain : une grosse antenne (signal ~0.3) et une petite
      (~0.07) sont traitées pareil.
    - Toujours adaptatif → jamais bloqué : une calibration ratée (transitoire de
      mise en place capturé comme baseline) se corrige seule en ~τ, ou
      instantanément via recalibrate() (touche « c »). C'est la correction du
      défaut où le « gel pendant l'apnée » verrouillait une mauvaise baseline.
    - L'apnée reste détectée malgré l'adaptation continue : l'amplitude
      s'effondre TRÈS en dessous du seuil et y reste ~70 s avant que la baseline
      ait assez décru — bien au-delà du seuil clinique (10 s).

    Démarrage : pendant WARMUP_S, le patient s'installe et respire ; on n'alerte
    pas et on collecte l'amplitude. La baseline est initialisée sur le régime
    permanent (médiane des dernières secondes de calibration). Hystérésis
    (FRAC_ENTER / FRAC_EXIT) anti-flicker.
    """

    def __init__(self):
        self.warmup_s = config.WARMUP_S
        self.tau      = config.APNEA_BASELINE_TAU_S
        self.f_enter  = config.APNEA_FRAC_ENTER
        self.f_exit   = config.APNEA_FRAC_EXIT
        self.eps      = config.APNEA_AMP_EPS
        self._reset()

    def _reset(self):
        self._elapsed   = 0.0
        self._warm_amps = collections.deque()
        self.baseline   = None
        self.in_apnea   = False

    def recalibrate(self):
        """Relance la calibration (ex. après changement d'antenne/position)."""
        self._reset()

    def update(self, amplitude: float, dt: float):
        """Avance d'un pas. Retourne (état, respire, seuil, restant_s).

        état : "warmup" (calibration) ou "active".
        """
        self._elapsed += dt

        # --- Calibration ---
        if self._elapsed < self.warmup_s:
            self._warm_amps.append((self._elapsed, amplitude))
            return ("warmup", True, self.eps, self.warmup_s - self._elapsed)

        # --- Initialisation de la baseline (une fois, en fin de calibration) ---
        if self.baseline is None:
            recent = [a for (t, a) in self._warm_amps if t >= self.warmup_s - 4.0]
            if not recent:
                recent = [a for (_, a) in self._warm_amps] or [amplitude]
            self.baseline = max(float(np.median(recent)), self.eps)
            self._warm_amps.clear()

        # --- Décision (hystérésis) : le seuil renvoyé EST la frontière de décision ---
        frac      = self.f_exit if self.in_apnea else self.f_enter
        threshold = max(self.eps, frac * self.baseline)
        breathing = amplitude >= threshold
        self.in_apnea = not breathing

        # --- Baseline TOUJOURS adaptée (EMA lente, jamais gelée) ---
        alpha = dt / (self.tau + dt)
        self.baseline = max((1 - alpha) * self.baseline + alpha * amplitude, self.eps)

        return ("active", breathing, threshold, 0.0)
