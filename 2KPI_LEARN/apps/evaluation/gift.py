"""Lecture du format GIFT (Moodle) : QCM simple/multiple, Vrai/Faux, réponse courte,
numérique, appariement. Utilisé par la commande `import_gift` et par Paramètres > Quiz."""
import re
from django.db import transaction
from .models import Choix, Question


def unescape(s):
    return s.replace(r"\=", "=").replace(r"\~", "~").replace(r"\#", "#").replace(r"\:", ":").strip()


def split_options(ans):
    """Découpe la zone de réponse en options délimitées par = ou ~ non échappés."""
    parts = re.split(r"(?<!\\)(?=[=~])", ans)
    return [p for p in (x.strip() for x in parts) if p]


def parse_block(block):
    """Retourne (titre, intitule, type, data) ou None."""
    # retirer les commentaires
    lines = [l for l in block.splitlines() if not l.lstrip().startswith("//")]
    text = "\n".join(lines).strip()
    if "{" not in text or "}" not in text:
        return None
    titre = ""
    mt = re.match(r"^::(.+?)::\s*", text, re.S)
    if mt:
        titre = mt.group(1).strip()
        text = text[mt.end():]
    intitule = text[:text.index("{")].strip()
    ans = text[text.index("{") + 1:text.rindex("}")].strip()

    # Vrai / Faux
    mvf = re.match(r"^(TRUE|FALSE|T|F)\b", ans)
    if mvf:
        vrai = mvf.group(1) in ("TRUE", "T")
        return (titre, intitule, "vf", {"vrai": vrai})

    # Numérique
    if ans.startswith("#"):
        val = ans[1:].split("#", 1)[0].strip()
        return (titre, intitule, "num", {"reponse": val})

    options = split_options(ans)
    # Appariement
    if any("->" in o for o in options):
        pairs = []
        for o in options:
            o = o.lstrip("=").split("#", 1)[0]
            if "->" in o:
                g, d = o.split("->", 1)
                pairs.append((unescape(g), unescape(d)))
        return (titre, intitule, "appariement", {"pairs": pairs})

    # Réponse courte (uniquement des =)
    if options and all(o.startswith("=") for o in options):
        rep = [unescape(o[1:].split("#", 1)[0]) for o in options]
        return (titre, intitule, "court", {"reponses": rep})

    # QCM (simple ou multiple)
    choix = []
    for o in options:
        correct = o.startswith("=")
        body = o[1:]
        poids = 100 if correct else 0
        mp = re.match(r"^%(-?\d+)%", body)
        if mp:
            poids = int(mp.group(1))
            correct = poids > 0
            body = body[mp.end():]
        body = unescape(body.split("#", 1)[0])
        choix.append({"texte": body, "correct": correct, "poids": poids})
    return (titre, intitule, "qcm", {"choix": choix})


@transaction.atomic
def importer_gift(quiz, texte, remplacer=False):
    """Ajoute au quiz les questions du texte GIFT (en remplaçant l'existant si demandé).
    Retourne le nombre de questions importées."""
    if remplacer:
        quiz.questions.all().delete()
    blocks = re.split(r"\n\s*\n", texte.replace("\r\n", "\n"))
    categorie = ""
    n = 0
    for b in blocks:
        mc = re.search(r"\$CATEGORY:\s*(.+)", b)
        if mc:
            categorie = mc.group(1).strip().split("/")[-1]
        parsed = parse_block(b)
        if not parsed:
            continue
        titre, intitule, qtype, data = parsed
        q = Question.objects.create(quiz=quiz, intitule=intitule, type=qtype, categorie=categorie)
        if qtype == "vf":
            Choix.objects.create(question=q, texte="Vrai", correct=data["vrai"],
                                 poids=100 if data["vrai"] else 0)
            Choix.objects.create(question=q, texte="Faux", correct=not data["vrai"],
                                 poids=0 if data["vrai"] else 100)
        elif qtype == "num":
            q.reponse_courte = data["reponse"]
            q.save(update_fields=["reponse_courte"])
        elif qtype == "court":
            q.reponse_courte = " | ".join(data["reponses"])
            q.save(update_fields=["reponse_courte"])
        elif qtype == "appariement":
            for g, d in data["pairs"]:
                Choix.objects.create(question=q, texte=f"{g} -> {d}", correct=True, poids=0)
        else:  # qcm
            for c in data["choix"]:
                Choix.objects.create(question=q, texte=c["texte"], correct=c["correct"], poids=c["poids"])
        n += 1
    return n
