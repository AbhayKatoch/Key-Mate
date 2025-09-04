from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BrokerViewSet, PropertyViewSet, MediaViewSet, ClientViewSet
from .views_twilio import whatsaap_webhook


router = DefaultRouter()
router.register(r'brokers', BrokerViewSet, basename='broker')
router.register(r'properties', PropertyViewSet, basename='property')
router.register(r'media', MediaViewSet, basename='mediaasset')
router.register(r'requests', ClientViewSet, basename='clientrequest')

urlpatterns = [
    path('', include(router.urls)),
    path("twilio/webhook", whatsaap_webhook, name="twilio-webhook" )
]