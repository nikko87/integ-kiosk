import logging
import sys
from datetime import date, timedelta
from typing import Any

import httpx
from tenacity import (
    after_log,
    retry,
    retry_if_result,
    stop_after_attempt,
    stop_after_delay,
    wait_fixed,
)

VITAL_DOC_BASE_URL = "https://h-mj.vitaldoc.com.br/admin/v1/attendance"
SPONSOR_ID = "1ce09866-c945-4f25-ba7a-f6bed5335b51"
TOKEN = "X-APPLICATION-TOKEN--bc73978d4d533a69c7a10b5fca98339799ebd50eae4560455d4793718baacb2c"


logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def create_headers() -> dict[str, str]:
    return {"Authorization": "Bearer " + TOKEN}


def attendances_not_found(value):
    return value["data"] == []


class GetAttendanceDataVitalDocUseCase:

    @retry(
        retry=retry_if_result(attendances_not_found),
        wait=wait_fixed(5),
        stop=stop_after_attempt(6),
        after=after_log(logger, logging.INFO),
    )
    async def execute(self, user_id: str, date: date) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            r_json = await self.send_request(client, date, user_id)

            if attendances_not_found(r_json):
                logger.warning(
                    f"Não foram encontrados atendimentos para o dia"
                    f" {date.isoformat()} . Tentando com data de ontem."
                )

            r_json = await self.try_yesterday(client, date, user_id)

            return r_json

    @staticmethod
    def create_vitaldoc_api_url(attendance_date: date, user_id: str) -> str:
        return f"{VITAL_DOC_BASE_URL}/history?start={attendance_date.isoformat()}&sponsorId={user_id}"

    async def try_yesterday(self, client: httpx.AsyncClient, date: date, user_id: str):
        yesterday = self.get_yesterday(date)
        return await self.send_request(client, yesterday, user_id)

    @staticmethod
    def find_attendance_in_json(attendances: dict, user_id: str) -> dict:
        for data in attendances["data"]:
            patient_id = data["patient"]["id"]
            if patient_id == user_id:
                return data
        return {}

    @staticmethod
    def get_yesterday(d: date) -> date:
        return d - timedelta(days=1)

    async def send_request(
        self, client: httpx.AsyncClient, attendance_date: date, user_id: str
    ):
        url = self.create_vitaldoc_api_url(attendance_date, user_id)
        headers = create_headers()

        r = await client.get(url, headers=headers)
        return r.json()
