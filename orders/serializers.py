from rest_framework import serializers
from .models import Order, OrderItem, OrderFeedback, Bill, BillItem
from products.models import Product
from .pincode_service import ensure_serviceable_pincode


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = OrderItem
        fields = ['product_id', 'quantity', 'price']
        read_only_fields = ['price']

    def validate(self, data):
        try:
            product = Product.objects.get(id=data['product_id'])
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found")

        if product.stock_qty < data['quantity']:
            raise serializers.ValidationError(f"{product.name} out of stock")

        return data


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    customer_name = serializers.CharField(write_only=True)
    phone = serializers.CharField(write_only=True)
    whatsapp_no = serializers.CharField(write_only=True)
    address = serializers.CharField(write_only=True)
    pincode = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'customer_name',
            'phone',
            'whatsapp_no',
            'address',
            'pincode',
            'items',
            'total_price',
            'status',
            'created_at'
        ]
        read_only_fields = ['total_price', 'status', 'created_at']


    def validate(self, attrs):
        pincode = attrs.get("pincode", "")
        address = attrs.get("address", "")
        try:
            attrs["pincode"] = ensure_serviceable_pincode(pincode=pincode, address=address)
        except ValueError as exc:
            raise serializers.ValidationError({"pincode": str(exc)})
        return attrs


class OrderFeedbackWriteSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    phone = serializers.CharField(max_length=20)
    message = serializers.CharField(max_length=2000)
    rating = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5)

    def validate_message(self, value):
        text = str(value or "").strip()
        if len(text) < 3:
            raise serializers.ValidationError("Please enter at least 3 characters.")
        return text

    def validate_phone(self, value):
        return (value or "").strip()


class OrderFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderFeedback
        fields = [
            'id',
            'order',
            'phone',
            'rating',
            'message',
            'created_at',
            'updated_at',
        ]


class BillItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillItem
        fields = ['product_name', 'quantity', 'unit_price']


class BillSerializer(serializers.ModelSerializer):
    items = BillItemSerializer(many=True, read_only=True)

    class Meta:
        model = Bill
        fields = [
            'id',
            'order',
            'recipient_type',
            'bill_number',
            'customer_name',
            'phone',
            'shipping_address',
            'total_amount',
            'items',
            'created_at',
        ]
