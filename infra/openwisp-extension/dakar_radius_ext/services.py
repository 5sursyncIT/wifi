"""Business operations missing from the openwisp-radius REST API.

Both operations go through openwisp-radius' own models and helpers. Nothing here
writes to RADIUS tables directly, and nothing patches the upstream package.
"""

import logging

from openwisp_radius.coa import coa_manager
from openwisp_radius.radclient.client import RadClient
from openwisp_radius.utils import load_model

logger = logging.getLogger(__name__)

RadiusAccounting = load_model("RadiusAccounting")
RadiusGroup = load_model("RadiusGroup")
RadiusUserGroup = load_model("RadiusUserGroup")


class GroupNotFound(Exception):
    pass


def assign_group(user, group_name):
    """Move a user to a RADIUS group.

    openwisp-radius watches RadiusUserGroup and pushes a CoA to the NAS of every
    open session, so the change applies to sessions already running. That is what
    activates a plan immediately after payment (cahier des charges §4.3).

    Returns the RadiusUserGroup that is now in effect.
    """
    organization_ids = user.organizations_dict.keys()
    group = RadiusGroup.objects.filter(
        name=group_name, organization_id__in=organization_ids
    ).first()
    if group is None:
        raise GroupNotFound(
            f'No RADIUS group "{group_name}" in the organizations of user "{user}".'
        )

    memberships = list(RadiusUserGroup.objects.filter(user=user).order_by("priority"))

    # The membership must be UPDATED IN PLACE, never deleted and recreated.
    # openwisp-radius triggers the CoA from a pre_save receiver that compares the
    # stored group to the incoming one; a brand-new row has no stored counterpart,
    # the receiver bails out, and the change never reaches the NAS.
    user_group = memberships[0] if memberships else RadiusUserGroup(user=user, priority=1)
    if user_group.pk and user_group.group_id == group.id:
        return user_group

    user_group.group = group
    user_group.full_clean()
    user_group.save()

    # One user carries one plan here, so any extra membership is dropped afterwards.
    for extra in memberships[1:]:
        extra.delete()
    return user_group


def disconnect_user(user):
    """Send a RADIUS Disconnect-Request for every open session of a user.

    openwisp-radius only disconnects as a side effect of an exhausted quota, so an
    operator-initiated disconnect (§8.8) needs this explicit path. Returns a report
    per session rather than raising, because a partial failure is a normal outcome:
    a NAS may be unreachable while others answer.
    """
    sessions = RadiusAccounting.objects.filter(username=user.username, stop_time=None)
    results = []
    for session in sessions:
        secret = coa_manager.get_radsecret_from_radacct(session)
        if not secret:
            results.append(
                {
                    "session": session.unique_id,
                    "nas": session.nas_ip_address,
                    "status": "no_nas_secret",
                }
            )
            continue
        client = RadClient(host=session.nas_ip_address, radsecret=secret)
        acknowledged = client.perform_disconnect({"User-Name": session.username})
        results.append(
            {
                "session": session.unique_id,
                "nas": session.nas_ip_address,
                "status": "acknowledged" if acknowledged else "refused_or_unreachable",
            }
        )
    return results
