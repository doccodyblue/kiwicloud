import requests
import json
import pathlib
import sqlite3
import urllib.parse
import time
import datetime
import uuid
import os
import urllib.parse
from wordcloud import WordCloud
from optparse import OptionParser


### todo: change old database structure and add "hidden" flag
parser = OptionParser()
parser.add_option("-s", "--server", type=str,
                  help="server name", dest="server", default='192.168.2.25')
parser.add_option("-p", "--port", type=int,
                  help="port number", dest="port", default=8073)
parser.add_option("-d", "--debug", type=int,
                  help="debug", dest="debug")

options = vars(parser.parse_args()[0])

if 'filename' in options:
    filename = options['filename']
else:
    filename = "kiwisqlite.db"

if 'debug' in options:
    if options['debug'] == 1:
        debug = True
    else:
        debug = False


host = options['server']
port = options['port']
kiwiserverurl = "http://" + host + ":" + str(port) + "/users"

# this is to prevent getting specific things into the statistics
# i.e. skimmer, you own call, ...
# needs to be in lowercase
ident_blacklist = ["digiskr_0.35.1", "snr-measure", "dg7lan", "dg7lan-p", "xyxc", "kiwirecorder.py", "supersdr", "wspr-autorun", "tdoa_service", "(no identity)", "???"]
ident_skimmer = "digiskr_0.35.1"
extension_modes = ["drm", "fax", "wspr", "fsk", "hfdl", "loran_c", "navtext", "sstv", "tdoa"]
frequency_blacklist = [30000]

# wait n seconds between polling data - don't recommend setting it to less than 30s
polldelay = 30

# don't change below
counter = 0
inuse_human = 0
inuse_skimmer = 0
inuse_idle = 0
hidden = 0


class db:
    def __init__(self, filename):
        self.filename = filename
        self.conn = sqlite3.connect(filename)
        self.cursor = self.conn.cursor()

        self.newDB()

    def add(self, slot, frequency, mode, username, hidden, location="", extension="", ip=""):
        if debug:
            print("|----> adding to QRGstat:", username, frequency, geo, mode, hidden)

        conhash = str(uuid.uuid4())[:8]

        username = urllib.parse.unquote(username)
        location = urllib.parse.unquote(location)

        self.cursor.execute("SELECT counter FROM qrgstat WHERE frequency = ? AND mode = ?", (str(frequency),mode.lower()))
        data = self.cursor.fetchone()
        if data is None:
            self.conn.execute("INSERT INTO qrgstat (frequency, mode, counter, sqltime) VALUES (?, ?, 1, ?)",
                              (frequency, mode.lower(), time.time()))
        else:
            print("|----> adding to QRGstat:", frequency)
            self.conn.execute("UPDATE qrgstat SET counter = counter +1 WHERE frequency = ? AND mode = ?", (str(frequency), mode.lower()))
            self.conn.execute("UPDATE qrgstat SET sqltime = ? WHERE frequency = ?", (time.time(), str(frequency)))

        self.conn.commit()

        self.cursor.execute("SELECT counter FROM geostat WHERE geo = ?",
                            (geo,))

        data = self.cursor.fetchone()
        if data is None:
            self.conn.execute("INSERT INTO geostat (geo, counter) VALUES (?, 1)",
                              (geo,))
        else:
            print("|----> adding to GEOstat:", geo)
            self.conn.execute("UPDATE geostat SET counter = counter +1 WHERE geo = ?",
                              (geo,))

        self.conn.commit()

        self.cursor.execute("SELECT counter FROM userstat WHERE user = ?", (str(username.lower()),))
        data = self.cursor.fetchone()
        if not username == "unknown":
            if data is None:
                self.conn.execute("INSERT INTO userstat (user, geo, extension, counter, hidden, ip) VALUES (?, ?, ?, 1, ?, ?)", (str(username.lower()), str(location), str(extension), hidden, str(ip)))
            else:
                self.conn.execute("UPDATE userstat SET counter = counter +1 WHERE user = ?", (username.lower(),))
                self.conn.execute("UPDATE userstat SET geo = ?, extension = ?, hidden = ?, ip = ? WHERE user = ?", (location, extension, hidden, ip, username.lower()))

            self.conn.execute("UPDATE userstat SET sqltime = ? WHERE user = ?", (time.time(), username.lower()))

            self.conn.commit()
        return conhash

    def readQrgFrequency(self):
        self.cursor.execute("SELECT frequency || '' || lower(mode), counter FROM qrgstat WHERE hidden IS NOT '1' ORDER BY counter DESC LIMIT 10")
        data = self.cursor.fetchall()
        return dict(data)

    def readUserData(self):
        self.cursor.execute("SELECT upper(user), counter FROM userstat WHERE hidden IS NOT '1'")
        data = self.cursor.fetchall()
        return dict(data)

    def readGeoData(self):
        self.cursor.execute("SELECT geo, counter FROM geostat WHERE hidden IS NOT '1'")
        data = self.cursor.fetchall()
        return dict(data)

    def readLastUser(self):
        c = self.cursor.execute("SELECT user, ip, sqltime FROM userstat WHERE hidden IS NOT '1' ORDER BY sqltime DESC limit 5")
        #data = self.cursor.fetchall()
        #return dict(data)
        return c

    def newDB(self):
        self.conn.execute("CREATE TABLE IF NOT EXISTS qrgstat (frequency TEXT(5), mode TEXT(5), counter INTEGER(12), hidden INTEGER(1), sqltime TIMESTAMP)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS userstat (user TEXT(15), geo TEXT(40), extension TEXT(10), counter INTEGER(12), hidden INTEGER(1), ip TEXT(16), sqltime TIMESTAMP)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS geostat (geo TEXT(40), counter INTEGER(12), hidden INTEGER(1))")

