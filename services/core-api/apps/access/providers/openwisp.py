"""OpenWISP HTTP adapter behind NetworkProvider (ADR-0001, ADR-0006, §11)."""

import logging
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

logger = logging.getLogger(__name__)


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

    def _raise_if_open(self) -> bool:
        with type(self)._circuit_lock:
            if self._opened_at is None:
                return False
            elapsed = time.monotonic() - self._opened_at
            if elapsed < settings.OPENWISP_CIRCUIT_OPEN_SECONDS:
                raise NetworkTemporaryError("OpenWISP circuit is open.")
            if type(self)._probe_in_flight:
                raise NetworkTemporaryError("OpenWISP circuit is open.")
            type(self)._probe_in_flight = True
            return True

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

    def _log_request(
        self,
        method: str,
        path: str,
        subscriber_ref: str,
        status: int | None,
        started_at: float,
    ) -> None:
        level = logging.INFO if status is not None and status < 400 else logging.WARNING
        logger.log(
            level,
            "OpenWISP HTTP request completed",
            extra={
                "http_method": method.upper(),
                "http_url": self._url(path),
                "http_path": path,
                "http_status": status,
                "duration_ms": max(0, (time.monotonic() - started_at) * 1000),
                "subscriber_ref": subscriber_ref,
            },
        )

    def _request(self, method: str, path: str, subscriber_ref: str, **kwargs) -> httpx.Response:
        probe_reserved = self._raise_if_open()
        max_attempts = 1 + settings.OPENWISP_RETRY_MAX

        try:
            for attempt in range(1, max_attempts + 1):
                started_at = time.monotonic()
                try:
                    response = httpx.request(
                        method,
                        self._url(path),
                        headers={"Authorization": f"Bearer {settings.OPENWISP_API_TOKEN}"},
                        timeout=settings.OPENWISP_HTTP_TIMEOUT_SECONDS,
                        **kwargs,
                    )
                except httpx.TimeoutException as error:
                    self._log_request(method, path, subscriber_ref, None, started_at)
                    if attempt < max_attempts:
                        time.sleep(0.2 * 2 ** (attempt - 1))
                        continue
                    self._record_failure()
                    raise NetworkTimeout(str(error)) from error
                except httpx.RequestError as error:
                    self._log_request(method, path, subscriber_ref, None, started_at)
                    if attempt < max_attempts:
                        time.sleep(0.2 * 2 ** (attempt - 1))
                        continue
                    self._record_failure()
                    raise NetworkTemporaryError(str(error)) from error

                self._log_request(
                    method,
                    path,
                    subscriber_ref,
                    response.status_code,
                    started_at,
                )
                if response.status_code >= 500 or response.status_code == 429:
                    if attempt < max_attempts:
                        time.sleep(0.2 * 2 ** (attempt - 1))
                        continue
                    self._record_failure()
                    raise NetworkTemporaryError(f"OpenWISP returned HTTP {response.status_code}.")

                if response.status_code >= 400:
                    raise NetworkPermanentError(f"OpenWISP returned HTTP {response.status_code}.")

                self._record_success()
                return response
        finally:
            if probe_reserved:
                with type(self)._circuit_lock:
                    type(self)._probe_in_flight = False

        raise RuntimeError("unreachable")

    @staticmethod
    def _json(response: httpx.Response):
        try:
            return response.json()
        except (ValueError, httpx.DecodingError) as error:
            raise NetworkPermanentError("OpenWISP returned an invalid JSON response.") from error

    def assign_plan(self, subscriber_ref: str, profile_ref: str) -> AssignmentResult:
        response = self._request(
            "POST",
            "/api/v1/dakar/radius/assign-group/",
            subscriber_ref,
            json={"username": subscriber_ref, "group_name": profile_ref},
        )
        payload = self._json(response)
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
            subscriber_ref,
            params={"username": subscriber_ref},
        )
        results = self._json(response).get("results", [])
        if results:
            return subscriber_ref

        response = self._request(
            "POST",
            "/api/v1/users/user/",
            subscriber_ref,
            json={
                "username": subscriber_ref,
                "password": secrets.token_urlsafe(32),
                "email": f"{subscriber_ref}@radius.dakar-wifi.invalid",
            },
        )
        try:
            user_id = self._json(response)["id"]
        except KeyError as error:
            raise NetworkPermanentError("OpenWISP user response is missing the id.") from error
        self._request(
            "PATCH",
            f"/api/v1/users/user/{user_id}/",
            subscriber_ref,
            json={"organization": settings.OPENWISP_ORGANIZATION_ID},
        )
        return subscriber_ref

    def disconnect(self, subscriber_ref: str) -> list[DisconnectResult]:
        response = self._request(
            "POST",
            "/api/v1/dakar/radius/disconnect/",
            subscriber_ref,
            json={"username": subscriber_ref},
        )
        payload = self._json(response)
        return [
            DisconnectResult(
                session_id=session["session"],
                acknowledged=session.get("status") == "acknowledged",
                detail=session.get("status", ""),
            )
            for session in payload.get("sessions", [])
        ]

    def read_usage(self, subscriber_ref: str) -> Usage:
        path = f"/api/v1/radius/organization/{settings.OPENWISP_ORGANIZATION_SLUG}/account/usage/"
        response = self._request(
            "GET",
            path,
            subscriber_ref,
            params={"username": subscriber_ref},
        )

        seconds_used = 0
        bytes_used = 0
        # The OpenWISP account usage endpoint's ?username= contract is unverified.
        for check in self._json(response).get("checks") or []:
            attribute = check.get("attribute")
            if attribute == "Max-Daily-Session":
                seconds_used = int(check.get("result", 0))
            elif attribute == "Max-Daily-Session-Traffic":
                bytes_used = int(check.get("result", 0))
        return Usage(seconds_used=seconds_used, bytes_used=bytes_used)
