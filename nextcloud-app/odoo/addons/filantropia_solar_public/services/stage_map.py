"""CRM stage → NC lifecycle intent (pure helpers for unit tests)."""

from __future__ import annotations


def is_qualified_stage(stage_name: str | None, *, is_won: bool = False) -> bool:
    """True when CRM stage means NGO was qualified (promote Virtual→Planned)."""
    if is_won:
        return False
    name = (stage_name or "").casefold()
    return "qualif" in name


def is_won_stage(*, is_won: bool = False, stage_name: str | None = None) -> bool:
    """Won must never trigger mark-installed (D4)."""
    if is_won:
        return True
    name = (stage_name or "").casefold()
    return name in {"won", "ganho", "won / signed"} or name.endswith(" won")


def lifecycle_action_for_stage_change(
    old_name: str | None,
    new_name: str | None,
    *,
    old_is_won: bool = False,
    new_is_won: bool = False,
) -> str | None:
    """
    Return NC action for a stage transition, or None.

    - promote_planned: entering Qualified (not Won)
    - noop for Won (explicit None; callers must not mark-installed)
    """
    if is_won_stage(is_won=new_is_won, stage_name=new_name):
        return None
    if is_qualified_stage(new_name, is_won=new_is_won) and not is_qualified_stage(
        old_name, is_won=old_is_won
    ):
        return "promote_planned"
    return None
