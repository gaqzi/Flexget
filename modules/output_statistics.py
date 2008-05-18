import sys, os.path
import types

__pychecker__ = 'unusednames=parser'

has_sqlite = True
try:
    import sqlite3 as sqlite # python >2.5 only
except:
    has_sqlite = False
    
# fall back to pysqlite on older versions
if not has_sqlite:
    try:
        from pysqlite2 import dbapi2 as sqlite
    except:
        has_sqlite = False

has_pygooglechart = True
try:
    from pygooglechart import StackedVerticalBarChart, Axis
except:
    has_pygooglechart = False

class Statistics:
    """
    Saves statistics about downloaded releases and generates graphs from the data.
    """
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0

    def register(self, manager, parser):
        manager.register(instance=self, event='input', keyword='statistics', callback=self.input, order=65535)
        manager.register(instance=self, event='exit', keyword='statistics', callback=self.exit)
        manager.register(instance=self, event='terminate', keyword='statistics', callback=self.generate_statistics)

    def init(self, con):
        """Create the sqlite table if necessary"""
        
        create = """
        CREATE TABLE IF NOT EXISTS statistics
        (
           timestamp TIMESTAMP,
           feed varchar(255),
           success integer,
           failure integer
        );"""
        cur = con.cursor()
        cur.execute(create)
        con.commit()
        
    def input(self, feed):
        if not has_sqlite:
            raise Exception('module statistics requires python-sqlite2 or python 2.5.')
        self.total = len(feed.entries)

    def exit(self, feed):
        self.passed = len(feed.entries)
        self.failed = self.total - self.passed

        dbname = os.path.join(sys.path[0], feed.manager.configname+".db")
        con = sqlite.connect(dbname)
        self.init(con)
        cur = con.cursor()

        cur.execute("insert into statistics (timestamp, feed, success, failure) values (datetime('now'), '%s', %d, %d);" % (feed.name, self.passed, self.failed))

        con.commit()
        con.close()


    def get_config(self, feed):
        config = feed.config['statistics']
        if type(config) != types.DictType:
            config = {'file': os.path.join(sys.path[0], feed.manager.configname+'_statistics.html')}

        return config

    def generate_statistics(self, feed):
        if not has_pygooglechart:
            raise Exception('module statistics requires pygooglechart library.')

        dbname = os.path.join(os.path.join(sys.path[0], feed.manager.configname+".db"))
        con = sqlite.connect(dbname)

        charts = []
        charts.append(self.weekly_stats_by_feed(con))
        charts.append(self.hourly_stats_by_feed(con))

        self.save_index(charts, feed)

    def save_index(self, charts, feed):
        imagelinks = ""
        for chart in charts:
            imagelinks += """<img src="%s" alt="" />""" % chart

        index = index_html % imagelinks

        config = self.get_config(feed)

        f = file(config['file'], 'w')
        f.write(index)
        f.close()

    def hourly_stats(self, con):
        sql = """
        select strftime("%H", timestamp, 'localtime') as hour, sum(success) from statistics group by hour
        """
        cur = con.cursor()
        cur.execute(sql)

        chart = StackedVerticalBarChart(680, 200, title="Releases by hour")
        axislabels = [str(i) for i in range(24)]
        data = 24*[0]
            
        axis = chart.set_axis_labels(Axis.BOTTOM, axislabels)
        chart.set_axis_style(axis, '000000', alignment=-1)

        for hour, success in cur:
            hour = int(hour)

            data[hour] = success

        chart.add_data(data)
        chart.set_axis_range(Axis.LEFT, 0, max(data))
        
        for i in range(0, len(data)):
            if data[i] > 0:
                chart.add_marker(0, i, 't%s'%data[i], '000000', 13)

        return chart.get_url()


    def hourly_stats_by_feed(self, con):
        sql = """
        select feed, strftime("%H", timestamp, 'localtime') as hour, sum(success) from statistics group by feed, hour;
        """

        cur = con.cursor()
        cur.execute(sql)

        chart = StackedVerticalBarChart(800, 200, title="Releases by source")
        axislabels = [str(i) for i in range(24)]
            
        axis = chart.set_axis_labels(Axis.BOTTOM, axislabels)
        chart.set_axis_style(axis, '000000', alignment=-1)

        feedname = ""
        maxdata = 0
        legend = []
        for feed, hour, success in cur:
            # clear data array for this feed
            if feed != feedname:
                feedname = feed
                legend.append(feedname)
                data = 24*[0]
                # add data set
                chart.add_data(data)

            success = int(success)
            if success > maxdata:
                maxdata = success
            data[int(hour)] = success

        # random colors
        #import random as rn
        #colors = ["".join(["%02x" % rn.randrange(256) for x in range(3)]) for i in range(len(legend))]
        colors = ('00FFFF', '0000FF', 'FF00FF', '008000', '808080', '00FF00', '800000', '000080', '808000', '800080', 'FF0000', 'C0C0C0', '008080', 'FFFF00')
        chart.set_colours(colors)

        chart.set_axis_range(Axis.LEFT, 0, maxdata)
        chart.set_legend(legend)

        return chart.get_url()

    def weekly_stats(self, con):
        sql = """
        select strftime("%w", timestamp, 'localtime') as dow, sum(success) from statistics group by dow
        """

        cur = con.cursor()
        cur.execute(sql)

        chart = StackedVerticalBarChart(220, 200, title="Releases by day of week")
        axis = chart.set_axis_labels(Axis.BOTTOM, ['mon','tue','wed','thu','fri','sat','sun'])
        chart.set_axis_style(axis, '000000', alignment=-1)

        data = 7*[0]

        for dow, success in cur:
            dow = int(dow) - 1
            if dow == -1:
                dow = 6

            data[dow] = success

        chart.add_data(data)
        chart.set_axis_range(Axis.LEFT, 0, max(data))

        for i in range(0, len(data)):
            if data[i] > 0:
                chart.add_marker(0, i, 't%s'%data[i], '000000', 13)

        return chart.get_url()

    def weekly_stats_by_feed(self, con):
        sql = """
        select feed, strftime("%w", timestamp, 'localtime') as hour, sum(success) from statistics group by feed, hour;
        """

        cur = con.cursor()
        cur.execute(sql)

        chart = StackedVerticalBarChart(350, 200, title="Releases by source")            
        axis = chart.set_axis_labels(Axis.BOTTOM, ['mon','tue','wed','thu','fri','sat','sun'])
        chart.set_axis_style(axis, '000000', alignment=-1)

        feedname = ""
        maxdata = 0
        legend = []
        for feed, dow, success in cur:
            dow = int(dow) - 1
            if dow == -1:
                dow = 6
            # clear data array for this feed
            if feed != feedname:
                feedname = feed
                legend.append(feedname)
                data = 7*[0]
                # add data set
                chart.add_data(data)

            success = int(success)
            if success > maxdata:
                maxdata = success
            data[dow] = success

        # random colors
        #import random as rn
        #colors = ["".join(["%02x" % rn.randrange(256) for x in range(3)]) for i in range(len(legend))]
        colors = ('00FFFF', '0000FF', 'FF00FF', '008000', '808080', '00FF00', '800000', '000080', '808000', '800080', 'FF0000', 'C0C0C0', '008080', 'FFFF00')
        chart.set_colours(colors)

        chart.set_axis_range(Axis.LEFT, 0, maxdata)
        chart.set_legend(legend)

        return chart.get_url()


index_html = """
<?xml version="1.0"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">
<head>
<title>Flexget statistics</title>
  <link rel="stylesheet" type="text/css" href="http://yui.yahooapis.com/2.5.1/build/reset-fonts-grids/reset-fonts-grids.css" />
  <link rel="stylesheet" type="text/css" href="http://yui.yahooapis.com/2.5.1/build/base/base-min.css" />
</head>
<body class="yui-skin-sam">
<h1>Stats</h1>

<div id="charts">
%s
</div>

</body>
</html>
"""

if __name__ == "__main__":
    dbname = os.path.join("../test.db")
    con = sqlite.connect(dbname)

    s = Statistics()

    s.weekly_stats_by_feed('config', con)
    #s.weekly_stats('config', con)
    #s.hourly_stats('config', con)
