def est_formateur(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    profil = getattr(user, "profil", None)
    return bool(profil and profil.est_formateur)
