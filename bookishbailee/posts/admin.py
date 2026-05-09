from django.contrib import admin
from django.utils.html import format_html

from .models import BookshelfEntry, Category, Post, RightNowFeature, Tag, WebConfig


@admin.register(WebConfig)
class WebConfigAdmin(admin.ModelAdmin):
    list_display = ('key', 'enabled', 'description', 'updated_at')
    list_editable = ('enabled',)
    search_fields = ('key', 'description')
    readonly_fields = ('updated_at',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'post_count')
    list_editable = ('order',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    ordering = ('order', 'name')

    @admin.display(description='posts')
    def post_count(self, obj):
        return obj.posts.count()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'pub_date', 'is_featured', 'reading_time')
    list_filter = ('category', 'is_featured', 'tags')
    search_fields = ('title', 'body', 'excerpt')
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('tags',)
    autocomplete_fields = ('category',)
    readonly_fields = ('reading_time', 'updated_at', 'image_preview')
    date_hierarchy = 'pub_date'
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'category', 'tags', 'pub_date', 'is_featured'),
        }),
        ('Content', {
            'fields': ('excerpt', 'body', 'image', 'image_preview', 'caption'),
        }),
        ('Meta', {
            'fields': ('reading_time', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='preview')
    def image_preview(self, obj):
        if not obj.image:
            return ''
        return format_html(
            '<img src="{}" style="max-height:160px; border:1px solid #ccc;">',
            obj.image.url,
        )


@admin.register(BookshelfEntry)
class BookshelfEntryAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'order', 'updated_at')
    list_editable = ('order',)
    search_fields = ('title', 'author')
    ordering = ('order', 'title')


@admin.register(RightNowFeature)
class RightNowFeatureAdmin(admin.ModelAdmin):
    list_display = ('book_title', 'label', 'updated_at')
    fieldsets = (
        (None, {'fields': ('book_title', 'note', 'label')}),
        ('Meta', {'fields': ('updated_at',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        # Singleton — block "Add" once the row exists.
        return not RightNowFeature.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
