
import time
from uflacs.utils.log import debug

class TicToc(object):
    def __init__(self, name, showinfo=None, gettime=None):
        self.name = name
        self.info = showinfo or debug
        self.time = gettime or time.time
        self._ticdata = []

    def clear(self):
        self._ticdata = []

    def step(self, msg):
        self.info("[%s] starting: %s" % (self.name, msg))
        self._ticdata.append((self.time(), msg))

    def stop(self):
        self.info("[%s] stopping." % (self.name,))
        self._ticdata.append((self.time(), "END"))

    def timing_stats(self, sort=True):
        stats = []
        for i in range(len(self._ticdata)-1):
            t1, msg = self._ticdata[i]
            t2 = self._ticdata[i+1][0]
            t = t2-t1
            stats.append((t, msg))
        if sort:
            stats = sorted(stats, key=lambda x: -x[0])
        return stats

    def __getitem__(self, msg):
        stats = self.timing_stats()
        for t, m in stats:
            if m == msg:
                return t
        return None

    def __str__(self):
        lines = ["[Sorted timing summary for %s]:" % (self.name,)]
        for t, msg in self.timing_stats():
            lines.append("  %9.1f s   %s" % (t, msg))
        return '\n'.join(lines)