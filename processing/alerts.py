import time
import config


class AlertSystem:
    """Surveille le rythme respiratoire et déclenche des alertes console."""

    def __init__(self):
        self._last_detection_time = time.time()

    def evaluate(self, rate_rpm: float | None) -> list[str]:
        """Analyse le rythme et retourne la liste des alertes actives (vide = tout va bien)."""
        alerts = []
        now = time.time()

        if rate_rpm is None:
            if now - self._last_detection_time > config.APNEA_DELAY_S:
                alerts.append(
                    f"APNÉE — aucune respiration détectée depuis "
                    f"{int(now - self._last_detection_time)} s"
                )
            return alerts

        self._last_detection_time = now

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

    def print_status(self, rate_rpm: float | None, alerts: list[str]) -> None:
        if rate_rpm is not None:
            status = f"Rythme : {rate_rpm:.1f} resp/min"
        else:
            status = "Rythme : calcul en cours..."

        if alerts:
            for a in alerts:
                print(f"  ⚠️  {a}")
        else:
            print(f"  ✅ {status}")


class CardiacAlertSystem:
    """Surveille le rythme cardiaque et déclenche des alertes console.

    Pas d'alerte d'asystolie par timeout : le signal cardiaque radar est bruité
    et un silence de signal ne peut pas être distingué d'une perte de contact.
    """

    def evaluate(self, rate_bpm: float | None) -> list[str]:
        if rate_bpm is None:
            return []

        alerts = []
        if rate_bpm < config.BRADY_BPM:
            alerts.append(
                f"BRADYCARDIE — rythme trop lent : {rate_bpm:.0f} bpm "
                f"(min : {config.BRADY_BPM})"
            )
        elif rate_bpm > config.TACHY_BPM:
            alerts.append(
                f"TACHYCARDIE — rythme trop rapide : {rate_bpm:.0f} bpm "
                f"(max : {config.TACHY_BPM})"
            )
        return alerts

    def print_status(self, rate_bpm: float | None, alerts: list[str]) -> None:
        if rate_bpm is not None:
            status = f"Cardiaque : {rate_bpm:.0f} bpm"
        else:
            status = "Cardiaque : calcul en cours..."

        if alerts:
            for a in alerts:
                print(f"  ⚠️  {a}")
        else:
            print(f"  ✅ {status}")
