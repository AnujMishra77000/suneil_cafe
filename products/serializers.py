from rest_framework import serializers
from .models import Section, Category, Product,ProductViewLog

class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ['id', 'name']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'section']
        
class ProductSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    category_id = serializers.IntegerField(source='category.id', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    section_name = serializers.CharField(source='category.section.name', read_only=True)
    related_product_ids = serializers.PrimaryKeyRelatedField(
        source="related_products",
        many=True,
        read_only=True,
    )

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'category_id',
            'category_name',
            'section_name',
            'price',
            'stock_qty',
            'is_available',
            'message',
            'description',
            'image',
            'created_at',
            'related_product_ids',
        ]

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_message(self, obj):
        if not obj.is_available:
            return "Currently unavailable. Please call the owner to confirm."
        return None



class ProductCardSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    category_id = serializers.IntegerField(source='category.id', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    section_name = serializers.CharField(source='category.section.name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'category_id',
            'category_name',
            'section_name',
            'price',
            'stock_qty',
            'is_available',
            'message',
            'description',
            'image',
        ]

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_message(self, obj):
        if not obj.is_available:
            return "Currently unavailable. Please call the owner to confirm."
        return None


class ProductViewLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductViewLog
        fields = ['id', 'product', 'viewed_at']
        read_only_fields = ['viewed_at']


class RelatedProductSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    section_name = serializers.CharField(source='category.section.name', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'is_available', 'image', 'category_name', 'section_name']

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None
