from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        n = Notification.objects.filter(destinataire=request.user, lu=False).count()
        return {"notifs_non_lues": n}
    return {"notifs_non_lues": 0}
