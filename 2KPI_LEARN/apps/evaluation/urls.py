from django.urls import path
from . import views

app_name = "evaluation"
urlpatterns = [
    path("quiz/<int:quiz_id>/", views.quiz, name="quiz"),
]
