from rest_framework import serializers
from .models import Broker, Property, MediaAsset, ClientRequest


class BrokerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Broker
        fields = "__all__"


class BrokerRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Broker
        fields = ["id", "name", "phone_number", "email", "password"]

    def create(self, validated_data):
        phone_number = validated_data.get("phone_number")
        name = validated_data.get("name", "")
        email = validated_data.get("email", "")
        password = validated_data.get("password")

        broker, created = Broker.objects.get_or_create(
            phone_number=phone_number,
            defaults={"name": name, "email": email},
        )

        # Update fields if broker already exists (e.g. from WhatsApp onboarding)
        broker.name = name or broker.name
        broker.email = email or broker.email

        # Always hash the password
        broker.set_password(password)
        broker.save()
        return broker


class MediaAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaAsset
        fields = "__all__"


class PropertySerializer(serializers.ModelSerializer):
    media = MediaAssetSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = [
            "id",
            "broker",
            "short_code",
            "title",
            "description_raw",
            "description_beautified",
            "city",
            "locality",
            "bhk",
            "bathrooms",
            "area_sqft",
            "floor",
            "total_floors",
            "furnishing",
            "age_of_property",
            "amenities",
            "sale_or_rent",
            "price",
            "currency",
            "maintenance",
            "deposit",
            "source",
            "source_broker_name",
            "source_broker_phone",
            "status",
            "moderation_flags",
            "embedding",
            "created_at",
            "updated_at",
            "media",
        ]
        read_only_fields = ["short_code", "created_at", "updated_at"]


class ClientRequestSerializer(serializers.ModelSerializer):
    broker = BrokerSerializer(read_only=True)

    class Meta:
        model = ClientRequest
        fields = "__all__"
