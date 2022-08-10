import requests
import json
import pathlib
import sqlite3
import urllib.parse
import time
import datetime
import uuid
import os
from wordcloud import WordCloud
from optparse import OptionParser

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
ident_blacklist = ["digiskr_0.35.1", "snr-measure", "dg7lan"]
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


class db:
    def __init__(self, filename):
        self.filename = filename
        self.conn = sqlite3.connect(filename)
        self.cursor = self.conn.cursor()

        self.newDB()

    def add(self, slot, frequency, mode, username, location="", extension=""):
        if debug:
            print("|----> adding to QRGstat:", username, frequency, geo, mode)
        conhash = str(uuid.uuid4())[:8]

        self.cursor.execute("SELECT counter FROM qrgstat WHERE frequency = ? AND mode = ?", (str(frequency),mode.lower()))
        data = self.cursor.fetchone()
        if data is None:
            self.conn.execute("INSERT INTO qrgstat (frequency, mode, counter) VALUES (?, ?, 1)",
                              (frequency, mode.lower()))
        else:
            print("|----> adding to QRGstat:", frequency)
            self.conn.execute("UPDATE qrgstat SET counter = counter +1 WHERE frequency = ? AND mode = ?", (str(frequency), mode.lower()))

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
                self.conn.execute("INSERT INTO userstat (user, geo, extension, counter) VALUES (?, ?, ?, 1)", (str(username.lower()), str(location), str(extension)))
            else:
                self.conn.execute("UPDATE userstat SET counter = counter +1 WHERE user = ?", (username.lower(),))
                self.conn.execute("UPDATE userstat SET geo = ?, extension = ? WHERE user = ?", (location, extension, username.lower()))

            self.conn.commit()
        return conhash

    def readQrgFrequency(self):
        self.cursor.execute("SELECT frequency || ' ' || upper(mode), counter FROM qrgstat ORDER BY counter DESC LIMIT 16")
        data = self.cursor.fetchall()
        return dict(data)

    def readUserData(self):
        self.cursor.execute("SELECT upper(user), counter FROM userstat")
        data = self.cursor.fetchall()
        return dict(data)

    def readGeoData(self):
        self.cursor.execute("SELECT geo, counter FROM geostat")
        data = self.cursor.fetchall()
        return dict(data)

    def newDB(self):
        self.conn.execute("CREATE TABLE IF NOT EXISTS qrgstat (frequency TEXT(5), mode TEXT(5), counter INTEGER(12))")
        self.conn.execute("CREATE TABLE IF NOT EXISTS userstat (user TEXT(15), geo TEXT(40), extension TEXT(10), counter INTEGER(12))")
        self.conn.execute("CREATE TABLE IF NOT EXISTS geostat (geo TEXT(40), counter INTEGER(12))")


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

    jdata = get_json(kiwiserverurl)
    if jdata:
        cont = json.loads(jdata.content.decode())
        for item in cont:
            counter += 1
            if not item.get('f') is None:
                # slot is in use
                username = item.get('n')
                if username == "":
                    username = "unknown"
                printqrg = int(item.get('f')/1000)
                print("Slot", item.get('i'), "on", printqrg, "in use by", username)
                #print("{:10.4f}".format(x))
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
                        if mode == "lsn":
                            mode = "LSB"
                        if mode == "usn":
                            mode = "USB"

                        conhash = database.add(slot, frequency, mode, username=username, location=geo, extension=extension)
                    else:
                        if debug:
                            print("|---->", username, " / ", frequency," prevented due blacklist")
            else:
                print("Slot", item.get('i'), "is idle")
                inuse_idle += 1

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

