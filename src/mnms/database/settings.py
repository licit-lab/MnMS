# -*- coding: utf-8 -*-
from typing import Dict

from mnms.tools.singleton import Singleton


class DbSettings(metaclass=Singleton):
    def __init__(self):
        self._db_folder: str = "./"
        self._max_file_number = -1

    def load_from_dict(self, dict_param: Dict):
        self._db_folder = dict_param.get("db_folder", "./")
        self._max_file_number = dict_param.get("max_file_number", -1)

    @property
    def db_folder(self):
        return self._db_folder

    @property
    def max_file_number(self):
        return self._max_file_number

