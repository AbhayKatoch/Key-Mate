from django.contrib import admin
from .models import Property, Broker, ClientRequest

admin.site.register(Property)
admin.site.register(Broker)
admin.site.register(ClientRequest)
