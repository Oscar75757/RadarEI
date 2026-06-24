"""
Résolution des Plutos par numéro de série (stable entre les sessions)
=====================================================================
L'URI usb:bus.port.addr est attribué dynamiquement par l'OS et change au gré
des branchements/reboots. Le numéro de série, lui, est gravé dans le module.
On scanne donc les Plutos présents et on retrouve l'URI de chaque rôle à partir
de sa série — quel que soit le port ou l'ordre de branchement.
"""

import iio
import config


def _scan_serials() -> dict[str, str]:
    """Retourne {numéro_de_série: uri} pour tous les Plutos branchés en USB."""
    found = {}
    for uri in iio.scan_contexts():            # itère sur les URI détectés
        try:
            serial = dict(iio.Context(uri).attrs).get("hw_serial")
        except Exception:
            continue
        if serial:
            found[serial] = uri
    return found


def resolve_uri(serial: str, role: str) -> str:
    """Retrouve l'URI courant d'un Pluto à partir de son numéro de série.

    Lève une erreur explicite si le module attendu n'est pas branché.
    """
    serials = _scan_serials()
    uri = serials.get(serial)
    if uri is None:
        disponibles = "\n".join(f"    {s}  →  {u}" for s, u in serials.items()) or "    (aucun)"
        raise RuntimeError(
            f"Pluto '{role}' (série {serial}) introuvable.\n"
            f"  Plutos détectés :\n{disponibles}\n"
            f"  → Vérifie le branchement USB et le numéro de série dans config.py."
        )
    print(f"[discovery] {role} : série {serial[-8:]} → {uri}")
    return uri


def resolve_master() -> str:
    return resolve_uri(config.SERIAL_MASTER, "maître TX+RX")


def resolve_rx2() -> str:
    return resolve_uri(config.SERIAL_RX2, "récepteur 2")
