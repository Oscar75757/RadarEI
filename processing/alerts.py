import time
import config


class AlertSystem:
    """Surveille la respiration et déclenche des alertes.

    L'apnée est détectée par ABSENCE d'oscillation (amplitude du signal filtré
    sous le seuil pendant plus de APNEA_DELAY_S), et non par le niveau absolu :
    le passe-haut fait retomber à zéro tout signal figé, donc seul le critère
    « ça ne bouge plus » est fiable (et il reste valable si le patient s'éloigne).

    La bradypnée / tachypnée n'est évaluée que lorsqu'une respiration est présente
    (sinon le rythme issu de la FFT n'a pas de sens).
    """

    def __init__(self):
        self._low_amp_since = None   # instant depuis lequel l'amplitude est basse

    def evaluate(self, rate_rpm: float | None, amplitude: float) -> list[str]:
        """Retourne la liste des alertes actives (vide = tout va bien)."""
        alerts = []
        now = time.time()
        breathing = amplitude >= config.APNEA_AMP_THRESH

        if not breathing:
            # Pas de mouvement respiratoire : on chronomètre le silence.
            if self._low_amp_since is None:
                self._low_amp_since = now
            silent = now - self._low_amp_since
            if silent > config.APNEA_DELAY_S:
                alerts.append(
                    f"APNÉE — aucun mouvement respiratoire depuis {int(silent)} s"
                )
            return alerts   # rythme non significatif quand ça ne respire pas

        # Respiration présente → on remet le chrono à zéro et on juge le rythme.
        self._low_amp_since = None

        if rate_rpm is not None:
            if rate_rpm < config.BRADY_RPM:
                alerts.append(
                    f"BRADYPNÉE — rythme trop lent : {rate_rpm:.1f} rpm "
                    f"(min : {config.BRADY_RPM})"
                )
            elif rate_rpm > config.TACHY_RPM:
                alerts.append(
                    f"TACHYPNÉE — rythme trop rapide : {rate_rpm:.1f} rpm "
                    f"(max : {config.TACHY_RPM})"
                )

        return alerts

    def status_line(self, rate_rpm: float | None, amplitude: float,
                    alerts: list[str]) -> str:
        """Ligne de statut lisible pour la console."""
        rate_str = f"{rate_rpm:4.1f} rpm" if rate_rpm is not None else "  -- rpm"
        head = f"Rythme {rate_str} | ampl {amplitude:.3f} rad"
        if alerts:
            return "⚠️  " + head + "  ||  " + "  ;  ".join(alerts)
        return "✅  " + head
