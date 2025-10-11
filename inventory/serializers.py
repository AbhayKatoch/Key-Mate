from rest_framework import serializers
from .models import Broker, Property, MediaAsset, ClientRequest

class BrokerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Broker
        fields = '__all__'

class BrokerRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Broker
        fields = ['id', 'name', 'phone', 'password']

    def create(self, validated_data):
        phone = validated_data.get("phone")
        broker, created = Broker.objects.get_or_create(
            phone = phone,
            defaults={
                "name": validated_data.get("name"),
                "email": validated_data.get("email"),
            }

        )
        broker.password = validated_data.get("password")
        broker.save()
        return broker

class MediaAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaAsset
        fields = '__all__'

class PropertySerializer(serializers.ModelSerializer):
    media = MediaAssetSerializer(many = True, read_only = True)

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
            "embedding",   # keep for AI layer / pgvector
            "created_at",
            "updated_at",
            "media"
        ]
        read_only_fields = ["short_code", "created_at", "updated_at"]


class ClientRequestSerializer(serializers.ModelSerializer):
    broker = BrokerSerializer(read_only=True)

    class Meta:
        model = ClientRequest
        fields = '__all__'
