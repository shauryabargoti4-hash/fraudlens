"""Role-Based Access Control (RBAC) Module for ClauseGuard.

Enforces role permissions via lightweight request headers (X-User-Role, X-User-Name)
without breaking existing endpoints or one-click exhibition workflows.
"""

from typing import Optional
from fastapi import Header, HTTPException, status, Depends
from backend.models.enums import UserRole


def get_current_user_role(
    x_user_role: Optional[str] = Header(None, description="Active user role (AUDITOR or SENIOR_ADJUDICATOR)"),
) -> UserRole:
    """Extracts user role from header or defaults cleanly to AUDITOR."""
    if not x_user_role:
        return UserRole.AUDITOR
    val = x_user_role.strip().upper()
    if val == UserRole.SENIOR_ADJUDICATOR.value:
        return UserRole.SENIOR_ADJUDICATOR
    return UserRole.AUDITOR


def get_current_user_name(
    x_user_name: Optional[str] = Header(None, description="Operator or adjudicator display name"),
    role: UserRole = Depends(get_current_user_role),
) -> str:
    """Extracts username from header or provides role-appropriate default."""
    if x_user_name and x_user_name.strip():
        return x_user_name.strip()
    if role == UserRole.SENIOR_ADJUDICATOR:
        return "Senior Claims Adjudicator"
    return "Staff Claims Auditor"


def require_role(required_role: UserRole):
    """Dependency factory checking that the caller possesses the required role."""

    def role_checker(role: UserRole = Depends(get_current_user_role)) -> UserRole:
        if role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: this operation requires '{required_role.value}' role privileges. Current role is '{role.value}'.",
            )
        return role

    return role_checker
