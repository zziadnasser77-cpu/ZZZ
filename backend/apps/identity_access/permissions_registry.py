"""Permission registry (ADR-006). Codename = <module>.<resource>.<action>.

Actions: view/create/edit/cancel/approve/post/export/manage. Sensitive fields get their own
permission (e.g. catalog.cost.view) so they can be hidden from users who can see the record.
Each domain app appends its permissions here as it is built.
"""
ACTIONS = ("view", "create", "edit", "cancel", "approve", "post", "export", "manage")

# module -> resource -> allowed actions
REGISTRY: dict[str, dict[str, tuple[str, ...]]] = {
    "identity": {
        "user": ("view", "create", "edit", "manage"),
        "role": ("view", "create", "edit", "manage"),
        "mfa": ("manage",),
    },
    "audit": {"event": ("view", "export")},
    "settings": {
        "organization": ("view", "edit"),
        "numbering": ("view", "edit"),
    },
}


def all_codenames() -> list[str]:
    return [f"{m}.{r}.{a}" for m, res in REGISTRY.items() for r, acts in res.items() for a in acts]


# Default role templates (customizable at runtime). '*' = every permission EXCEPT the
# financial approval family (spec §9: system admin gets no automatic financial approval).
FINANCIAL_APPROVAL_ACTIONS = ("approve", "post")

ROLE_TEMPLATES: dict[str, dict] = {
    "SYSTEM_ADMIN": {"name_ar": "مدير النظام", "name_en": "System Administrator",
                     "perms": ["identity.*", "settings.*", "audit.event.view"]},
    "GENERAL_MANAGER": {"name_ar": "المدير العام", "name_en": "General Manager",
                        "perms": ["audit.event.view", "audit.event.export", "settings.organization.view"]},
    "SALES_MANAGER": {"name_ar": "مدير المبيعات", "name_en": "Sales Manager", "perms": []},
    "SALES_REP": {"name_ar": "موظف المبيعات", "name_en": "Sales Representative", "perms": []},
    "FINANCE_MANAGER": {"name_ar": "المدير المالي", "name_en": "Finance Manager",
                        "perms": ["audit.event.view", "settings.numbering.view"]},
    "ACCOUNTANT": {"name_ar": "المحاسب", "name_en": "Accountant", "perms": []},
    "PROCUREMENT_MANAGER": {"name_ar": "مدير المشتريات", "name_en": "Procurement Manager", "perms": []},
    "WAREHOUSE_KEEPER": {"name_ar": "أمين المخزن", "name_en": "Warehouse Keeper", "perms": []},
    "BIOMED_ENGINEER": {"name_ar": "المهندس الطبي", "name_en": "Biomedical Engineer", "perms": []},
    "LOGISTICS_OFFICER": {"name_ar": "مسؤول اللوجستيات", "name_en": "Logistics Officer", "perms": []},
}


def expand(patterns: list[str]) -> set[str]:
    out: set[str] = set()
    codes = all_codenames()
    for p in patterns:
        if p.endswith(".*"):
            out |= {c for c in codes if c.startswith(p[:-1])}
        elif p in codes:
            out.add(p)
    return out
