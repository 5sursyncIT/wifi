from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone

from apps.core.admin import AuditedModelAdmin
from apps.core.audit import record_audit, snapshot
from apps.promotions.codes import issue_batch, prefix_of, revoke_batch, revoke_voucher
from apps.promotions.models import Campaign, Sponsor, Voucher, VoucherBatch, VoucherRedemption


def _is_partner(user) -> bool:
    return user.groups.filter(name="partenaire").exists() and not user.is_superuser


class PartnerScopedAdmin(AuditedModelAdmin):
    partner_lookup: str = ""

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if _is_partner(request.user) and self.partner_lookup:
            return queryset.filter(**{self.partner_lookup: request.user})
        return queryset


@admin.register(Sponsor)
class SponsorAdmin(PartnerScopedAdmin):
    list_display = ("name", "status", "partner_user")
    list_filter = ("status",)
    partner_lookup = "partner_user"


@admin.register(Campaign)
class CampaignAdmin(PartnerScopedAdmin):
    list_display = ("name", "sponsor", "status", "start_at", "end_at")
    list_filter = ("status", "sponsor")
    filter_horizontal = ("zones",)
    partner_lookup = "sponsor__partner_user"
    actions = ["end_campaign"]

    @admin.action(description="Clôturer les campagnes sélectionnées")
    def end_campaign(self, request, queryset):
        for campaign in queryset:
            before = snapshot(campaign)
            campaign.status = Campaign.Status.ENDED
            campaign.save(update_fields=["status", "updated_at"])
            record_audit(
                actor=request.user,
                action="campaign.end",
                target=campaign,
                before=before,
                after=snapshot(campaign),
            )


@admin.register(VoucherBatch)
class VoucherBatchAdmin(PartnerScopedAdmin):
    list_display = (
        "id",
        "plan_version",
        "quantity",
        "expires_at",
        "codes_exported_at",
    )
    list_filter = ("campaign",)
    partner_lookup = "campaign__sponsor__partner_user"
    actions = ["issue_codes", "revoke_codes"]

    @admin.action(description="Émettre les codes (CSV unique)")
    def issue_codes(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Sélectionnez un seul lot.", level=messages.ERROR)
            return None
        batch = queryset.get()
        try:
            codes = issue_batch(batch)
        except ValueError as error:
            self.message_user(request, str(error), level=messages.ERROR)
            return None
        batch.codes_exported_at = timezone.now()
        batch.save(update_fields=["codes_exported_at", "updated_at"])
        record_audit(
            actor=request.user,
            action="voucher.issue",
            target=batch,
            after={"quantity": len(codes)},
        )
        lines = ["prefix,code", *[f"{prefix_of(code)},{code}" for code in codes]]
        response = HttpResponse("\n".join(lines) + "\n", content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="vouchers-{batch.pk}.csv"'
        return response

    @admin.action(description="Révoquer les coupons non épuisés")
    def revoke_codes(self, request, queryset):
        for batch in queryset:
            count = revoke_batch(batch)
            record_audit(
                actor=request.user,
                action="voucher.revoke_batch",
                target=batch,
                after={"revoked": count},
            )
        self.message_user(request, "Coupons révoqués.")


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("prefix", "status", "uses_count", "max_uses", "batch")
    list_filter = ("status",)
    search_fields = ("prefix",)
    readonly_fields = [field.name for field in Voucher._meta.fields]
    actions = ["revoke_selected"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if _is_partner(request.user):
            return queryset.filter(batch__campaign__sponsor__partner_user=request.user)
        return queryset

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Révoquer")
    def revoke_selected(self, request, queryset):
        for voucher in queryset:
            before = snapshot(voucher)
            revoke_voucher(voucher)
            voucher.refresh_from_db()
            record_audit(
                actor=request.user,
                action="voucher.revoke",
                target=voucher,
                before=before,
                after=snapshot(voucher),
            )


@admin.register(VoucherRedemption)
class VoucherRedemptionAdmin(admin.ModelAdmin):
    list_display = ("voucher", "created_at")
    readonly_fields = [field.name for field in VoucherRedemption._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
