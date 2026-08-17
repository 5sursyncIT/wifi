def shares_organization(actor_org_ids: set[str], target_org_ids: set[str]) -> bool:
    return bool(actor_org_ids & target_org_ids)
