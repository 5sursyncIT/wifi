"""OpenWISP HTTP adapter behind NetworkProvider (ADR-0001, ADR-0006, §11)."""

import secrets
import threading
import time
from urllib.parse import urljoin

import httpx
from django.conf import settings

from apps.access.providers.base import (
    AssignmentResult,
    DisconnectResult,
    NetworkError,
    NetworkPermanentError,
    NetworkProvider,
    NetworkTemporaryError,
    NetworkTimeout,
    Usage,
)


class OpenWispClient(NetworkProvider):
    name = "openwisp"
    _failures = 0
    _opened_at: float | None = None
    _probe_in_flight = False
    _circuit_lock = threading.Lock()

    @classmethod
    def reset(cls) -> None:
        cls._failures = 0
        cls._opened_at = None
        cls._probe_in_flight = False

    def _url(self, path: str) -> str:
        return urljoin(settings.OPENWISP_BASE_URL.rstrip("/") + "/", path.lstrip("/"))

    def _raise_if_open(self) -> None:
        with type(self)._circuit_lock:
            if self._opened_at is None:
                return
            elapsed = time.monotonic() - self._opened_at
            if elapsed < settings.OPENWISP_CIRCUIT_OPEN_SECONDS:
                raise NetworkTemporaryError("OpenWISP circuit is open.")
            if type(self)._probe_in_flight:
                raise NetworkTemporaryError("OpenWISP circuit is open.")
            type(self)._probe_in_flight = True

    def _record_success(self) -> None:
        with type(self)._circuit_lock:
            type(self)._failures = 0
            type(self)._opened_at = None
            type(self)._probe_in_flight = False

    def _record_failure(self) -> None:
        with type(self)._circuit_lock:
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
                with type(self)._circuit_lock:
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
        try:
            response = httpx.request(
                "GET",
                self._url("/api/v1/users/user/"),
                params={"limit": 1},
                headers={"Authorization": f"Bearer {settings.OPENWISP_API_TOKEN}"},
                timeout=settings.OPENWISP_HTTP_TIMEOUT_SECONDS,
            )
        except (NetworkError, httpx.HTTPError):
            return False
        if response.status_code >= 400:
            return False
        return True

    def ensure_user(self, subscriber_ref: str) -> str:
        response = self._request(
            "GET",
            "/api/v1/users/user/",
            params={"username": subscriber_ref},
        )
        results = response.json().get("results", [])
        if results:
            return subscriber_ref

        response = self._request(
            "POST",
            "/api/v1/users/user/",
            json={
                "username": subscriber_ref,
                "password": secrets.token_urlsafe(32),
                "email": f"{subscriber_ref}@radius.dakar-wifi.invalid",
            },
        )
        user_id = response.json()["id"]
        self._request(
            "PATCH",
            f"/api/v1/users/user/{user_id}/",
            json={"organization": settings.OPENWISP_ORGANIZATION_ID},
        )
        return subscriber_ref

    def disconnect(self, subscriber_ref: str) -> list[DisconnectResult]:
        response = self._request(
            "POST",
            "/api/v1/dakar/radius/disconnect/",
            json={"username": subscriber_ref},
        )
        payload = response.json()
        return [
            DisconnectResult(
                session_id=session["session"],
                acknowledged=session.get("status") == "acknowledged",
                detail=session.get("status", ""),
            )
            for session in payload.get("sessions", [])
        ]

    def read_usage(self, subscriber_ref: str) -> Usage:
        path = (
            f"/api/v1/radius/organization/{settings.OPENWISP_ORGANIZATION_SLUG}"
            "/account/usage/"
        )
        response = self._request(
            "GET",
            path,
            params={"username": subscriber_ref},
        )

        seconds_used = 0
        bytes_used = 0
        for check in response.json().get("checks", []):
            attribute = check.get("attribute")
            if attribute == "Max-Daily-Session":
                seconds_used = int(check.get("result", 0))
            elif attribute == "Max-Daily-Session-Traffic":
                bytes_used = int(check.get("result", 0))
        return Usage(seconds_used=seconds_used, bytes_used=bytes_used)
