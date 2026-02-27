from decimal import Decimal

from rest_framework import serializers

from orders.pincode_service import ensure_serviceable_pincode
from users.phone_utils import PhoneNormalizationError, normalize_phone

from .models import Cart, CartItem


class AddToCartSerializer(serializers.Serializer):
    phone = serializers.CharField()
    customer_name = serializers.CharField(required=False, allow_blank=True)
    whatsapp_no = serializers.CharField(required=False, allow_blank=True)
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except PhoneNormalizationError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id")
    product_name = serializers.CharField(source="product.name")
    price = serializers.DecimalField(source="product.price", max_digits=10, decimal_places=2)
    image = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["product_id", "product_name", "price", "quantity", "image", "line_total"]

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.product.image and request:
            return request.build_absolute_uri(obj.product.image.url)
        return None

    def get_line_total(self, obj):
        return str(obj.product.price * obj.quantity)


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "customer", "items", "total_items", "total_amount"]

    def get_total_items(self, obj):
        if hasattr(obj, "total_items") and obj.total_items is not None:
            return int(obj.total_items)
        return sum(item.quantity for item in obj.items.all())

    def get_total_amount(self, obj):
        if hasattr(obj, "total_amount") and obj.total_amount is not None:
            return str(obj.total_amount)

        total = 0
        for item in obj.items.select_related("product"):
            total += item.product.price * item.quantity
        return str(Decimal(total))


class PlaceOrderSerializer(serializers.Serializer):
    phone = serializers.CharField()
    customer_name = serializers.CharField()
    whatsapp_no = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField()
    pincode = serializers.CharField()
    cart_phone = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.UUIDField()

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except PhoneNormalizationError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_cart_phone(self, value):
        if not value:
            return ""
        try:
            return normalize_phone(value)
        except PhoneNormalizationError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_whatsapp_no(self, value):
        if not value:
            return ""
        try:
            return normalize_phone(value)
        except PhoneNormalizationError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate(self, attrs):
        pincode = attrs.get("pincode", "")
        address = attrs.get("address", "")
        try:
            attrs["pincode"] = ensure_serviceable_pincode(pincode=pincode, address=address)
        except ValueError as exc:
            raise serializers.ValidationError({"pincode": str(exc)})

        if not attrs.get("whatsapp_no"):
            attrs["whatsapp_no"] = attrs["phone"]
        return attrs


class UpdateCartItemSerializer(serializers.Serializer):
    phone = serializers.CharField()
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=0)

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except PhoneNormalizationError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class RemoveCartItemSerializer(serializers.Serializer):
    phone = serializers.CharField()
    product_id = serializers.IntegerField()

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except PhoneNormalizationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
