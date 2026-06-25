import time
from pathlib import Path

# sorties NOMINATIVES (vrais noms) à purger par défaut
_DEFAULT_DIRS = ["out/json-nom", "out/html"]


def _candidates(dirs, older_than_days, now=None):
    """Fichiers des dossiers donnés dont l'âge (mtime) dépasse le seuil."""
    now = time.time() if now is None else now
    cutoff = now - older_than_days * 86400
    out = []
    for d in dirs:
        p = Path(d)
        if not p.exists():
            continue
        for f in sorted(p.rglob("*")):
            if f.is_file() and f.stat().st_mtime < cutoff:
                out.append(f)
    return out


def run_purge(dirs=None, older_than_days=7, assume_yes=False):
    dirs = dirs or _DEFAULT_DIRS
    files = _candidates(dirs, older_than_days)
    if not files:
        print(f"purge : rien à effacer (aucune sortie nominative de plus de "
              f"{older_than_days} j dans {', '.join(dirs)}).")
        return
    total_ko = sum(f.stat().st_size for f in files) / 1024
    print(f"⚠️  {len(files)} fichier(s) nominatif(s) de plus de {older_than_days} jours "
          f"({total_ko:.0f} Ko) dans {', '.join(dirs)}.")
    print("    Ce sont des sorties désanonymisées (vrais noms d'e-mails déjà envoyés) — "
          "recommandé de les effacer (hygiène vie privée).")
    if not assume_yes:
        try:
            ans = input("    On efface ? [O/n] ").strip().lower()
        except EOFError:
            ans = "n"
        if ans not in ("", "o", "oui", "y", "yes"):
            print("purge : rien supprimé.")
            return
    n = 0
    for f in files:
        f.unlink()
        n += 1
    print(f"purge : {n} fichier(s) effacé(s).")
