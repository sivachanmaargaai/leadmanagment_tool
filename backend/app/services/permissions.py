"""Module permission checks; record assignment scope remains an additional rule."""
from fastapi import HTTPException
from app.models.role_permissions import RolePermissions


def attach_role_permissions(user, policy):
    user._staff_quotation_access = bool(policy and policy.quotations)
    user._role_permission_snapshot = policy
    return user


def resolve_role_permissions(db, user):
    return attach_role_permissions(user, db.get(RolePermissions, "Staff"))


def quotations_allowed(user):
    # Trusted internal service calls have no HTTP actor. HTTP dependencies always
    # provide the freshly authenticated database account.
    return user is None or user.can_access_quotations


def require_quotations(user):
    if not quotations_allowed(user):
        raise HTTPException(403, "Quotation access is disabled. Ask an administrator for access")