def get_json(url):
    try:
        r = requests.get(url=url, timeout=10)
    except requests.exceptions.RequestException as e:
        r = False
    return r


def create_cloud(filename, qrgs):
    # colormaps from matplotlib: ['viridis', 'plasma', 'inferno', 'magma', 'cividis'])
    cloud = WordCloud(width=860, height=300, background_color="white", colormap='plasma').generate_from_frequencies(dict(qrgs))
    cloud.to_file(filename)


sqlitepath = pathlib.Path(filename)

database = db(sqlitepath)

while 1:
    os.system('clear')
    print("|----------> Server: " + kiwiserverurl)
    now = datetime.datetime.now()
    print("|---------->", now.strftime("%H:%M:%S"))
    hidden = 0
    jdata = get_json(kiwiserverurl)
    if jdata:
        cont = json.loads(jdata.content.decode())
        for item in cont:
            counter += 1
            if not item.get('f') is None:
                # slot is in use
                username = item.get('n')
                ip = item.get('a')
                if username == "":
                    username = "unknown"
                printqrg = int(item.get('f')/1000)
                print("Slot", item.get('i'), "on", printqrg, "in use by", username)

                if item.get('n') in ident_skimmer and len(item.get('n')) >0:
                    inuse_skimmer += 1
                else:
                    inuse_human += 1
                    frequency = int(item.get('f') / 1000)
                    geo = item.get('g')
                    geo = urllib.parse.unquote(geo)
                    mode = item.get('m').lower()
                    extension = item.get('e').lower()
                    slot = item.get('i')

                    if not username.lower() in ident_blacklist and not frequency in frequency_blacklist:
                        if extension in extension_modes and len(extension) > 0:
                            if debug:
                                print("|----> swapped mode", mode, "for", extension)
                            mode = extension.upper()
                        if mode.upper() == "LSN":
                            mode = "LSB"
                        elif mode.upper() == "USN":
                            mode = "USB"
                        elif mode.upper() == "AMN":
                            mode = "AM"

                        if extension == "CW_decoder":
                            mode = "CW"
                        if len(username) < 3:
                            hidden = 1
                            
                        conhash = database.add(slot, frequency, mode, username=username, hidden=hidden, location=geo, extension=extension, ip=ip)
                    else:
                        if debug:
                            print("|---->", username, " / ", frequency," prevented due blacklist")
            else:
                print("Slot", item.get('i'), "is idle")
                inuse_idle += 1

        lastlogin = database.readLastUser()
        print("|-----------> Last users")
        for user, ip, ts in lastlogin:
            if ts:
                ts = datetime.datetime.fromtimestamp(ts)
            else:
                ts = "unknown"
            print("%16s %15s %s" % (user, ip, ts))

        qrgdata = database.readQrgFrequency()
        userdata = database.readUserData()
        geodata = database.readGeoData()
        if qrgdata:
            create_cloud("qrgcloud.png", qrgdata)
        if userdata:
            create_cloud("usercloud.png", userdata)
        if geodata:
            create_cloud("geocloud.png", geodata)
        time.sleep(polldelay)
    else:
        print("request failed. waiting 120s....")
        time.sleep(120)

