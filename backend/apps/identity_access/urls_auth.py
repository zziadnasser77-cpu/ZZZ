from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.LoginView.as_view()),
    path("refresh/", views.RefreshView.as_view()),
    path("logout/", views.LogoutView.as_view()),
    path("me/", views.MeView.as_view()),
    path("password/", views.PasswordChangeView.as_view()),
    path("mfa/setup/", views.MfaSetupView.as_view()),
    path("mfa/confirm/", views.MfaConfirmView.as_view()),
    path("mfa/disable/", views.MfaDisableView.as_view()),
]
