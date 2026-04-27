"""Subscribers admin with CSV export.

The CSV export is critical — it's the path off this Django-native
storage and into any newsletter provider (Buttondown / ConvertKit /
Substack / Listmonk all accept CSV imports).
"""
import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import Subscriber


def export_as_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="subscribers.csv"'
    writer = csv.writer(response)
    writer.writerow(['email', 'source', 'confirmed', 'unsubscribed', 'created_at'])
    for sub in queryset.order_by('created_at'):
        writer.writerow([
            sub.email,
            sub.source,
            sub.confirmed,
            sub.unsubscribed,
            sub.created_at.isoformat(),
        ])
    return response

export_as_csv.short_description = 'Export selected as CSV'


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'source', 'confirmed', 'unsubscribed', 'created_at')
    list_filter = ('source', 'confirmed', 'unsubscribed', 'created_at')
    search_fields = ('email',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    actions = [export_as_csv]
