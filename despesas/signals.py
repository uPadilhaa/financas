# Arquivo: despesas/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from despesas.models import Usuario

class OnboardingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        urls_permitidas = [
            reverse('account_login'),
            reverse('account_logout'),
            reverse('account_signup'),
            reverse('onboarding_renda'),
            reverse('onboarding_notificacoes'),
            '/admin/',
            '/accounts/', 
        ]

        if request.user.is_authenticated:
            path = request.path_info            
            if any(path.startswith(u) for u in urls_permitidas):
                return self.get_response(request)

            try:
                perfil = Usuario.objects.get(user=request.user)                
                if not perfil.renda_fixa or perfil.renda_fixa == 0:
                    return redirect('onboarding_renda')

            except Usuario.DoesNotExist:
                Usuario.objects.create(user=request.user)
                return redirect('onboarding_renda')

        response = self.get_response(request)
        return response