import pandas as pd


class StateFlow(object):
    def __init__(self, *fields):
        self._data = pd.DataFrame(columns=fields)
        self.__entry_counter = 0

    def add_entry(self, **kwargs):
        for key, val in kwargs.items():
            self._data.at[self.__entry_counter, key] = val

        self.__entry_counter += 1

    def __getitem__(self, item):
        return self._data[item].to_xarray()

if __name__ == "__main__":
    state = StateFlow('user', 'speed', 'pos')

    state.add_entry(user='0', speed=23, pos=[0, 0])
    state.add_entry(user='1', speed=3, pos=[0, 0])
    state.add_entry(user='2', speed=2)



