import html as _html
import markdown as _md

# tension -> (libellé avec emoji, fond pastille, couleur texte)
_TENSION = {
    "vert": ("🟢 Places disponibles", "#dcfce7", "#15803d"),
    "jaune": ("🟡 Tension modérée", "#fef3c7", "#b45309"),
    "orange": ("🟠 Service sollicité", "#ffedd5", "#c2410c"),
    "rouge": ("🔴 Service très sollicité", "#fee2e2", "#b91c1c"),
}

def render_richblock(block):
    if not block:
        return ""
    if block["format"] == "html":
        return block["content"]
    return _md.markdown(block["content"])

def tension_badge(tension):
    """Pastille de tension en pilule colorée (vide si tension inconnue/None)."""
    if not tension or tension not in _TENSION:
        return ""
    label, bg, fg = _TENSION[tension]
    return (f'<span style="display:inline-block;background:{bg};color:{fg};'
            f'font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px;'
            f'white-space:nowrap;vertical-align:middle;">{label}</span>')

def _first_name(nom):
    # Les noms conseiller du MD sont nom-de-famille d'abord (composé possible,
    # ex. fictif "MARTIN DUPONT Alex") ; le prénom est le dernier token.
    parts = (nom or "").split()
    return parts[-1] if parts else ""

def default_intro(conseiller):
    prenom = _first_name(conseiller.get("nom", ""))
    salut = f"Bonjour {prenom}," if prenom else "Bonjour,"
    return (f"{salut}<br><br>Voici les solutions de parcours structurées "
            f"identifiées pour les bénéficiaires de votre portefeuille convoqués "
            f"cette semaine, sur la base de leurs critères d'éligibilité.")

DEFAULT_REMARQUES = [
    "Les recommandations sont établies automatiquement et nécessitent une validation en entretien.",
    "Structures géolocalisées sur le secteur (< 20 km pour l'IAE, < 10 km pour les services).",
]

def esc(s):
    return _html.escape(s or "")
