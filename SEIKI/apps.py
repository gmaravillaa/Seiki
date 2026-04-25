from django.apps import AppConfig

class SeikiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'SEIKI'

    def ready(self):
        import SEIKI.signals