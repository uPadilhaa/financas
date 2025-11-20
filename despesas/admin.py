from django.contrib import admin
from django.db.models import QuerySet
from .models import Categoria, Despesa, ItemDespesa, Usuario

class OwnedByUserAdmin(admin.ModelAdmin):
    owner_field_name = "user" 
    limit_fk_by_owner = ()     

    def get_queryset(self, request):
        qs: QuerySet = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(**{self.owner_field_name: request.user})

    def save_model(self, request, obj, form, change):
        if not change or getattr(obj, self.owner_field_name, None) is None:
            setattr(obj, self.owner_field_name, request.user)
        return super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in getattr(self, "limit_fk_by_owner", ()):
            if request.user and not request.user.is_superuser:
                kwargs["queryset"] = db_field.related_model.objects.filter(
                    **{self.owner_field_name: request.user}
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class ItemDespesaInline(admin.TabularInline):
    model = ItemDespesa
    extra = 0
    readonly_fields = ("nome", "codigo", "quantidade", "unidade", "valor_unitario", "valor_total")
    can_delete = False

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "nome")
    list_filter = ("user",)
    ordering = ("user", "nome")

@admin.register(Despesa)
class DespesaAdmin(OwnedByUserAdmin):
    list_display = ("descricao", "valor", "data", "categoria", "user")
    list_filter = ("data", "categoria", "user")
    inlines = [ItemDespesaInline] 
    limit_fk_by_owner = ("categoria",)  

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "moeda")
    def email(self, obj): return obj.user.email