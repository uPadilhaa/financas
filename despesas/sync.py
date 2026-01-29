from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.socialaccount.models import SocialAccount

from .models.usuario import Usuario

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_usuario_for_user(sender, instance, created, **kwargs):
    if created:
        Usuario.objects.get_or_create(user=instance)

@receiver(post_save, sender=SocialAccount)
def sync_profile_from_socialaccount(sender, instance, created, **kwargs):

    perfil, _ = Usuario.objects.get_or_create(user=instance.user)
    data = instance.extra_data or {}
    foto = data.get("picture")
    if foto and perfil.foto_url != foto:
        perfil.foto_url = foto
        perfil.save()
