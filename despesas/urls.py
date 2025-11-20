from django.contrib import admin
from django.urls import path, include
from . import views as v

urlpatterns = [
    path("", v.home, name="home"),
    path("login/", v.pagina_login, name="login"),
    path("cadastro/", v.pagina_cadastro, name="signup"),
    path("accounts/", include("allauth.urls")),
    path("despesas/", v.listar_despesa, name="listar_despesa"),
    path("despesas/nova/", v.criar_despesa, name="despesa_criar"),
    path("despesas/<int:pk>/editar/", v.editar_despesa, name="despesa_editar"),
    path("categorias/nova/", v.criar_categoria, name="categoria_criar"),
    path("importar/nfce/", v.importar_nfce, name="despesa_importar_nfce"),
]
