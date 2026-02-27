from django import forms

from .models import Advertisement, Category, Product


class AdminProductCreateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "price",
            "stock_qty",
            "image",
            "description",
            "related_products",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "related_products": forms.SelectMultiple(attrs={"size": 8}),
        }

    def __init__(
        self,
        *args,
        section=None,
        category_queryset=None,
        related_choices=None,
        load_related=False,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.section = section

        self.fields["stock_qty"].initial = self.initial.get("stock_qty", 20)
        if "related_products" in self.fields:
            self.fields["related_products"].required = False

        if category_queryset is not None:
            self.fields["category"].queryset = category_queryset
        elif section is not None:
            self.fields["category"].queryset = Category.objects.filter(section=section).order_by("name")
        else:
            self.fields["category"].queryset = Category.objects.none()
        # Avoid N+1 from Category.__str__ (which touches section) while rendering choices.
        self.fields["category"].label_from_instance = lambda obj: obj.name

        if load_related and "related_products" in self.fields:
            if related_choices is not None:
                ids = [pid for pid, _ in related_choices]
                related_qs = Product.objects.filter(id__in=ids).only("id", "name").order_by("name")
                self.fields["related_products"].queryset = related_qs
            elif section is not None:
                self.fields["related_products"].queryset = Product.objects.filter(
                    category__section=section
                ).only("id", "name").order_by("-created_at", "name")[:200]
            else:
                self.fields["related_products"].queryset = Product.objects.none()
        else:
            # Fast path: remove the field entirely to avoid extra rendering and M2M DB checks.
            self.fields.pop("related_products", None)

    def clean_category(self):
        category = self.cleaned_data.get("category")
        if self.section is not None and category and category.section_id != self.section.id:
            raise forms.ValidationError("Please select a category from the chosen section.")
        return category


class AdminAdvertisementForm(forms.ModelForm):
    class Meta:
        model = Advertisement
        fields = [
            "title",
            "subtitle",
            "image",
            "cta_label",
            "cta_url",
            "display_order",
            "is_active",
        ]
        widgets = {
            "subtitle": forms.TextInput(attrs={"placeholder": "Short attractive text"}),
            "cta_label": forms.TextInput(attrs={"placeholder": "Example: Order Now"}),
            "cta_url": forms.TextInput(attrs={"placeholder": "Example: /snacks/"}),
        }
