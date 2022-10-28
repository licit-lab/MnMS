from json import JSONEncoder
from importlib import import_module

import numpy as np


def load_class_by_module_name(cls):
    cls_name = cls.split('.')[-1]
    cls_module_name = cls.removesuffix('.' + cls_name)
    cls_module = import_module(cls_module_name)
    cls_class = getattr(cls_module, cls_name)

    return cls_class


class MNMSEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.int64):
            return int(obj)

        return super().default(obj)
