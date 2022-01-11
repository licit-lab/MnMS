from decimal import Decimal
from typing import List

import numpy as np


class Dt(object):
    def __init__(self, hours:int=0, minutes:int=0, seconds:float=0):
        new_seconds = Decimal(seconds)%60
        new_minutes = minutes + seconds//60
        hours = hours + new_minutes//60
        minutes = new_minutes%60
        seconds = new_seconds%60

        self._hours = hours
        self._minutes = minutes
        self._seconds = Decimal(seconds)

    def __mul__(self, other:int):
        seconds = self._seconds*other
        minutes = int(self._minutes*other)
        hours = int(self._hours*other)
        return Dt(hours, minutes, seconds)

    def __repr__(self):
        return f"dt(hours:{self._hours}, minutes:{self._minutes}, seconds:{self._seconds})"

    def to_seconds(self):
        return float(int(self._hours*3600)+int(self._minutes*60)+self._seconds)


class Time(object):
    def __init__(self, strdate="00:00:00"):
        self._hours = None
        self._minutes = None
        self._seconds = None

        if strdate != "":
            self._str_to_floats(strdate)

    def _str_to_floats(self, date):
        split_string = date.split(':')
        self._hours = Decimal(split_string[0])
        self._minutes = Decimal(split_string[1])
        self._seconds = Decimal(split_string[2])

    def to_seconds(self):
        return float(self._hours*3600+self._minutes*60+self._seconds)

    @classmethod
    def fromSeconds(cls, seconds:float):
        time = cls('')
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        time._seconds = s
        time._minutes = int(m)
        time._hours = int(h)

        return time

    def __repr__(self):
        return f"Time({self.time})"

    def __lt__(self, other):
        return self.to_seconds() < other.to_seconds()

    def __le__(self, other):
        return self.to_seconds() <= other.to_seconds()

    def __gt__(self, other):
        return self.to_seconds() > other.to_seconds()

    def __ge__(self, other):
        return self.to_seconds() >= other.to_seconds()

    @property
    def seconds(self):
        return float(self._seconds)

    @seconds.setter
    def seconds(self, value):
        assert value < 60
        self._seconds = Decimal(value)

    @property
    def minutes(self):
        return int(self._minutes)

    @minutes.setter
    def minutes(self, value):
        assert value < 60
        self._minutes = Decimal(value)

    @property
    def hours(self):
        return int(self._hours)

    @hours.setter
    def hours(self, value):
        assert value < 24
        self._hours = Decimal(value)

    @property
    def time(self):
        return f"{str(self._hours) if self._hours >= 10 else '0' + str(self._hours)}:{str(self._minutes) if self._minutes >= 10 else '0' + str(self._minutes)}:{str(round(self._seconds, 2)) if self._seconds >= 10 else '0' + str(round(self._seconds, 2))}"

    def add_time(self, dt: Dt):
        new_seconds = self._seconds + Decimal(dt._seconds)
        new_minutes = self._minutes + Decimal(dt._minutes) + Decimal(new_seconds//60)
        new_seconds = new_seconds%60
        # print(new_minutes)
        hours = self._hours + Decimal(dt._hours) + Decimal(new_minutes//60)
        new_minutes = new_minutes%60
        # print(new_minutes)
        new_seconds = new_seconds%60
        # print(hours, new_minutes, new_seconds)
        assert hours <= 24

        new_time = Time("")
        new_time._hours = hours
        new_time._minutes = new_minutes
        new_time._seconds = new_seconds
        return new_time

    def remove_time(self, dt:Dt):
        new_seconds = self._seconds - Decimal(dt._seconds%60)
        new_minutes = self._minutes - (Decimal(dt._minutes) + Decimal(dt._seconds//60))
        hours = self._hours - (Decimal(dt._hours) + Decimal(new_minutes//60))
        new_minutes = new_minutes%60
        new_seconds = new_seconds%60
        if new_seconds < 0:
            n = -new_seconds//60
            new_seconds = 60*n - new_seconds%60
            new_minutes -= n
        if new_minutes < 0:
            n = -new_minutes // 60 +1
            new_minutes = 60*n + new_minutes%60
            hours -= n

        assert new_seconds >= 0, f"{new_seconds}"
        assert new_minutes >= 0, f"{new_minutes}"
        assert hours >= 0

        new_time = Time("")
        new_time._hours = hours
        new_time._minutes = new_minutes
        new_time._seconds = new_seconds
        return new_time


class TimeTable(object):
    def __init__(self, times:List[Time]=None):
        self.table:List[Time] = times if times is not None else []

    @classmethod
    def create_table_freq(cls, start, end, dt:Dt):
        assert dt._hours!=0 or dt._minutes!=0 or dt._seconds!=0
        table = []
        current_time = Time(start)
        end_time = Time(end)
        end_time_dt = end_time.remove_time(dt)
        table.append(current_time)
        while current_time <= end_time_dt:
            ntime = current_time.add_time(dt)
            table.append(ntime)
            current_time = ntime
        # print(current_time)
        # table.append(current_time)

        return cls(table)

    def get_next_departure(self, date):
        for d in self.table:
            if date < d:
                return d

    def get_freq(self):
        if len(self.table) > 1:
            waiting_times_seconds = [self.table[i+1].to_seconds()-self.table[i].to_seconds() for i in range(len(self.table)-1)]
            return np.mean(waiting_times_seconds)
        else:
            return None


if __name__ == "__main__":
    # t = TimeTable.create_table_freq("05:00:00", "22:00:00", Dt(seconds=600))

    t = Time.fromSeconds(0)

    t2 = t.add_time(Dt(seconds=32))
    t3 = t2.add_time(Dt(seconds=30))
    print(t3)