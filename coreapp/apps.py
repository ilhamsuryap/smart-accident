from django.apps import AppConfig


class CoreappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'coreapp'
    verbose_name = 'Smart Accident - Core App'
    
    def ready(self):
        """Load signals ketika app siap"""
        import coreapp.signals  # noqa
