from rest_framework.permissions import BasePermission

from .org_scope import shares_organization


class SameOrganizationPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        actor = set(map(str, request.user.organizations_dict.keys()))
        target = set(map(str, obj.organizations_dict.keys()))
        return shares_organization(actor, target)
