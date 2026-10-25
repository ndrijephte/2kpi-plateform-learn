"""Texte mis en forme (gras, italique, souligné, listes, liens) saisi dans l'éditeur des consignes et
des notifications. Le HTML est filtré par liste blanche à l'enregistrement et à l'affichage : seules
les balises de TAGS passent, sans attribut (sauf href http(s)/mailto sur les liens).
Les textes anciens, en texte brut, restent affichés avec leurs retours à la ligne."""
import re
from html import escape
from html.parser import HTMLParser
from django import forms
from django.utils.html import linebreaks
from django.utils.safestring import mark_safe

TAGS = {"p", "div", "br", "b", "strong", "i", "em", "u", "s", "ul", "ol", "li", "a"}
VIDES = {"br"}
BLOCS = {"p", "div", "li", "ul", "ol"}
_HTML = re.compile(r"<\s*/?\s*(%s)\b[^>]*>" % "|".join(sorted(TAGS)), re.I)
_LIEN_OK = re.compile(r"^(https?://|mailto:)", re.I)


def est_riche(texte):
    return bool(texte) and bool(_HTML.search(texte))


class _Filtre(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sortie, self.ouvertes, self.ignore = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignore += 1
            return
        if tag not in TAGS:
            return
        if tag in BLOCS - {"li"} and "p" in self.ouvertes:  # pas de bloc dans un paragraphe
            self.handle_endtag("p")
        if tag == "a":
            href = (dict(attrs).get("href") or "").strip()
            if not _LIEN_OK.match(href):
                return
            self.sortie.append(f'<a href="{escape(href)}" target="_blank" rel="noopener noreferrer">')
        else:
            self.sortie.append(f"<{tag}>")
        if tag not in VIDES:
            self.ouvertes.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in TAGS and tag not in VIDES:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.ignore = max(0, self.ignore - 1)
            return
        if tag in self.ouvertes:  # referme proprement, même si l'imbrication reçue était bancale
            while self.ouvertes:
                t = self.ouvertes.pop()
                self.sortie.append(f"</{t}>")
                if t == tag:
                    break

    def handle_data(self, data):
        if not self.ignore:
            self.sortie.append(escape(data, quote=False))

    def resultat(self):
        self.close()
        return "".join(self.sortie) + "".join(f"</{t}>" for t in reversed(self.ouvertes))


def nettoyer(html):
    """HTML réduit à la liste blanche ; chaîne vide si rien de lisible n'a été saisi."""
    if not html or not en_texte(html):
        return ""
    if not est_riche(html):  # saisie sans éditeur (JavaScript désactivé) : texte brut conservé
        return html.strip()
    f = _Filtre()
    f.feed(html)
    return re.sub(r"<(p|div)>(\s|<br>)*</\1>", "", f.resultat()).strip()


def rendre(texte):
    """HTML sûr pour l'affichage : texte riche filtré, ou texte brut avec ses retours à la ligne."""
    if not texte:
        return ""
    if est_riche(texte):
        return mark_safe(nettoyer(texte))
    return mark_safe(linebreaks(texte, autoescape=True))  # texte échappé par linebreaks : sûr


class _Texte(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.morceaux, self.listes = [], []

    def _ligne(self):
        if self.morceaux and not self.morceaux[-1].endswith("\n"):
            self.morceaux.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag in ("ul", "ol"):
            self._ligne()
            self.listes.append([tag, 0])
        elif tag == "li":
            self._ligne()
            if self.listes and self.listes[-1][0] == "ol":
                self.listes[-1][1] += 1
                puce = f"{self.listes[-1][1]}. "
            else:
                puce = "- "
            self.morceaux.append("  " * max(len(self.listes) - 1, 0) + puce)
        elif tag == "br":
            self.morceaux.append("\n")
        elif tag in BLOCS:
            self._ligne()

    def handle_endtag(self, tag):
        if tag in ("ul", "ol") and self.listes:
            self.listes.pop()
        if tag in BLOCS:
            self._ligne()

    def handle_data(self, data):
        self.morceaux.append(data)


def en_texte(texte):
    """Version texte brut (e-mails, aperçus tronqués)."""
    if not texte:
        return ""
    if not est_riche(texte):
        return texte.strip()
    p = _Texte()
    p.feed(texte)
    p.close()
    lignes = [l.rstrip() for l in "".join(p.morceaux).replace("\xa0", " ").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lignes)).strip()


# ---------- Formulaires ----------

class EditeurRiche(forms.Textarea):
    """Zone de texte enrichie par static/js/editeur.js (barre d'outils + zone éditable).
    Sans JavaScript, le textarea reste utilisable en texte brut."""
    def __init__(self, attrs=None):
        super().__init__({"rows": 6, "data-editeur": "", **(attrs or {})})


class ChampRiche(forms.CharField):
    widget = EditeurRiche

    def to_python(self, value):
        return nettoyer(super().to_python(value))
