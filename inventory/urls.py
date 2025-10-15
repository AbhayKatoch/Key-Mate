from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ping,BrokerMeView, LoginView, RegisterView,BrokerViewSet,ForgotPasswordView, PropertyViewSet, MediaViewSet, ClientViewSet
from .views_ai import whatsaap_webhook, whatsapp_webhook_meta
from .views_customer import customer_webhook


router = DefaultRouter()
router.register(r'properties', PropertyViewSet, basename='property')
router.register(r'media', MediaViewSet, basename='mediaasset')
router.register(r'requests', ClientViewSet, basename='clientrequest')

urlpatterns = [
    path('', include(router.urls)),
    path("brokers/register/", RegisterView.as_view(), name="broker-register"),
    path("brokers/login/", LoginView.as_view(), name="broker-login"),
    path("brokers/me/", BrokerMeView.as_view(), name="broker-me"),
    path("brokers/forgot-password/", ForgotPasswordView.as_view(), name = "broker-forgot-password"),
    path("twilio/webhook", whatsaap_webhook, name="twilio-webhook" ),
    path("twilio/customer_webhook", customer_webhook, name="customer_webhook"),
    path("whatsapp_webhook_meta", whatsapp_webhook_meta, name="meta-webhook" ),
    path("ping/", ping,name="ping" )
]