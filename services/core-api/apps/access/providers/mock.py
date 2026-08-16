"""In-memory network provider covering the failure modes of §11.3.

Every scenario is reachable by setting `MockNetworkProvider.scenario`, so the retry,
outbox and reconciliation paths of phases 3 and 4 can be exercised without any
equipment. State is class-level and reset between tests.
"""

from apps.access.providers.base import (
    AssignmentResult,
    DisconnectResult,
    NetworkPermanentError,
    NetworkProvider,
    NetworkTemporaryError,
    NetworkTimeout,
    QuotaExhausted,
    SessionAlreadyActive,
    Usage,
)

SCENARIOS = (
    "success",
    "timeout",
    "temporary_error",
    "permanent_error",
    "session_already_active",
    "quota_exhausted",
    "duplicate_accounting",
)

_FAILURES = {
    "timeout": (NetworkTimeout, "Le contrôleur n'a pas répondu."),
    "temporary_error": (NetworkTemporaryError, "Indisponibilité temporaire du contrôleur."),
    "permanent_error": (NetworkPermanentError, "Profil refusé par le contrôleur."),
    "session_already_active": (SessionAlreadyActive, "Une session est déjà ouverte."),
    "quota_exhausted": (QuotaExhausted, "Quota déjà épuisé."),
}


class MockNetworkProvider(NetworkProvider):
    name = "mock"

    scenario: str = "success"
    assignments: dict[str, str] = {}
    assignment_calls: int = 0
    subscribers: set[str] = set()
    # subscriber -> {unique_id: (seconds, bytes)}; keyed by unique_id so replaying an
    # accounting record cannot count twice, exactly as OpenWISP behaves.
    accounting: dict[str, dict[str, tuple[int, int]]] = {}

    @classmethod
    def reset(cls) -> None:
        cls.scenario = "success"
        cls.assignments = {}
        cls.assignment_calls = 0
        cls.subscribers = set()
        cls.accounting = {}

    def _raise_if_scenario_fails(self) -> None:
        failure = _FAILURES.get(type(self).scenario)
        if failure is not None:
            error_class, message = failure
            raise error_class(message)

    def healthcheck(self) -> bool:
        return type(self).scenario not in _FAILURES

    def ensure_user(self, subscriber_ref: str) -> str:
        self._raise_if_scenario_fails()
        type(self).subscribers.add(subscriber_ref)
        return subscriber_ref

    def assign_plan(self, subscriber_ref: str, profile_ref: str) -> AssignmentResult:
        type(self).assignment_calls += 1
        self._raise_if_scenario_fails()
        type(self).subscribers.add(subscriber_ref)
        type(self).assignments[subscriber_ref] = profile_ref
        return AssignmentResult(applied=True, profile_ref=profile_ref)

    def disconnect(self, subscriber_ref: str) -> list[DisconnectResult]:
        self._raise_if_scenario_fails()
        sessions = type(self).accounting.get(subscriber_ref, {})
        return [
            DisconnectResult(session_id=session_id, acknowledged=True)
            for session_id in sorted(sessions)
        ]

    def read_usage(self, subscriber_ref: str) -> Usage:
        sessions = type(self).accounting.get(subscriber_ref, {})
        return Usage(
            seconds_used=sum(seconds for seconds, _ in sessions.values()),
            bytes_used=sum(volume for _, volume in sessions.values()),
            sessions=sorted(sessions),
        )

    def record_accounting(
        self, subscriber_ref: str, unique_id: str, seconds: int, bytes_total: int
    ) -> None:
        """Simulate an accounting record arriving from the gateway."""
        sessions = type(self).accounting.setdefault(subscriber_ref, {})
        sessions[unique_id] = (seconds, bytes_total)
