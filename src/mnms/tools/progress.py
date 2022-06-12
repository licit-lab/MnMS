from math import ceil
from time import time_ns


def _format(timing):
    timing = float(timing)
    if timing < 1e3:
        return f"{timing:.2f} ns"
    elif timing < 1e6:
        return f"{timing / 1e3:.2f} us"
    elif timing < 1e9:
        return f"{timing/1e6:.2f} ms"
    elif timing < 6e10:
        return f"{timing / 1e9:.2f} s"
    elif timing < 3.6e+12:
        return f"{int(timing / 6e10)} min"
    else:
        return f"{int(timing /  3.6e+12)} hours"


class ProgressBarIterable(object):
    def __init__(self, iterable, text='Run', size_bar=20, item='■'):
        self._iterable = iter(iterable)
        self._max = len(iterable)
        self._index = 0
        self._text = text
        self._size_bar = size_bar
        self._item = item

        self._bar = None
        self._ptime = None

    def update(self):
        timing = time_ns()
        cur = (self._index/self._max)*self._size_bar
        nb_hash = ceil(cur)
        perc = round(self._index/self._max*100)
        prog = self._item*nb_hash+' '*(self._size_bar-nb_hash)
        self._bar = '\r'+self._text+' |{item}| {perc} %'.format(item=prog,perc=perc)

        if self._ptime:
            remaining_time = (timing-self._ptime)*(self._max-self._index)
            self._bar += f" | remain ~ {_format(remaining_time)}"

        self._index += 1
        self._ptime = time_ns()

    def show(self):
        print(self._bar, end='', flush=True)

    def __iter__(self):
        self._index = 0
        return self

    def __next__(self):
        if self._index < self._max:
            res = next(self._iterable)
            self.update()
            self.show()
            return res
        else:
            self.update()
            self.show()
            print('')
            raise StopIteration


class ProgressBar(object):
    def __init__(self, stop:int, start=0, text='Run', size_bar=20, item='■'):
        self._max = stop
        self._index = start
        self._text = text
        self._size_bar = size_bar
        self._item = item

        self._bar = None
        self._ptime = None

    def update(self):
        timing = time_ns()
        cur = (self._index/self._max)*self._size_bar
        nb_hash = ceil(cur)
        perc = round(self._index/self._max*100)
        prog = self._item*nb_hash+' '*(self._size_bar-nb_hash)
        # self._bar = '\r'+self._text+' |{item}| {perc} %'.format(item=prog,perc=perc)
        self._bar = f"\r{self._text} |{prog}| {perc} %"

        if self._ptime:
            remaining_time = (timing-self._ptime)*(self._max-self._index)
            self._bar += f" | remain ~ {_format(remaining_time)}"

        self._index += 1
        self._ptime = time_ns()

    def show(self):
        print(self._bar, end='', flush=True)

    def execute(self, func, *args, **kwargs):
        func(*args, **kwargs)
        self.update()
        self.show()

    def __iter__(self):
        self._index = 0
        return self


if __name__ == '__main__':
    from time import sleep, time
    # for i in ProgressBarIterable(range(100000), item="#"):
    #     sleep(1)

    n = 100
    p = ProgressBar(n)
    for i in range(n):
        p.execute(sleep, 1)
