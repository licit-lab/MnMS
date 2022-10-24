"""
Manage database settings.
"""
from os import path
from typing import Dict, Optional

from mnms.tools.singleton import Singleton


class DbSettings(metaclass=Singleton):
    """
    Maanage database settings.
    """
    def __init__(self):
        self._db_folder: str = "./"
        self._max_file_number: int = -1
        self._recovery_db_name: Optional[str] = None

    def load_from_dict(self, dict_param: Dict):
        """Load settings from the json."""
        self._db_folder = dict_param.get("db_folder", "./")
        self._max_file_number = dict_param.get("max_file_number", -1)
        self._recovery_db_name = dict_param.get("recovery_database_name", None)
        # verification of the file existence
        if self._recovery_db_name:
            if not path.exists(path.join(self._db_folder, self._recovery_db_name)):
                self._recovery_db_name = None

    @property
    def db_folder(self) -> str:
        """Return the folder where the database is created."""
        return self._db_folder

    @property
    def max_file_number(self) -> int:
        """Return the number max of database files in the folder."""
        return self._max_file_number + 1 if self._recovery_db_name else self._max_file_number

    @property
    def recovery_db_name(self) -> Optional[str]:
        """Return the name of the database to use ib case of resuming the simulation."""
        return self._recovery_db_name
