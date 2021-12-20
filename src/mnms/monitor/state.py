import pandas as pd


class StateFlow(object):
    def __init__(self, *fields):
        self._data = pd.DataFrame(columns=fields)
        self._time = None
        self.__entry_counter = 0

    def __getitem__(self, item):
        return self._data[item]

    def __eq__(self, other):
        return self._data.__eq__(other)

    def add_entry(self, **kwargs):
        for key, val in kwargs.items():
            self._data.at[self.__entry_counter, key] = val
        self.__entry_counter += 1

    def update_entry(self, ind: int, **kwargs):
        for key, val in kwargs.items():
            self._data.at[ind, key] = val

    def update_time(self, time):
        self._time = time


if __name__ == "__main__":
    state = StateFlow('user', 'speed', 'pos')

    state.add_entry(user='0', speed=23, pos=[0, 0])
    state.add_entry(user='1', speed=3, pos=[0, 0])
    state.add_entry(user='2', speed=2)



