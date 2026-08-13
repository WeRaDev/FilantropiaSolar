"""CRM stage <-> NC lifecycle intent (pure helpers for unit tests).

Mirror table (ADR 0006 supersedes ADR 0004 Won-noop):
  New         -> none (no station required)
  Qualified   -> Virtual
  Proposition -> Planned
  Installed   -> Running  (renamed from Won; is_won stage)
"""

from __future__ import annotations


def _name(stage_name: str | None) -> str:
    return (stage_name or "").casefold().strip()


def is_new_stage(stage_name: str | None) -> bool:
    n = _name(stage_name)
    return n in {"new", "novo", "nova"} or n.startswith("new ")


def is_qualified_stage(stage_name: str | None, *, is_won: bool = False) -> bool:
    """True when CRM stage means NGO was qualified (NC Virtual)."""
    if is_won:
        return False
    n = _name(stage_name)
    return "qualif" in n


def is_proposition_stage(stage_name: str | None, *, is_won: bool = False) -> bool:
    """Proposition / proposal stage -> NC Planned."""
    if is_won:
        return False
    n = _name(stage_name)
    return (
        "proposition" in n
        or "proposal" in n
        or "proposta" in n
        or n in {"proposition", "proposition / quote"}
    )


def is_installed_stage(*, is_won: bool = False, stage_name: str | None = None) -> bool:
    """Installed (ex-Won) -> NC Running. Matches is_won flag or name."""
    if is_won:
        return True
    n = _name(stage_name)
    return (
        n
        in {
            "won",
            "ganho",
            "won / signed",
            "installed",
            "instalado",
            "instalada",
        }
        or n.endswith(" won")
        or n.startswith("installed")
    )


def is_won_stage(*, is_won: bool = False, stage_name: str | None = None) -> bool:
    """Backward-compatible alias: Won/Installed terminal stage."""
    return is_installed_stage(is_won=is_won, stage_name=stage_name)


def nc_state_for_stage(stage_name: str | None, *, is_won: bool = False) -> str | None:
    """Map CRM stage to target NC lifecycle_state, or None for New/unlinked."""
    if is_installed_stage(is_won=is_won, stage_name=stage_name):
        return "running"
    if is_proposition_stage(stage_name, is_won=is_won):
        return "planned"
    if is_qualified_stage(stage_name, is_won=is_won):
        return "virtual"
    return None


def stage_xmlid_for_nc_state(lifecycle_state: str | None) -> str | None:
    """Full xmlid (module.xmlid) for inbound NC->CRM mapping onto core CRM stages."""
    state = (lifecycle_state or "").casefold().strip()
    return {
        "virtual": "crm.stage_lead2",  # Qualified
        "planned": "crm.stage_lead3",  # Proposition
        "running": "crm.stage_lead4",  # Installed (ex-Won)
    }.get(state)


def lifecycle_action_for_stage_change(
    old_name: str | None,
    new_name: str | None,
    *,
    old_is_won: bool = False,
    new_is_won: bool = False,
) -> str | None:
    """
    Return NC action for a stage transition, or None.

    - ensure_virtual: entering Qualified
    - promote_planned: entering Proposition
    - mark_installed: entering Installed (ex-Won)
    """
    old_target = nc_state_for_stage(old_name, is_won=old_is_won)
    new_target = nc_state_for_stage(new_name, is_won=new_is_won)
    if new_target is None or new_target == old_target:
        return None
    if new_target == "virtual":
        return "ensure_virtual"
    if new_target == "planned":
        return "promote_planned"
    if new_target == "running":
        return "mark_installed"
    return None
