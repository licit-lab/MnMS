from math import ceil
from time import perf_counter_ns


def _format(timing):
    timing = float(timing)
    if timing < 6e10:
        return f"{int(timing / 1e9)} s"
    elif timing < 3.6e+12:
        return f"{int(timing / 6e10)} min"
    else:
        return f"{int(timing /  3.6e+12)} hours"


class ProgressBar(object):
    def __init__(self, stop: int, start=0, text='Run', size_bar=20, item='■'):
        self._max = stop
        self._index = start
        self._text = text
        self._size_bar = size_bar
        self._item = item

        self._bar = None
        self._ptime = None
        self._mean_time = 0

    def update(self):
        timing = perf_counter_ns()
        cur = (self._index/self._max)*self._size_bar
        nb_hash = ceil(cur)
        perc = round(self._index/self._max*100)
        prog = self._item*nb_hash+' '*(self._size_bar-nb_hash)
        self._bar = f"\r{self._text} |{prog}| {perc} %"

        if self._ptime is not None:
            new_iter_time = timing - self._ptime
            self._mean_time = self._mean_time + (new_iter_time - self._mean_time)/self._index
            remaining_time = self._mean_time*(self._max - self._index)
            self._bar += f" | remain ~ {_format(remaining_time)}"

        self._index += 1
        self._ptime = perf_counter_ns()

    def show(self):
        print(self._bar, end='', flush=True)

    def end(self) -> None:
        print("")

    def execute(self, func, *args, **kwargs):
        func(*args, **kwargs)
        self.update()
        self.show()


if __name__ == '__main__':
    from time import sleep

    n = 100
    p = ProgressBar(n)
    for i in range(n):
        p.execute(sleep, 1)
