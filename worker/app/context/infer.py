"""Workbook context (report §4.3): what kind of workbook this seems to be, with evidence and stated uncertainty.

Deterministic and explainable: every guess lists the column names that led to it. The LLM is not involved.
"""
from ..engine import hints
from ..engine.models import EngineOutput
from ..qa.followups import initial_suggestions
from ..qa.schema import main_table

DOMAINS = {
    "sales": ("Sales and business performance", {"vente", "ventes", "sales", "sale", "client", "customer", "produit", "product", "prix", "price",
              "quantite", "qty", "quantity", "commande", "order", "revenue", "ca", "chiffre", "facture", "invoice", "vendeur", "commercial", "canal", "channel"}),
    "finance": ("Finance and transactions", {"debit", "credit", "solde", "balance", "compte", "account", "budget", "depense", "expense", "recette",
                "tva", "tax", "paiement", "payment", "transaction", "montant", "amount", "cout", "cost", "profit", "marge"}),
    "hr": ("People and HR", {"employe", "employee", "salaire", "salary", "departement", "department", "poste", "position", "embauche", "hire",
           "conge", "leave", "absence", "matricule", "paie", "prime"}),
    "inventory": ("Inventory and stock", {"stock", "sku", "article", "reference", "entrepot", "warehouse", "inventaire", "inventory", "fournisseur",
                  "supplier", "seuil", "quantite"}),
    "education": ("Education and results", {"etudiant", "student", "note", "grade", "classe", "class", "cours", "course", "matiere", "subject",
                  "enseignant", "teacher", "ecole", "school", "examen", "exam"}),
    "project": ("Project and task tracking", {"projet", "project", "tache", "task", "statut", "status", "echeance", "deadline", "responsable",
                "owner", "priorite", "priority", "avancement", "progress", "sprint", "milestone"}),
    "marketing": ("Marketing performance", {"campagne", "campaign", "impressions", "clics", "clicks", "ctr", "conversion", "lead", "leads",
                  "audience", "reach", "engagement", "cpc", "cpm", "annonce"}),
    "operations": ("Operations and logistics", {"livraison", "delivery", "transport", "vehicule", "vehicle", "trajet", "route", "maintenance",
                   "incident", "delai", "duree", "duration", "production", "machine", "qualite", "quality"}),
}
ENTITY_LABEL = {"product": "Products", "location": "Locations", "person": "People", "status": "Statuses", "category": "Categories"}


def infer_domain(out: EngineOutput) -> dict:
    toks = set()
    for t in out.tables:
        toks |= set(hints.tokens(t.name)) | set(hints.tokens(t.sheet))
        for c in t.columns:
            toks |= set(hints.tokens(c.name))
    scored = sorted(((min(1.0, len(toks & vocab) / 5), key, sorted(toks & vocab)) for key, (_, vocab) in DOMAINS.items()), reverse=True)
    top, second = scored[0], scored[1]
    alts = [{"key": k, "label": DOMAINS[k][0], "confidence": round(s, 2)} for s, k, _ in scored[1:3] if s > 0]
    if top[0] >= 0.4 and (top[0] - second[0] >= 0.15 or top[0] >= 0.8):
        return {"key": top[1], "label": DOMAINS[top[1]][0], "confidence": round(top[0], 2), "evidence": top[2][:8], "alternatives": alts}
    return {"key": "generic", "label": "General tabular data", "confidence": round(top[0], 2), "evidence": top[2][:8], "alternatives": alts}


def build_context(out: EngineOutput, schema: dict) -> dict:
    dom = infer_domain(out)
    tabs = [t for t in out.tables if t.columns]
    main = max(tabs, key=lambda t: len(t.rows), default=None)
    entities = {}
    measures, time = [], None
    for t in out.tables:
        for c in t.columns:
            if c.role == "dimension" and c.role_subtype in ENTITY_LABEL:
                entities.setdefault(c.role_subtype, [])
                if c.name not in entities[c.role_subtype]:
                    entities[c.role_subtype].append(c.name)
            if c.role == "measure" and not any(m["name"] == c.name for m in measures):
                measures.append({"name": c.name, "subtype": c.role_subtype, "currency": c.currency})
            if c.role == "time" and time is None and t is main:
                time = {"column": c.name, "from": str(c.stats.get("min", ""))[:10], "to": str(c.stats.get("max", ""))[:10],
                        "granularity": c.stats.get("granularity")}
    sub = {k: v for k, v in entities.items()}
    has_target = any(c.role == "measure" and any(tok in ("target", "objectif", "budget", "forecast", "quota", "plan") for tok in hints.tokens(c.name))
                     for t in out.tables for c in t.columns)
    analyses = []
    if time and any(m["subtype"] in ("amount", "quantity") for m in measures):
        analyses.append("Trend of the main measures over time, and what changed between periods")
    if "product" in sub:
        analyses.append("Product performance: which products contribute most")
    if "location" in sub:
        analyses.append("Regional performance: which locations lead and which lag")
    if "person" in sub:
        analyses.append("Performance by person (for example customers or staff)")
    if "category" in sub or "status" in sub:
        analyses.append("Comparison across categories and statuses")
    if has_target:
        analyses.append("Progress against targets or budgets")
    if any(f.severity in ("high", "medium") for f in out.findings):
        analyses.append("Data-quality review before relying on totals")

    assumptions = []
    curs = sorted({m["currency"] for m in measures if m["currency"]})
    if curs:
        assumptions.append(f"Amounts are treated as {', '.join(curs)} (taken from column names or number formats).")
    for t in out.tables:
        for c in t.columns:
            di = c.date_info
            if di and di.get("text_dates"):
                assumptions.append(f"Text dates in “{c.name}” are read as {'month/day' if di['order_assumed'] == 'mdy' else 'day/month'}.")
                break
    if any(f.code == "duplicate_rows" for f in out.findings):
        assumptions.append("Duplicate rows are counted as they appear in the file.")
    if any(s["hidden"] for s in out.sheets):
        assumptions.append("Hidden sheets are included in the analysis.")
    if time:
        assumptions.append("Incomplete periods at the edges of the data are left out of comparisons.")
    assumptions.append("The workbook type is inferred from column names and may be wrong.")
    unc = None
    if dom["confidence"] < 0.6:
        unc = "The workbook type is uncertain: " + (f"the closest match is “{dom['label']}”." if dom["key"] != "generic" else "no clear match.")
    return {
        "version": 1, "domain": dom, "purpose": dom["label"], "rows": len(main.rows) if main else 0, "tables": len(out.tables),
        "sheets": len(out.sheets), "entities": [{"kind": k, "label": ENTITY_LABEL[k], "columns": v} for k, v in sub.items()],
        "measures": measures[:12], "time": time, "potential_analyses": analyses[:6], "assumptions": assumptions, "uncertainty": unc,
        "suggested_questions": initial_suggestions(schema),
    }
