class CostDict(object):
    def __init__(self, *iterables, **kwargs):
        for k, v in iterables:
            assert isinstance(k, str), f"{k} must be a string"
            assert isinstance(v, (float, int)), f"{v} must be a float or int"

        for k, v in kwargs.items():
            assert isinstance(k, str), f"{k} must be a string"
            assert isinstance(v, (float, int)), f"{v} must be a float or int"

        self.__store = dict(iterables)
        self.__store.update(kwargs)

    def get(self, key:str, default=0):
        return self.__store.get(key, default)

    def update_from_dict(self, d:dict):
        for k, v in d.items():
            assert isinstance(k, str), f"{k} must be a string"
            assert isinstance(v, (float, int)), f"{v} must be a float or int"

        self.__store.update(d)

    def keys(self):
        return self.__store.keys()

    def values(self):
        return self.__store.values()

    def items(self):
        return self.__store.items()

    def __setitem__(self, key, value):
        assert isinstance(value, (float, int)), f"{value} must be a float or int"
        assert isinstance(key, str), f"{key} must be a string"
        self.__store.__setitem__(key, value)

    def __getitem__(self, item):
        return self.__store.__getitem__(item)

    def __mul__(self, other):
        return CostDict(*[(key, other*val) for key, val in self.__store.items()])

    def __rmul__(self, other):
        return self.__mul__(other)

    def __add__(self, other):
        return CostDict(*[(key, self.get(key) + other.get(key)) for key in set(self.__store.keys()).union(other.__store.keys())])

    def __radd__(self, other):
        return self.__add__(other)

    def __repr__(self):
        return f"CostDict({', '.join([f'{k.__repr__()}:{v.__repr__()}' for k, v in self.__store.items()])})"

    def __deepcopy__(self, memodict={}):
        return CostDict(**self.__store)
