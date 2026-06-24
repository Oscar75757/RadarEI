"""
Synchronisation logicielle du 2e récepteur (phase 1d)
=====================================================
Le Pluto 2 reçoit avec son propre oscillateur, décalé de Δf par rapport au TX
du maître. Mais il entend aussi le TRAJET DIRECT de l'émission CW : une raie
forte décalée précisément de Δf. On l'utilise comme référence pour dérotater
le signal et retrouver la cohérence avec l'émetteur — sans aucun câble.

Non encore branché dans la boucle principale : la phase 1 valide d'abord le
canal cohérent du maître. Ces fonctions sont prêtes pour l'étape suivante.
"""

import numpy as np
import config


def estimate_cfo(iq: np.ndarray, fs: float = config.SAMPLE_RATE) -> float:
    """Estime le décalage de fréquence Δf (Hz) du canal via sa raie dominante.

    L'émission étant une CW pure, le trajet direct apparaît comme le pic le plus
    fort du spectre ; sa position donne Δf.
    """
    spectrum = np.abs(np.fft.fftshift(np.fft.fft(iq)))
    freqs    = np.fft.fftshift(np.fft.fftfreq(len(iq), d=1.0 / fs))
    return float(freqs[np.argmax(spectrum)])


def derotate(iq: np.ndarray, cfo: float, fs: float = config.SAMPLE_RATE) -> np.ndarray:
    """Compense le décalage de fréquence : ramène la raie directe à DC.

    Après cette correction, la phase du 2e canal est cohérente avec l'émetteur,
    comme si les deux Plutos partageaient la même horloge.
    """
    n = np.arange(len(iq))
    return iq * np.exp(-1j * 2 * np.pi * cfo * n / fs)


def synchronize(iq_second: np.ndarray) -> np.ndarray:
    """Pipeline complet : estime Δf sur le trajet direct puis dérotate le canal."""
    cfo = estimate_cfo(iq_second)
    return derotate(iq_second, cfo)
