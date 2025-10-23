# despesas/admin.py
from django.contrib import admin
from django.db.models import QuerySet
from .models import Categoria, Despesa
from .models.usuario import Usuario


class OwnedByUserAdmin(admin.ModelAdmin):
    """
    Base para restringir o admin por usuário (se não for superuser)
    """

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


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "nome")
    list_display_links = ("id", "nome")
    search_fields = ("nome", "user__username", "user__email")
    list_filter = ("user",)
    ordering = ("user", "nome")


@admin.register(Despesa)
class DespesaAdmin(OwnedByUserAdmin):
    list_display = ("descricao", "valor", "data", "categoria", "user")
    search_fields = ("descricao",)
    list_filter = ("data", "categoria", "user")
    autocomplete_fields = ("categoria",)
    date_hierarchy = "data"
    limit_fk_by_owner = ("categoria",)  


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "moeda", "limite_mensal", "criado_em")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    list_select_related = ("user",)

    @admin.display(description="E-mail")
    def email(self, obj):
        return obj.user.email