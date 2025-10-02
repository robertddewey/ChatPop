from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView, CurrentUserView,
    UserSubscriptionListCreateView, UserSubscriptionDestroyView,
    MySubscribersView, CheckUsernameView
)

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('check-username/', CheckUsernameView.as_view(), name='check-username'),

    # Subscriptions
    path('subscriptions/', UserSubscriptionListCreateView.as_view(), name='subscription-list'),
    path('subscriptions/<uuid:pk>/', UserSubscriptionDestroyView.as_view(), name='subscription-delete'),
    path('subscribers/', MySubscribersView.as_view(), name='my-subscribers'),
]
