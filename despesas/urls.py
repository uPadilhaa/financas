from django.urls import path, include
from . import views as v

urlpatterns = [
    path("", v.home, name="home"),
    path("login/", v.pagina_login, name="login"),
    path("cadastro/", v.pagina_cadastro, name="signup"),
    path("dashboard/", v.dashboard, name="dashboard"),
    path("configuracao/", v.configurar_financas, name="configurar_financas"), 
    path("configuracao/limites/", v.salvar_limites, name="salvar_limites"), 
    path("accounts/", include("allauth.urls")),   
    path("despesas/", v.listar_despesa, name="listar_despesa"),
    path("despesas/criar/", v.criar_despesa, name="despesa_criar"),
    path("despesas/<int:pk>/editar/", v.editar_despesa, name="despesa_editar"),
    path("despesas/<int:pk>/deletar/", v.deletar_despesa, name="despesa_deletar"),    
    path("categorias/", v.listar_categorias, name="listar_categorias"),
    path("categorias/nova/", v.criar_categoria, name="categoria_criar"),
    path("categorias/<int:pk>/editar/", v.editar_categoria, name="categoria_editar"),
    path("categorias/<int:pk>/deletar/", v.deletar_categoria, name="categoria_deletar"),
    path("receitas/", v.listar_receitas, name="listar_receitas"),
    path("receitas/nova/", v.criar_receita, name="receita_criar"),
    path("receitas/<int:pk>/editar/", v.editar_receita, name="receita_editar"),
    path("receitas/<int:pk>/deletar/", v.deletar_receita, name="receita_deletar"),
    path("importar/NFe/", v.importar_NFe, name="despesa_importar_nfe"),
]