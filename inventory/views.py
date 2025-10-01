from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db.models import Q
from rest_framework.decorators import action
from .models import Broker, Property, MediaAsset, ClientRequest
from .serializers import BrokerSerializer, PropertySerializer, ClientRequestSerializer, MediaAssetSerializer
from .models import Broker
from .services.extract import extract

class BrokerViewSet(viewsets.ModelViewSet):
    queryset = Broker.objects.all()
    serializer_class = BrokerSerializer

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.all().select_related("broker").prefetch_related("media")
    serializer_class = PropertySerializer

    def get_queryset(self):
        broker_id = self.request.query_params.get("broker")
        if broker_id:
            return self.queryset.filter(broker_id= broker_id)
        return self.queryset
    
    @action(detail=False, methods=["get"], url_path="by-phone")
    def by_phone(self, request):
        phone = request.query_params.get("phone")
        if not phone:
            return Response({"detail": "phone is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Normalize minimal formatting (optional but helpful)
        phone_norm = phone.strip().replace(" ", "").replace("-", "")

        broker = Broker.objects.filter(
            Q(phone_number=phone_norm) | Q(phone_number__endswith=phone_norm)
        ).first()

        if not broker:
            return Response({"detail": "Broker not found"}, status=status.HTTP_404_NOT_FOUND)

        # return a compact payload like your earlier view
        return Response({"id": broker.id, "name": broker.name, "phone_number": broker.phone_number})
    
    @action(detail=False, methods=["post"])
    def extract_info(self,request):
        broker_id = request.data.get("broker_id")
        description = request.data.get("description")
        media_urls = request.data.get("media_urls", [])

        if not broker_id or not description:
            return Response({"error": "no broker or description"})
        
        try:
            broker = Broker.objects.get(id = broker_id)
        except Broker.DoesNotExist:
            return Response({"error": "Broker not found"}, status=status.HTTP_404_NOT_FOUND)
        
        prop = extract(broker, description, media_urls)

        return Response(
            {
                "message": "Property extracted successfully. Please Confirm (yes/No).",
                "property": PropertySerializer(prop).data,
            }, status=status.HTTP_201_CREATED
        )


    

    @action(detail=False, methods=["get"])
    def search(self, request):
        qs = self.get_queryset()

        city = request.query_params.get("city")
        bhk = request.query_params.get("bhk")
        sale_or_rent = request.query_params.get("sale_or_rent")
        price = request.query_params.get("price")

        if city:
            qs = qs.filter(city__icontains = city)
        if bhk:
            qs = qs.filter(bhk = bhk)
        if sale_or_rent:
            qs = qs.filter(sale_or_rent = sale_or_rent)
        if price:
            qs = qs.filter(price__lte = price)

        query_text = request.query_params.get("query_text")

        if query_text:
            qs = qs.filter(
                Q(title__icontains = query_text) |
                Q(description_beautified__icontains  = query_text) |
                Q(locality__icontains  = query_text) 
            )
        
        serializer = self.get_serializer(qs, many = True)
        return Response(serializer.data)

    
    @action(detail = True, methods=["post"])
    def enable(self, request, pk=None):
        property = self.get_object()
        property.status = "active"
        property.save()
        return Response({"status":"enabled", "property": PropertySerializer(property).data()})
    
    @action(detail = True, methods=["post"])
    def disable(self, request, pk=None):
        property = self.get_object()
        property.status = "disabled"
        property.save()
        return Response({"status":"disabled", "property": PropertySerializer(property).data()})


class MediaViewSet(viewsets.ModelViewSet):
    queryset = MediaAsset.objects.all()
    serializer_class = MediaAssetSerializer

    def get_queryset(self):
        property_id = self.request.query_params.get("property_id")
        if property_id:
            return self.queryset.filter(property_id=property_id)
        return self.queryset

class ClientViewSet(viewsets.ModelViewSet):
    queryset = ClientRequest.objects.all()
    serializer_class = ClientRequestSerializer

    def get_queryset(self):
        broker_id = self.request.query_params.get("broker_id")
        if broker_id:
            return self.queryset.filter(broker_id=broker_id)
        return self.queryset

