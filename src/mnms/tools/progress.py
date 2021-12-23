from math import floor, ceil

class ProgressBar(object):
    def __init__(self, iterable, text='Run', size_bar=20, item='■'):
        self._iterable = iter(iterable)
        self._max = len(iterable)
        self._index = 0
        self._text = text
        self._size_bar = size_bar
        self._item = item

        self._bar = None

    def update(self):
        cur = (self._index/self._max)*self._size_bar
        nb_hash = ceil(cur)
        perc = round(self._index/self._max*100)
        prog = self._item*nb_hash+' '*(self._size_bar-nb_hash)
        self._bar = '\r'+self._text+' |{item}| {perc} %'.format(item=prog,perc=perc)

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
            self._index += 1
            return res
        else:
            self.update()
            self.show()
            print('')
            raise StopIteration


if __name__ == '__main__':
    from time import sleep, time
    for i in ProgressBar(range(1000)):
        # print(i)
        sleep(0.001)


        def f():
            for i in range(1000):
                sleep(0.001)