from django.contrib import admin

from apps.network.models import Hotspot, Organization, Site, Zone


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "status", "site_count"]
    list_filter = ["type", "status"]
    search_fields = ["name"]

    @admin.display(description="Sites")
    def site_count(self, obj):
        return obj.sites.count()


class ZoneInline(admin.TabularInline):
    model = Zone
    extra = 0
    fields = ["code", "label", "access_mode", "status"]
    show_change_link = True


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "status", "is_public", "has_coordinates"]
    list_filter = ["status", "is_public", "organization"]
    search_fields = ["name", "address"]
    inlines = [ZoneInline]

    @admin.display(boolean=True, description="Géolocalisé")
    def has_coordinates(self, obj):
        return obj.has_coordinates


class HotspotInline(admin.TabularInline):
    model = Hotspot
    extra = 0
    fields = ["nas_identifier", "label", "status", "provider"]
    show_change_link = True


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ["code", "label", "site", "access_mode", "status", "hotspot_count"]
    list_filter = ["access_mode", "status", "site__organization"]
    search_fields = ["code", "label"]
    inlines = [HotspotInline]

    @admin.display(description="Bornes")
    def hotspot_count(self, obj):
        return obj.hotspots.count()


@admin.register(Hotspot)
class HotspotAdmin(admin.ModelAdmin):
    list_display = ["nas_identifier", "label", "zone", "status", "provider", "vendor"]
    list_filter = ["status", "provider", "zone__site__organization"]
    search_fields = ["nas_identifier", "label", "external_id"]
