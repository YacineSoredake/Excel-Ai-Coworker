"""Bilingual (FR/EN/AR) vocabulary used to interpret column names."""
import re

from .textutil import name_tokens, norm_key

CURRENCY_TOKENS = {
    "da": "DZD", "dzd": "DZD", "دج": "DZD", "dinar": "DZD", "dinars": "DZD",
    "$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR", "euro": "EUR", "£": "GBP", "gbp": "GBP",
}
CURRENCY_CODES = {"dzd", "da", "usd", "eur", "gbp"}
UNIT_TOKENS = {"kg", "g", "l", "ml", "m", "cm", "km", "m2", "pcs", "h", "min", "jours", "days", "units"}

ID = {"id", "uuid", "code", "ref", "reference", "sku", "matricule", "identifiant", "numero", "num", "nr", "no"}
QUANTITY = {"qty", "quantity", "quantite", "qte", "nombre", "nb", "stock", "units", "unites", "volume", "poids", "weight", "كمية"}
AMOUNT = {"total", "montant", "amount", "revenue", "revenu", "ca", "chiffre", "sales", "ventes", "vente", "cost", "cout",
          "depense", "expense", "recette", "salaire", "salary", "budget", "profit", "marge", "margin", "benefice",
          "valeur", "value", "solde", "balance", "tva", "tax", "taxe", "مبلغ", "مجموع"}
PRICE = {"prix", "price", "tarif", "pu", "سعر"}
RATE = {"taux", "rate", "pct", "percent", "pourcentage", "ratio"}
NON_NEGATIVE = QUANTITY | PRICE | {"montant", "amount", "total", "stock", "revenue", "sales", "ventes", "cost", "cout"}

LOCATION = {"wilaya", "ville", "city", "region", "pays", "country", "commune", "daira", "province", "zone",
            "lieu", "location", "localite", "ولاية", "مدينة"}
PERSON = {"client", "customer", "vendeur", "commercial", "employe", "employee", "name", "nom", "prenom", "agent",
          "representant", "rep", "utilisateur", "user", "fournisseur", "supplier", "manager", "responsable",
          "salesperson", "student", "etudiant", "patient", "زبون", "عميل", "اسم"}
PRODUCT = {"produit", "product", "article", "item", "designation", "libelle", "marque", "brand", "منتج", "سلعة"}
STATUS = {"statut", "status", "etat", "state", "situation"}
CATEGORY = {"categorie", "category", "type", "famille", "family", "groupe", "group", "segment", "canal", "channel",
            "mode", "method", "departement", "department", "service", "classe", "class", "paiement", "payment"}
PERIOD = {"annee", "year", "an", "mois", "month", "trimestre", "quarter", "semestre", "semaine", "week",
          "jour", "day", "periode", "period"}
BOOLEAN_HINTS = {"is", "has", "actif", "active", "flag", "paid", "valide", "valid", "annule", "cancelled"}

_PAREN = re.compile(r"[\(\[]([^)\]]+)[\)\]]")


def tokens(label) -> list[str]:
    return name_tokens(label)


def any_hint(toks: list[str], vocab: set[str]) -> bool:
    return any(t in vocab for t in toks)


def header_currency_and_unit(label: str) -> tuple[str | None, str | None]:
    """'Prix unitaire (DA)' -> ('DZD', None); 'weight_kg' -> (None, 'kg')."""
    toks = tokens(label)
    currency = next((CURRENCY_TOKENS[t] for t in toks if t in CURRENCY_CODES), None)
    unit = None
    m = _PAREN.search(str(label))
    if m:
        inner = m.group(1).strip()
        key = norm_key(inner)
        if key in CURRENCY_TOKENS:
            currency = currency or CURRENCY_TOKENS[key]
        elif len(inner) <= 12:
            unit = inner
    if unit is None:
        unit = next((t for t in toks[1:] if t in UNIT_TOKENS), None)
    return currency, unit


def currency_from_format(fmt: str | None) -> str | None:
    if not fmt:
        return None
    f = fmt.casefold()
    for token, code in (("dzd", "DZD"), ('"da"', "DZD"), ("د.ج", "DZD"), ("€", "EUR"), ("eur", "EUR"),
                        ("£", "GBP"), ("usd", "USD"), ("$", "USD")):
        if token in f:
            return code
    return None
