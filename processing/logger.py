import csv
import os
from datetime import datetime


class SessionLogger:
    """Journalise la session de monitoring dans un CSV horodaté (logs/).

    Une ligne par évaluation : horodatage, rythme, amplitude, alertes actives.
    Permet de rejouer/analyser une séance en conditions réelles hors-ligne.
    """

    def __init__(self, directory: str = "logs"):
        os.makedirs(directory, exist_ok=True)
        fname = datetime.now().strftime("session_%Y%m%d_%H%M%S.csv")
        self._path = os.path.join(directory, fname)
        self._f = open(self._path, "w", newline="")
        self._w = csv.writer(self._f)
        self._w.writerow(["horodatage", "rythme_rpm", "amplitude_rad", "alertes"])
        self._f.flush()

    def log(self, rate_rpm: float | None, amplitude: float,
            alerts: list[str]) -> None:
        self._w.writerow([
            datetime.now().isoformat(timespec="seconds"),
            f"{rate_rpm:.1f}" if rate_rpm is not None else "",
            f"{amplitude:.4f}",
            " | ".join(alerts),
        ])
        self._f.flush()

    @property
    def path(self) -> str:
        return self._path

    def close(self) -> None:
        self._f.close()
