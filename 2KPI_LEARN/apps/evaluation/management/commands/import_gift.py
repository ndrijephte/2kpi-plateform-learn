"""Importe la banque de questions GIFT (Test S1) dans un Quiz rattaché au module M1.
Gère le sous-ensemble GIFT utilisé : QCM (simple/multiple), Vrai/Faux, réponse
courte, numérique, appariement. Idempotent (recrée le quiz)."""
import re
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.formation.models import Module
from apps.evaluation.models import Quiz, Question, Choix

DATA = Path(__file__).resolve().parents[2] / "data" / "Test_S1_banque_questions.gift"


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


class Command(BaseCommand):
    help = "Importe le Test S1 (GIFT) dans un quiz du module M1."

    @transaction.atomic
    def handle(self, *args, **options):
        module = Module.objects.filter(code="M1").first()
        if not module:
            self.stderr.write("Module M1 introuvable — lance d'abord `seed_geoai`.")
            return
        if not DATA.exists():
            self.stderr.write(f"Fichier GIFT introuvable : {DATA}")
            return

        quiz, _ = Quiz.objects.get_or_create(module=module, titre="Test — Semaine 1")
        quiz.questions.all().delete()

        raw = DATA.read_text(encoding="utf-8")
        blocks = re.split(r"\n\s*\n", raw)
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
            q = Question.objects.create(
                quiz=quiz, intitule=intitule, type=qtype, categorie=categorie,
            )
            if qtype == "vf":
                Choix.objects.create(question=q, texte="Vrai", correct=data["vrai"],
                                     poids=100 if data["vrai"] else 0)
                Choix.objects.create(question=q, texte="Faux", correct=not data["vrai"],
                                     poids=0 if data["vrai"] else 100)
            elif qtype == "num":
                q.reponse_courte = data["reponse"]; q.save()
            elif qtype == "court":
                q.reponse_courte = " | ".join(data["reponses"]); q.save()
            elif qtype == "appariement":
                for g, d in data["pairs"]:
                    Choix.objects.create(question=q, texte=f"{g} -> {d}", correct=True, poids=0)
            else:  # qcm
                for c in data["choix"]:
                    Choix.objects.create(question=q, texte=c["texte"],
                                         correct=c["correct"], poids=c["poids"])
            n += 1

        self.stdout.write(self.style.SUCCESS(f"OK — {n} questions importées dans « {quiz.titre} »."))
