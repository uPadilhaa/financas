from django.urls import path, include
from . import views as v

urlpatterns = [
    path("", v.home, name="home"),
    path("accounts/", include("allauth.urls")),
    
    path("despesas/", v.listar_despesa, name="listar_despesa"),
    path("despesas/nova/", v.criar_despesa, name="despesa_criar"),
    path("despesas/<int:pk>/editar/", v.editar_despesa, name="despesa_editar"),
    path("despesas/<int:pk>/deletar/", v.deletar_despesa, name="despesa_deletar"), # Nova
    
    path("categorias/", v.listar_categorias, name="listar_categorias"), # Nova
    path("categorias/nova/", v.criar_categoria, name="categoria_criar"),
    path("categorias/<int:pk>/editar/", v.editar_categoria, name="categoria_editar"), # Nova
    path("categorias/<int:pk>/deletar/", v.deletar_categoria, name="categoria_deletar"), # Nova

    path("importar/nfce/", v.importar_nfce, name="despesa_importar_nfce"),
]