"""
Publication MQTT des données de monitoring respiratoire.

Topics publiés :
  {prefix}/live  — état courant (rythme, amplitude, onde, alertes)  QoS 0, retain

La connexion est asynchrone : si le broker est injoignable, les données sont
silencieusement ignorées (pas de blocage de la boucle radar).
"""

import json
import time
import paho.mqtt.client as mqtt

import config


class MQTTPublisher:

    def __init__(self):
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"radar-pc-{int(time.time())}",
        )
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._connected = False

        self._client.connect_async(config.MQTT_BROKER, config.MQTT_PORT, keepalive=60)
        self._client.loop_start()

    def publish_live(
        self,
        rate_rpm:   float | None,
        amplitude:  float,
        alerts:     list[str],
        wave:       list[float],
        mode:       str = "phase1c",     # "phase1a" ou "phase1c"
        warming:    bool = False,        # True pendant la calibration phase1c
    ) -> None:
        """Publie l'état courant (~6 Hz, QoS 0). Appelé à chaque redessin."""
        if not self._connected:
            return

        step     = max(1, len(wave) // config.MQTT_WAVE_POINTS)
        wave_out = [round(v, 4) for v in wave[::step][-config.MQTT_WAVE_POINTS:]]

        payload = json.dumps({
            "ts":        time.strftime("%Y-%m-%dT%H:%M:%S"),
            "mode":      mode,
            "warming":   warming,
            "rate_rpm":  round(rate_rpm, 1) if rate_rpm is not None else None,
            "amplitude": round(amplitude, 4),
            "alerts":    alerts,
            "wave":      wave_out,
        })
        self._client.publish(f"{config.MQTT_PREFIX}/live", payload, qos=0, retain=True)

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self._connected = True
            print(f"[MQTT] connecté → topic : {config.MQTT_PREFIX}/live")
        else:
            print(f"[MQTT] échec de connexion (code {reason_code})")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self._connected = False
        if reason_code != 0:
            print(f"[MQTT] déconnexion inattendue — reconnexion auto…")
