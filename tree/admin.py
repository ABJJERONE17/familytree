"""Admin screens used for data entry."""
from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from .models import Marriage, Person


class LivingFilter(admin.SimpleListFilter):
    """Sidebar filter: Living / Deceased."""

    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [("living", "Living"), ("deceased", "Deceased")]

    def queryset(self, request, queryset):
        if self.value() == "living":
            return queryset.filter(death_date__isnull=True)
        if self.value() == "deceased":
            return queryset.filter(death_date__isnull=False)
        return queryset


class MarriageInline(admin.TabularInline):
    """Add a spouse directly on the person's page."""

    model = Marriage
    fk_name = "partner1"  # Marriage has two links to Person; this is the one to use
    autocomplete_fields = ["partner2"]
    extra = 0
    verbose_name = "marriage"
    verbose_name_plural = "Marriages (add a spouse here)"


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["thumbnail", "full_name", "gender", "born", "status", "current_city"]
    list_display_links = ["thumbnail", "full_name"]
    list_filter = ["gender", LivingFilter, "current_city"]
    # search_fields also powers the type-a-name pickers (autocomplete_fields).
    search_fields = ["first_name", "last_name", "nickname"]
    autocomplete_fields = ["father", "mother"]
    readonly_fields = ["photo_preview", "status", "all_spouses"]
    list_per_page = 50
    inlines = [MarriageInline]

    fieldsets = [
        ("Name", {"fields": [("first_name", "last_name"), "nickname", "gender"]}),
        (
            "Life",
            {
                "fields": [
                    ("birth_date", "birth_date_precision"),
                    ("death_date", "death_date_precision"),
                    "status",
                    ("birthplace", "current_city"),
                    "occupation",
                ]
            },
        ),
        ("Parents", {"fields": [("father", "mother")]}),
        ("Photo and biography", {"fields": ["photo", "photo_preview", "biography"]}),
        ("Spouses", {"fields": ["all_spouses"]}),
    ]

    @admin.display(description="Photo")
    def thumbnail(self, obj):
        return format_html(
            '<img src="{}" alt="" style="width:40px;height:40px;'
            'object-fit:cover;border-radius:50%;filter:grayscale(1);">',
            obj.photo_url,
        )

    @admin.display(description="Preview")
    def photo_preview(self, obj):
        return format_html(
            '<img src="{}" alt="" style="width:160px;height:160px;'
            'object-fit:cover;filter:grayscale(1);">',
            obj.photo_url,
        )

    @admin.display(description="Name", ordering="last_name")
    def full_name(self, obj):
        return obj.full_name

    @admin.display(description="Born", ordering="birth_date")
    def born(self, obj):
        return obj.birth_display or "-"

    @admin.display(description="Age / late")
    def status(self, obj):
        return obj.life_summary or "-"

    @admin.display(description="All recorded spouses")
    def all_spouses(self, obj):
        if not obj.pk:
            return "-"
        rows = [
            (marriage.partner_of(obj).full_name, marriage.marriage_display or "date unknown")
            for marriage in obj.marriages()
        ]
        if not rows:
            return "-"
        return format_html_join(mark_safe("<br>"), "{} ({})", rows)


@admin.register(Marriage)
class MarriageAdmin(admin.ModelAdmin):
    list_display = ["partner1", "partner2", "married", "end_date"]
    autocomplete_fields = ["partner1", "partner2"]
    search_fields = [
        "partner1__first_name",
        "partner1__last_name",
        "partner2__first_name",
        "partner2__last_name",
    ]
    list_select_related = ["partner1", "partner2"]

    @admin.display(description="Married", ordering="marriage_date")
    def married(self, obj):
        return obj.marriage_display or "-"
