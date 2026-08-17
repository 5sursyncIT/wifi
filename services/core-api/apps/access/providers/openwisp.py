"""OpenWISP HTTP adapter behind NetworkProvider (ADR-0001, ADR-0006, §11)."""

from urllib.parse import urljoin

import httpx
from django.conf import settings

from apps.access.providers.base import (
    AssignmentResult,
    NetworkPermanentError,
    NetworkProvider,
    NetworkTemporaryError,
    NetworkTimeout,
)


class OpenWispClient(NetworkProvider):
    name = "openwisp"
    _failures = 0
    _opened_at: float | None = None

    @classmethod
    def reset(cls) -> None:
        cls._failures = 0
        cls._opened_at = None

    def _url(self, path: str) -> str:
        return urljoin(settings.OPENWISP_BASE_URL.rstrip("/") + "/", path.lstrip("/"))

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = httpx.request(
                method,
                self._url(path),
                headers={"Authorization": f"Bearer {settings.OPENWISP_API_TOKEN}"},
                timeout=settings.OPENWISP_HTTP_TIMEOUT_SECONDS,
                **kwargs,
            )
        except httpx.TimeoutException as error:
            raise NetworkTimeout(str(error)) from error
        except httpx.TransportError as error:
            raise NetworkTemporaryError(str(error)) from error

        if response.status_code >= 500 or response.status_code == 429:
            raise NetworkTemporaryError(
                f"OpenWISP returned HTTP {response.status_code}."
            )
        if response.status_code >= 400:
            raise NetworkPermanentError(
                f"OpenWISP returned HTTP {response.status_code}."
            )
        return response

    def assign_plan(self, subscriber_ref: str, profile_ref: str) -> AssignmentResult:
        response = self._request(
            "POST",
            "/api/v1/dakar/radius/assign-group/",
            json={"username": subscriber_ref, "group_name": profile_ref},
        )
        payload = response.json()
        changed = payload.get("changed", True)
        return AssignmentResult(
            applied=bool(changed),
            profile_ref=profile_ref,
            detail="" if changed else "already assigned",
        )

    def healthcheck(self) -> bool:
        raise NotImplementedError

    def ensure_user(self, subscriber_ref: str) -> str:
        raise NotImplementedError

    def disconnect(self, subscriber_ref: str):
        raise NotImplementedError

    def read_usage(self, subscriber_ref: str):
        raise NotImplementedError
