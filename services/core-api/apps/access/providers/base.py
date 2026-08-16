"""Contract between the business platform and whatever drives the network.

Isolating this keeps the domain free of OpenWISP specifics (§4.3, §6.2) and lets a
UniFi or a laboratory implementation appear later without touching business code.
`assign_plan` and `disconnect` are part of the contract because openwisp-radius has no
REST endpoint for either — see ADR-0006.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class NetworkError(Exception):
    """Base for every network-side failure."""

    retryable = False


class NetworkTimeout(NetworkError):
    """The equipment or controller did not answer in time."""

    retryable = True


class NetworkTemporaryError(NetworkError):
    """A transient failure. The caller should retry with backoff."""

    retryable = True


class NetworkPermanentError(NetworkError):
    """A refusal that retrying cannot fix. Needs an operator."""

    retryable = False


class SessionAlreadyActive(NetworkError):
    """The subscriber already holds an active session where none was expected."""

    retryable = False


class QuotaExhausted(NetworkError):
    """The subscriber has already consumed the allowance being applied."""

    retryable = False


@dataclass(frozen=True)
class AssignmentResult:
    applied: bool
    profile_ref: str
    detail: str = ""


@dataclass(frozen=True)
class DisconnectResult:
    session_id: str
    acknowledged: bool
    detail: str = ""


@dataclass(frozen=True)
class Usage:
    seconds_used: int = 0
    bytes_used: int = 0
    sessions: list = field(default_factory=list)


class NetworkProvider(ABC):
    """Operations the platform needs from the network layer."""

    name: str

    @abstractmethod
    def healthcheck(self) -> bool:
        """True when the provider believes the network side is reachable."""

    @abstractmethod
    def ensure_user(self, subscriber_ref: str) -> str:
        """Create or confirm the RADIUS subscriber, returning its username."""

    @abstractmethod
    def assign_plan(self, subscriber_ref: str, profile_ref: str) -> AssignmentResult:
        """Apply a plan profile, taking effect on sessions already running."""

    @abstractmethod
    def disconnect(self, subscriber_ref: str) -> list[DisconnectResult]:
        """Close every open session of a subscriber, one result per session."""

    @abstractmethod
    def read_usage(self, subscriber_ref: str) -> Usage:
        """Consumption counters as the network layer sees them."""
