from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

class DisableMessagesAccountAdapter(DefaultAccountAdapter):
    def add_message(self, request, level, message_template, message_context=None, extra_tags=''):
        pass

class DisableMessagesSocialAccountAdapter(DefaultSocialAccountAdapter):
    def add_message(self, request, level, message_template, message_context=None, extra_tags=''):
        pass