from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db.models import Q
from rest_framework.decorators import action
from .models import Broker, Property, MediaAsset, ClientRequest
from .serializers import BrokerRegisterSerializer, BrokerSerializer, PropertySerializer, ClientRequestSerializer, MediaAssetSerializer
from .models import Broker
from rest_framework.generics import CreateAPIView
from .services.extract import extract
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
import jwt, datetime
from django.conf import settings
from django.contrib.auth.hashers import check_password



# class RegisterView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request):
#         phone = request.data.get("phone")
#         name = request.data.get("name")
#         password = request.data.get("password")
#         email = request.data.get("email")

#         if not phone or not password:
#             return Response({"error": "phone and password are required"}, status=status.HTTP_400_BAD_REQUEST)

#         phone = str(phone).strip().replace(" ", "").replace("-", "")
#         broker, created = Broker.objects.get_or_create(phone_number=phone)
#         if broker.password and not created:
#             return Response(
#                 {"error": "Account already exists. Please login instead."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         broker.name = name or broker.name
#         broker.email = email or broker.email
        

#         broker.set_password(password)   
#         broker.save()
#         payload = {
#             "id": str(broker.id),
#             "exp": datetime.datetime.now() + datetime.timedelta(days=1),
#             "iat": datetime.datetime.now(),
#         }
#         token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

#         return Response(
#             {
#                 "message": "Registration successful",
#                 "token": token,
#                 "broker": {"id": broker.id, "name": broker.name, "phone": broker.phone_number},
#             },
#             status=status.HTTP_201_CREATED,
#         )

from rest_framework_simplejwt.tokens import RefreshToken

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone")
        name = request.data.get("name")
        password = request.data.get("password")
        email = request.data.get("email")

        if not phone or not password:
            return Response({"error": "phone and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        phone = str(phone).strip().replace(" ", "").replace("-", "")
        broker, created = Broker.objects.get_or_create(phone_number=phone)

        if broker.password and not created:
            return Response({"error": "Account already exists. Please login instead."}, status=status.HTTP_400_BAD_REQUEST)

        broker.name = name or broker.name
        broker.email = email or broker.email
        broker.set_password(password)
        broker.save()

        refresh = RefreshToken.for_user(broker)

        return Response({
            "message": "Registration successful",
            "token": str(refresh.access_token),
            "refresh": str(refresh),
            "broker": {"id": str(broker.id), "name": broker.name, "phone": broker.phone_number},
        }, status=status.HTTP_201_CREATED)



def ping(request):
    
    return Response({
        "status": "success",
    })
# class LoginView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request):
#         phone = request.data.get("phone")
#         password = request.data.get("password")

#         if not phone or not password:
#             return Response({"error": "Phone and password are required"}, status=status.HTTP_400_BAD_REQUEST)


#         try:
#             broker = Broker.objects.get(phone_number=phone)
#         except Broker.DoesNotExist:
#             return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)


#         if not broker.password:
#             return Response(
#                 {
#                     "error": "Password not set. Please create one before logging in.",
#                     "needs_setup": True,
#                     "broker_id": str(broker.id),
#                 },
#                 status=status.HTTP_403_FORBIDDEN,
#             )

#         if not broker.check_password(password):
#             return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

#         payload = {
#             "id": str(broker.id),
#             "exp": datetime.datetime.now() + datetime.timedelta(days=1),
#             "iat": datetime.datetime.now(),
#         }
#         token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

#         return Response({"token": token, "broker": {"id": broker.id, "name": broker.name, "phone": broker.phone_number}})

# class LoginView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request):
#         phone = request.data.get("phone")
#         password = request.data.get("password")

#         if not phone or not password:
#             return Response({"error": "Phone and password are required"}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             broker = Broker.objects.get(phone_number=phone)
#         except Broker.DoesNotExist:
#             return Response({"error": "No account found"}, status=status.HTTP_404_NOT_FOUND)

#         if not broker.password:
#             return Response({
#                 "error": "Password not set. Please create one.",
#                 "needs_setup": True,
#                 "broker_id": str(broker.id)
#             }, status=status.HTTP_403_FORBIDDEN)

#         if not broker.check_password(password):
#             return Response({"error": "Invalid password"}, status=status.HTTP_401_UNAUTHORIZED)

#         # ✅ Success - generate JWT
#         payload = {
#             "id": str(broker.id),
#             "exp": datetime.datetime.now() + datetime.timedelta(days=1),
#             "iat": datetime.datetime.now(),
#         }
#         token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

#         return Response({
#             "message": "Login successful",
#             "token": token,
#             "broker": {
#                 "id": str(broker.id),
#                 "name": broker.name,
#                 "phone": broker.phone_number,
#             },
#         }, status=status.HTTP_200_OK)

from rest_framework_simplejwt.tokens import RefreshToken

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone")
        password = request.data.get("password")

        if not phone or not password:
            return Response({"error": "Phone and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            broker = Broker.objects.get(phone_number=phone)
        except Broker.DoesNotExist:
            return Response({"error": "No account found"}, status=status.HTTP_404_NOT_FOUND)

        if not broker.password:
            return Response({
                "error": "Password not set. Please create one.",
                "needs_setup": True,
                "broker_id": str(broker.id)
            }, status=status.HTTP_403_FORBIDDEN)

        if not broker.check_password(password):
            return Response({"error": "Invalid password"}, status=status.HTTP_401_UNAUTHORIZED)

        # ✅ Generate SimpleJWT tokens
        refresh = RefreshToken.for_user(broker)

        return Response({
            "message": "Login successful",
            "token": str(refresh.access_token),
            "refresh": str(refresh),
            "broker": {
                "id": str(broker.id),
                "name": broker.name,
                "phone": broker.phone_number,
            },
        }, status=status.HTTP_200_OK)


class BrokerRegisterView(CreateAPIView):
    queryset = Broker.objects.all()
    serializer_class = BrokerRegisterSerializer

  
class BrokerMeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        broker = request.user
        serializer = BrokerSerializer(broker)
        return Response(serializer.data)

class BrokerViewSet(viewsets.ModelViewSet):
    queryset = Broker.objects.all()
    serializer_class = BrokerSerializer

    permission_classes = [IsAdminUser]

    @action(detail=False, methods=["get"], url_path="by-phone", permission_classes=[AllowAny])
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
    

class PropertyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Property.objects.all().select_related("broker").prefetch_related("media")
    serializer_class = PropertySerializer

    def get_queryset(self):
        broker_id = self.request.query_params.get("broker")
        if broker_id:
            return self.queryset.filter(broker_id= broker_id)
        return self.queryset
    
    
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

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        phone = request.data.get("phone")

        if not phone:
            return Response({"error": "Phone number required."}, status=400)

        try:
            broker = Broker.objects.get(phone_number=phone)
        except Broker.DoesNotExist:
            return Response({"error": "No account found with this phone number."}, status=404)

        from .views_twilio import set_session
        set_session(broker.id, {"mode": "reset_password", "step": "awaiting_password", "broker_id": str(broker.id)})

        msg = (
            f"Hi {broker.name or ''} 👋,\n\n"
            "We received a password reset request for your PropertyTrackrr account.\n"
            "👉 Please *reply with your new password* to reset it.\n\n"
            "If you didn’t request this, just ignore this message."
        )
        from .services.sender_meta import send_whatsapp_text
        send_whatsapp_text(phone, msg)

        return Response({"message": "Password reset instructions sent via WhatsApp."}, status=200)



