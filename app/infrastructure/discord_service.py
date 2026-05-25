from __future__ import annotations

import logging

import requests


logger = logging.getLogger(__name__)


class DiscordService:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def send_message(self, webhook_url: str | None, message: str) -> bool:
        webhook_url = (webhook_url or "").strip()
        if not webhook_url:
            return False

        try:
            response = requests.post(webhook_url, json={"content": message}, timeout=self.timeout)
            response.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.error("Falha ao enviar notificacao para o Discord: %s", exc)
            return False

    def notify_match_started(self, championship: dict, match: dict) -> bool:
        message = (
            f"🎮 A partida entre {match['time_a']['nome']} e {match['time_b']['nome']} "
            f"foi iniciada no campeonato {championship['nome']}"
        )
        return self.send_message(championship.get("discord_webhook_url"), message)

    def notify_result_registered(self, championship: dict, match: dict, score_a: int, score_b: int) -> bool:
        message = (
            f"🏆 Resultado registrado: {match['time_a']['nome']} {score_a} x {score_b} "
            f"{match['time_b']['nome']} no campeonato {championship['nome']}"
        )
        return self.send_message(championship.get("discord_webhook_url"), message)
