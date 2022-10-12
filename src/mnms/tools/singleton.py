"""Classe générique pour implémenter des singleton."""


class Singleton(type):
    """Meta-Classe de singleton."""

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """Appel d'une classe singleton."""
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args,
                                                                 **kwargs)
        return cls._instances[cls]
