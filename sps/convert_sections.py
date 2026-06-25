import re

_TENSION = {"🟢": "vert", "🟡": "jaune", "🟠": "orange", "🔴": "rouge"}

def section_type_for(emoji, legende):
    if emoji == "🏆":
        return "best_service"
    if emoji == "📚":
        return "formation"
    if emoji == "🎯":
        return "dispositif"
    if emoji == "⚠":
        return "aucune_action"
    if emoji == "✅":
        if legende.startswith("Structures IAE") or legende.startswith("Structures les-emplois"):
            return "structures_iae"
        return "eligibilite"
    return f"{emoji} {legende}".strip()

_ITEM_IAE = re.compile(
    r"•\s*(?:([🟢🟡🟠🔴])\s*)?(?:\[([^\]]+)\]\s*)?(.+?)\s*\|\s*(.+?)\s*"
    r"(?:\((\d+)\s*km\))?\s*(?:—\s*(.+))?$")

def _emoji_head(line):
    for e in ("🏆", "✅", "📚", "🎯", "⚠", "💡", "📋"):
        if line.startswith(e):
            return e, line[len(e):].strip()
    return None, None

def _parse_item(lines, i):
    m = _ITEM_IAE.search(lines[i].strip())
    item = {"tension": None, "type_struct": None, "nom": None, "structure": None,
            "adresse": None, "distance_km": None, "telephone": None,
            "email": None, "note": None, "url": None}
    if m:
        item["tension"] = _TENSION.get(m.group(1)) if m.group(1) else None
        item["type_struct"] = m.group(2)
        item["nom"] = (m.group(3) or "").strip()
        item["adresse"] = (m.group(4) or "").strip() or None
        item["distance_km"] = int(m.group(5)) if m.group(5) else None
        item["note"] = (m.group(6) or "").strip() or None
    else:
        item["nom"] = lines[i].strip().lstrip("•").strip()
    j = i + 1
    while j < len(lines):
        s = lines[j].strip()
        if s.startswith("→"):
            item["url"] = s[1:].strip()
        elif re.match(r"^(\+33|0)\d", s):
            item["telephone"] = s
        elif re.match(r"^[\w.+-]+@[\w.-]+$", s):
            item["email"] = s
        elif s == "" or s.startswith("•") or s.startswith("⚪") or _emoji_head(s)[0] \
                or s.startswith("▸") or s.startswith("Alternatives"):
            break
        else:  # accumulate multi-line notes instead of dropping continuation lines
            item["note"] = s if item["note"] is None else f'{item["note"]} {s}'
        j += 1
    return item, j

def _parse_best_item(lines, i):
    s = lines[i].strip()
    m = re.match(r"⚪\s*(.+?)\s*→\s*(.+)", s)
    contrainte = m.group(1).strip() if m else None
    service = m.group(2).strip() if m else s.lstrip("⚪").strip()
    item = {"tension": None, "type_struct": None, "nom": service, "structure": None,
            "adresse": None, "distance_km": None, "telephone": None, "email": None,
            "note": contrainte, "url": None}
    j = i + 1
    while j < len(lines):
        t = lines[j].strip()
        if t.startswith("→"):
            item["url"] = t[1:].strip()
        elif re.match(r"^(\+33|0)\d", t):
            item["telephone"] = t
        elif re.match(r"^[\w.+-]+@[\w.-]+$", t):
            item["email"] = t
        elif t == "" or t.startswith("⚪") or t.startswith("▸") or _emoji_head(t)[0]:
            break
        elif "|" in t and item["adresse"] is None:
            item["adresse"] = t
        j += 1
    return item, j

def parse_sections(body_lines):
    avis = None
    groupes = []
    cur_group = None
    cur_section = None
    i = 0
    n = len(body_lines)
    while i < n:
        raw = body_lines[i]
        line = raw.strip()
        if line.startswith("📋"):
            j = i + 1
            while j < n and not body_lines[j].strip():
                j += 1
            if j < n:
                avis = body_lines[j].strip()
            i = j + 1
            continue
        if line.startswith("▸"):
            cur_group = {"titre": line[1:].strip(), "before_block": None,
                         "after_block": None, "sections": []}
            groupes.append(cur_group)
            cur_section = None
            i += 1
            continue
        emoji, rest = _emoji_head(line)
        if emoji in ("🏆", "✅", "📚", "🎯", "⚠"):
            cur_section = {"type": section_type_for(emoji, rest), "legende": rest,
                           "items": [], "aside": None, "before_block": None,
                           "after_block": None, "alternatives": None}
            if cur_group is None:
                cur_group = {"titre": "", "before_block": None,
                             "after_block": None, "sections": []}
                groupes.append(cur_group)
            cur_group["sections"].append(cur_section)
            i += 1
            continue
        if emoji == "💡" and cur_section is not None:
            content = [rest]
            j = i + 1
            while j < n and body_lines[j].strip():
                content.append(body_lines[j].strip())
                j += 1
            cur_section["aside"] = {"format": "markdown",
                                    "content": " ".join(content).strip()}
            i = j
            continue
        if line.startswith("Alternatives") and cur_section is not None:
            cur_section["alternatives"] = []
            i += 1
            continue
        if line.startswith("•") and cur_section is not None:
            item, i = _parse_item(body_lines, i)
            (cur_section["alternatives"] if cur_section["alternatives"] is not None
             else cur_section["items"]).append(item)
            continue
        if line.startswith("⚪") and cur_section is not None:
            item, i = _parse_best_item(body_lines, i)
            cur_section["items"].append(item)
            continue
        i += 1
    return avis, groupes
