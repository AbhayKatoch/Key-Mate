from django.db import models
import uuid

class Broker(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20, unique = True)
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    broker_code = models.CharField(max_length=50, blank=True, unique=True)
    

    def save(self, *args, **kwargs):
        # Ensure id exists
        if not self.id:
            self.id = uuid.uuid4()
        if not self.broker_code:
            self.broker_code = f"KD-BROKER-{self.id}"
        super().save(*args, **kwargs)


    @property
    def whatsapp_link(self):
        bot_number = "+14155238886"
        return f"https://wa.me/{bot_number}?text=KD-BROKER-{self.id}"

    def __str__(self):
        return f"{self.name or self.phone_number}"

class Property(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("disabled", "Disabled"),
        ("archived", "Archived"),
    ]

    SOURCE_CHOICES = [
        ("direct", "Direct"),
        ("broker", "Through Broker"),
    ]

    FURNISHING_CHOICES = [
        ("unfurnished", "Unfurnished"),
        ("semi", "Semi-Furnished"),
        ("fully", "Fully Furnished"),
    ]

    SALE_RENT_CHOICES = [
        ("sale", "For Sale"),
        ("rent", "For Rent"),
    ]

    id = models.UUIDField(primary_key=True, default = uuid.uuid4, editable=False)
    broker = models.ForeignKey(Broker, on_delete=models.CASCADE, related_name="properties")

    short_code = models.CharField(max_length=50, unique=True, editable=False, null=True)
    title = models.CharField(max_length=200, blank = True, null = True)
    description_raw = models.TextField()
    description_beautified = models.TextField(blank=True, null=True)

    city = models.CharField(max_length=100, null=True)
    locality = models.CharField(max_length=150, blank = True, null=True)

    bhk = models.IntegerField(blank=True, null=True)
    bathrooms = models.IntegerField(blank=True, null=True)
    area_sqft = models.FloatField(blank=True, null=True)
    floor = models.IntegerField(blank=True, null=True)
    total_floors = models.IntegerField(blank=True, null=True)
    furnishing = models.CharField(max_length=20, choices=FURNISHING_CHOICES, blank=True, null=True)
    age_of_property = models.IntegerField(blank=True, null=True)
    amenities = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    sale_or_rent = models.CharField(max_length=10, choices=SALE_RENT_CHOICES, default="rent")
    price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=10, default="INR")
    maintenance = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    deposit = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)

    source = models.CharField(max_length=50, choices=SOURCE_CHOICES, default="direct", blank=True, null=True)
    source_broker_name = models.CharField(max_length=100, blank=True, null=True)
    source_broker_phone = models.CharField(max_length=15, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    moderation_flags = models.JSONField(blank=True, null=True)
    embedding = models.BinaryField(blank=True, null=True)  # pgvector later
    property_id = models.CharField(max_length=10, null=True, editable=False, blank=True)

    def save(self, *args, **kwargs):
        if not self.property_id:
            count = Property.objects.filter(broker= self.broker).count() + 1
            self.property_id = f"{count}"

        if not self.short_code:
            city_code = (self.city[:3] if self.city else "XXX").upper()
            bhk_code = f"{self.bhk}BHK" if self.bhk else "NA"
            count = Property.objects.count() + 1
            self.short_code = f"KD-{city_code}-{bhk_code}-{count:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title or 'Property'} - {self.city or ''}"

class MediaAsset(models.Model):
    MEDIA_TYPES = [
        ("image", "Image"),
        ("video", "Video"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(max_length=10, choices = MEDIA_TYPES)
    storage_url = models.URLField() #S3
    caption = models.CharField(max_length=200, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.media_type} for {self.property.id}"
    

class ClientRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=True)
    broker = models.ForeignKey(Broker, on_delete=models.CASCADE, related_name="Client")
    query = models.TextField()
    ai_structure = models.JSONField(blank = True, null = True)
    response = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Request by {self.broker} at {self.created_at}"
    


class Session(models.Model):
    broker = models.ForeignKey(Broker, on_delete=models.CASCADE)
    client_phone = models.CharField(max_length=20, unique=True)
    last_message_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.client_phone}->{self.broker.name}"