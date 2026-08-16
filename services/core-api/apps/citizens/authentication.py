"""DRF authentication for citizens.

Separate from the staff session authentication on purpose (ADR-0007): a citizen token
can never grant anything in the administration, because a citizen is not a Django user.
"""

from rest_framework import authentication, exceptions

from apps.citizens.models import Citizen
from apps.citizens.tokens import InvalidToken, read_access_token


class CitizenUser:
    """Minimal principal DRF can work with. Never a Django user."""

    def __init__(self, citizen: Citizen):
        self.citizen = citizen

    @property
    def is_authenticated(self) -> bool:
        return True


class CitizenTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith(f"{self.keyword} "):
            return None

        token = header[len(self.keyword) + 1 :].strip()
        try:
            citizen_id = read_access_token(token)
        except InvalidToken as error:
            raise exceptions.AuthenticationFailed("Jeton invalide.") from error

        citizen = Citizen.objects.filter(pk=citizen_id).first()
        # Status is re-read on every call: blocking an account must take effect at
        # once, without waiting for the short-lived token to expire.
        if citizen is None or not citizen.is_usable:
            raise exceptions.AuthenticationFailed("Compte inutilisable.")

        return CitizenUser(citizen), token

    def authenticate_header(self, request):
        return self.keyword


def citizen_of(request) -> Citizen:
    """Narrow the DRF principal to the citizen a portal view requires.

    Also a runtime guard: a staff session reaching a citizen endpoint is refused
    rather than crashing on a missing attribute. The two populations are separate
    by design (ADR-0007).
    """
    user = getattr(request, "user", None)
    if not isinstance(user, CitizenUser):
        raise exceptions.AuthenticationFailed("Authentification citoyen requise.")
    return user.citizen
