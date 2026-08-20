"""CRM stage <-> NC lifecycle intent (pure helpers for unit tests).

Mirror table (ADR 0006 supersedes ADR 0004 Won-noop):
  New         -> none (no station required)
  Qualified   -> Virtual
  Proposition -> Planned
  Installed   -> Running  (renamed from Won; is_won stage)
  Archived    -> Running + public_archived (hide public map; keep stats)
"""

from __future__ import annotations


def _name(stage_name: str | None) -> str:
    return (stage_name or "").casefold().strip()


def is_new_stage(stage_name: str | None) -> bool:
    n = _name(stage_name)
    return n in {"new", "novo", "nova"} or n.startswith("new ")


def is_archived_stage(stage_name: str | None, *, is_won: bool = False) -> bool:
    """Archived CRM stage: running station hidden from public map."""
    if is_won:
        return False
    n = _name(stage_name)
    return n in {"archived", "arquivado", "arquivada"} or n.startswith("archived")


def is_qualified_stage(stage_name: str | None, *, is_won: bool = False) -> bool:
    """True when CRM stage means NGO was qualified (NC Virtual)."""
    if is_won or is_archived_stage(stage_name, is_won=is_won):
        return False
    n = _name(stage_name)
    return "qualif" in n


def is_proposition_stage(stage_name: str | None, *, is_won: bool = False) -> bool:
    """Proposition / proposal stage -> NC Planned."""
    if is_won or is_archived_stage(stage_name, is_won=is_won):
        return False
    n = _name(stage_name)
    return (
        "proposition" in n
        or "proposal" in n
        or "proposta" in n
        or n in {"proposition", "proposition / quote"}
    )


def is_installed_stage(*, is_won: bool = False, stage_name: str | None = None) -> bool:
    """Installed (ex-Won) -> NC Running (public map). Matches is_won flag or name."""
    if is_archived_stage(stage_name, is_won=False):
        return False
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
    if is_archived_stage(stage_name, is_won=is_won):
        return "running"
    if is_installed_stage(is_won=is_won, stage_name=stage_name):
        return "running"
    if is_proposition_stage(stage_name, is_won=is_won):
        return "planned"
    if is_qualified_stage(stage_name, is_won=is_won):
        return "virtual"
    return None


def stage_xmlid_for_nc_state(
    lifecycle_state: str | None,
    *,
    public_archived: bool = False,
) -> str | None:
    """Full xmlid (module.xmlid) for inbound NC->CRM mapping onto CRM stages."""
    state = (lifecycle_state or "").casefold().strip()
    if state == "running" and public_archived:
        return "filantropia_solar_public.stage_archived"
    return {
        "virtual": "crm.stage_lead2",  # Qualified
        "planned": "crm.stage_lead3",  # Proposition
        "running": "crm.stage_lead4",  # Installed (ex-Won)
    }.get(state)


def _state_rank(state: str | None) -> int:
    """Order virtual < planned < running for promote vs demote."""
    return {"virtual": 1, "planned": 2, "running": 3}.get((state or "").casefold(), 0)


def lifecycle_action_for_stage_change(
    old_name: str | None,
    new_name: str | None,
    *,
    old_is_won: bool = False,
    new_is_won: bool = False,
) -> str | None:
    """
    Return NC action for a stage transition, or None.

    Promotions:
    - ensure_virtual: entering Qualified (create if missing)
    - promote_planned: entering Proposition from below
    - mark_installed: entering Installed (ex-Won)
    - set_public_archived / clear_public_archived: Archived <-> Installed

    Demotions (rank decreases) use set-lifecycle:
    - set_lifecycle_virtual: Installed/Proposition/Archived → Qualified
    - set_lifecycle_planned: Installed/Archived → Proposition
    """
    old_archived = is_archived_stage(old_name, is_won=old_is_won)
    new_archived = is_archived_stage(new_name, is_won=new_is_won)
    if new_archived and not old_archived:
        return "set_public_archived"
    if (
        old_archived
        and not new_archived
        and is_installed_stage(is_won=new_is_won, stage_name=new_name)
    ):
        return "clear_public_archived"

    old_target = nc_state_for_stage(old_name, is_won=old_is_won)
    new_target = nc_state_for_stage(new_name, is_won=new_is_won)
    if new_target is None:
        return None
    # Same lifecycle target (e.g. Archived already running) — only archive toggles above.
    if new_target == old_target and not (old_archived or new_archived):
        return None
    if new_target == old_target and old_archived and new_archived:
        return None
    # Explicit demotion when moving down the lifecycle ladder.
    if old_target and _state_rank(new_target) < _state_rank(old_target):
        if new_target == "virtual":
            return "set_lifecycle_virtual"
        if new_target == "planned":
            return "set_lifecycle_planned"
        return None
    if new_target == "virtual":
        return "ensure_virtual"
    if new_target == "planned":
        return "promote_planned"
    if new_target == "running":
        # Entering Installed from below (or from Archived handled above).
        if old_archived:
            return "clear_public_archived"
        return "mark_installed"
    return None
