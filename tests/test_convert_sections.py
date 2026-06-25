from sps.convert_sections import parse_sections, section_type_for

BODY = """
📋 Donnez votre avis sur les solutions en 1 minute !
   https://tally.so/r/J9MBBd?email=jane%40x

▸ SERVICES D'INSERTION PONCTUELS

🏆 Meilleur service par contrainte (< 10 km)
   ⚪ Mobilité → Aide prothèses auditives
     Agefiph Hauts-de-France | 27BIS Rue, Lille (1 km)
     +33800111009
     → https://www.agefiph.fr/aide?mtm_campaign=xp-sps

▸ ACCOMPAGNEMENT LONG ET SPÉCIFIQUE

✅ Structures IAE — ROME K2205 (Agent) [critère(s) N1: RSA]
   • 🔴 [AI] Assoc Test Emploi | 59800 (1 km)
     1175 candidatures sur ce métier (30 derniers jours)
     → https://emplois.inclusion.beta.gouv.fr/company/4721/card?mtm_campaign=xp-sps

   💡 Le saviez-vous ? Les SIAE ne forment pas
   à un métier précis :
   — elles lèvent les freins.

   Alternatives les moins sollicitées à proximité (< 10 km) :
   • 🟡 [EI] Metal Insertion | 59110 (3 km) — Métallier
     1 candidature sur H2911 (30 jours)
     → https://emplois.inclusion.beta.gouv.fr/company/4929/card?mtm_campaign=xp-sps
""".splitlines()

def test_type_mapping():
    assert section_type_for("✅", "Structures IAE — ROME K2205") == "structures_iae"
    assert section_type_for("✅", "PLIE — Éligible (DELD)") == "eligibilite"
    assert section_type_for("✅", "EPIDE — Éligible") == "eligibilite"
    assert section_type_for("🏆", "Meilleur service") == "best_service"
    assert section_type_for("📚", "Accès à la formation") == "formation"
    assert section_type_for("🎯", "SEVE") == "dispositif"
    assert section_type_for("⚠", "Aucune action") == "aucune_action"
    assert section_type_for("❓", "Nouveau truc") == "❓ Nouveau truc"  # unknown -> raw

def test_parse_sections():
    avis, groupes = parse_sections(BODY)
    assert avis.startswith("https://tally.so/")
    assert [g["titre"] for g in groupes] == [
        "SERVICES D'INSERTION PONCTUELS", "ACCOMPAGNEMENT LONG ET SPÉCIFIQUE"]

    best = groupes[0]["sections"][0]
    assert best["type"] == "best_service"
    assert best["items"][0]["nom"].startswith("Aide prothèses auditives") or \
           best["items"][0]["note"] == "Mobilité"  # contrainte captured

    iae = groupes[1]["sections"][0]
    assert iae["type"] == "structures_iae"
    it = iae["items"][0]
    assert it["tension"] == "rouge"
    assert it["type_struct"] == "AI"
    assert it["nom"] == "Assoc Test Emploi"
    assert it["adresse"] == "59800"
    assert it["distance_km"] == 1
    assert it["url"].startswith("https://emplois.inclusion")
    assert iae["aside"]["format"] == "markdown"
    assert "saviez-vous" in iae["aside"]["content"].lower()
    assert iae["alternatives"][0]["type_struct"] == "EI"
