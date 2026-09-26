"""Correction automatique d'un quiz à partir des données POST."""

def _bonne_reponse_qcm(question, post):
    field = f"q{question.id}"
    selected = set(post.getlist(field))
    corrects = set(str(c.id) for c in question.choix.all() if c.correct)
    return bool(corrects) and selected == corrects

def _bonne_reponse_court(question, post):
    ans = (post.get(f"q{question.id}") or "").strip().lower()
    accepted = [a.strip().lower() for a in (question.reponse_courte or "").split("|") if a.strip()]
    return ans != "" and ans in accepted

def _bonne_reponse_num(question, post):
    raw = (post.get(f"q{question.id}") or "").strip().replace(",", ".")
    try:
        val = float(raw)
    except ValueError:
        return False
    spec = (question.reponse_courte or "").split(":")
    try:
        cible = float(spec[0]); tol = float(spec[1]) if len(spec) > 1 else 0.0
    except (ValueError, IndexError):
        return False
    return abs(val - cible) <= tol

def _bonne_reponse_appariement(question, post):
    ok = True
    for c in question.choix.all():
        droite = c.texte.split("->", 1)[1].strip() if "->" in c.texte else ""
        choisi = (post.get(f"q{question.id}_{c.id}") or "").strip()
        if choisi != droite:
            ok = False
    return ok

def corriger(quiz, post):
    """Retourne (score_sur_20, nb_bonnes, total, details[list de (question, ok)])."""
    details = []
    bonnes = 0
    questions = list(quiz.questions.all().prefetch_related("choix"))
    for q in questions:
        if q.type == "qcm":
            ok = _bonne_reponse_qcm(q, post)
        elif q.type == "vf":
            ok = _bonne_reponse_qcm(q, post)  # VF = un seul choix correct
        elif q.type == "court":
            ok = _bonne_reponse_court(q, post)
        elif q.type == "num":
            ok = _bonne_reponse_num(q, post)
        elif q.type == "appariement":
            ok = _bonne_reponse_appariement(q, post)
        else:
            ok = False
        bonnes += 1 if ok else 0
        details.append((q, ok))
    total = len(questions)
    score = round(20 * bonnes / total, 2) if total else 0
    return score, bonnes, total, details
