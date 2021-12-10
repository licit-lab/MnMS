from decimal import Decimal
from typing import List

import numpy as np

class Time(object):
    def __init__(self, date):
        self._hours = None
        self._minutes = None
        self._seconds = None

        if date !=  "":
            self._str_to_floats(date)

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

    def __gt__(self, other):
        return self.to_seconds() > other.to_seconds()

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


    def add_time(self, hours:int=0, minutes:int=0, seconds:float=0):
        seconds = self._seconds + Decimal(seconds%60)
        minutes = self._minutes + Decimal(minutes) + Decimal(seconds//60)
        hours = self._hours + Decimal(hours) + Decimal(minutes//60)
        minutes = minutes%60
        seconds = seconds%60
        assert hours < 24

        new_time = Time("")
        new_time._hours = hours
        new_time._minutes = minutes
        new_time._seconds = seconds
        return new_time



class TimeTable(object):
    def __init__(self, times:List[Time]=[]):
        self.table:List[Time] = times

    @classmethod
    def create_table_freq(cls, start, end, delta_hour=0, delta_min=0, delta_sec=0):
        assert delta_hour!=0 or delta_min!=0 or delta_sec!=0
        table = []
        current_time = Time(start)
        end_time = Time(end)

        table.append(current_time)
        while current_time < end_time:
            ntime = current_time.add_time(hours=delta_hour, minutes=delta_min, seconds=delta_sec)
            table.append(ntime)
            current_time = ntime

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
    t = TimeTable()
    t.create_table("07:00:00", "18:00:00", delta_min=15, delta_sec=33)
    print(t.table)
    print(t.get_next_departure("15:48:52"))


    print(Time.fromSeconds(15000.35))
    print(t.get_freq())