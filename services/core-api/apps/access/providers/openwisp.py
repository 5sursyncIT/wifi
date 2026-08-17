"""OpenWISP HTTP adapter behind NetworkProvider (ADR-0001, ADR-0006, §11)."""

import time
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
    _probe_in_flight = False

    @classmethod
    def reset(cls) -> None:
        cls._failures = 0
        cls._opened_at = None
        cls._probe_in_flight = False

    def _url(self, path: str) -> str:
        return urljoin(settings.OPENWISP_BASE_URL.rstrip("/") + "/", path.lstrip("/"))

    def _raise_if_open(self) -> None:
        if self._opened_at is None:
            return
        elapsed = time.monotonic() - self._opened_at
        if elapsed < settings.OPENWISP_CIRCUIT_OPEN_SECONDS:
            raise NetworkTemporaryError("OpenWISP circuit is open.")
        if type(self)._probe_in_flight:
            raise NetworkTemporaryError("OpenWISP circuit is open.")
        type(self)._probe_in_flight = True

    def _record_success(self) -> None:
        type(self)._failures = 0
        type(self)._opened_at = None
        type(self)._probe_in_flight = False

    def _record_failure(self) -> None:
        type(self)._failures += 1
        if type(self)._failures >= settings.OPENWISP_CIRCUIT_FAILURES:
            type(self)._opened_at = time.monotonic()
        type(self)._probe_in_flight = False

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        self._raise_if_open()
        max_attempts = 1 + settings.OPENWISP_RETRY_MAX

        for attempt in range(1, max_attempts + 1):
            try:
                response = httpx.request(
                    method,
                    self._url(path),
                    headers={"Authorization": f"Bearer {settings.OPENWISP_API_TOKEN}"},
                    timeout=settings.OPENWISP_HTTP_TIMEOUT_SECONDS,
                    **kwargs,
                )
            except httpx.TimeoutException as error:
                if attempt < max_attempts:
                    time.sleep(0.2 * 2 ** (attempt - 1))
                    continue
                self._record_failure()
                raise NetworkTimeout(str(error)) from error
            except httpx.TransportError as error:
                if attempt < max_attempts:
                    time.sleep(0.2 * 2 ** (attempt - 1))
                    continue
                self._record_failure()
                raise NetworkTemporaryError(str(error)) from error

            if response.status_code >= 500 or response.status_code == 429:
                if attempt < max_attempts:
                    time.sleep(0.2 * 2 ** (attempt - 1))
                    continue
                self._record_failure()
                raise NetworkTemporaryError(
                    f"OpenWISP returned HTTP {response.status_code}."
                )

            if response.status_code >= 400:
                type(self)._probe_in_flight = False
                raise NetworkPermanentError(
                    f"OpenWISP returned HTTP {response.status_code}."
                )

            self._record_success()
            return response

        raise RuntimeError("unreachable")

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
