import requests
import json
import pathlib
import sqlite3
import urllib.parse
import time
import datetime
import uuid
from wordcloud import WordCloud
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-s", "--server", type=str,
                  help="server name", dest="server", default='192.168.2.25')
parser.add_option("-p", "--port", type=int,
                  help="port number", dest="port", default=8073)

options = vars(parser.parse_args()[0])

if 'filename' in options:
    filename = options['filename']
else:
    filename = "kiwisqlite.db"

host = options['server']
port = options['port']
kiwiserverurl = "http://" + host + ":" + str(port) + "/users"

# this is to prevent me getting added to the statistics
# todo turn this into a blacklist
ident_blacklist = ["digiskr_0.35.1", "SNR-measure", "dg7lan"]
ident_skimmer = "digiskr_0.35."
extension_modes = ["drm", "fax", "wspr","fsk"]
frequency_blacklist = [6160, 30000]
debug = True
counter = 0
inuse_human = 0
inuse_skimmer = 0
inuse_idle = 0

print("Kiwi Server is: " + kiwiserverurl)


class db:
    def __init__(self, filename):
        self.filename = filename
        self.conn = sqlite3.connect(filename)
        self.cursor = self.conn.cursor()

        self.newDB()

    def add(self, slot, frequency, mode, username, location="", extension=""):
        if debug:
            print("add DB:", username, frequency, geo, mode)
        conhash = str(uuid.uuid4())[:8]

        self.cursor.execute("SELECT counter FROM qrgstat WHERE frequency = ?", (str(frequency),))
        data = self.cursor.fetchone()
        if data is None:
            self.conn.execute("INSERT INTO qrgstat (frequency, mode, counter) VALUES (?, ?, 1)",
                              (str(frequency), str(mode)))
        else:
            print("|----> adding to", frequency)
            self.conn.execute("UPDATE qrgstat SET counter = counter +1 WHERE frequency = ?", (str(frequency),))

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
        self.cursor.execute("SELECT frequency || ' ' || upper(mode), counter FROM qrgstat LIMIT 15")
        data = self.cursor.fetchall()
        return dict(data)

    def readUserData(self):
        self.cursor.execute("SELECT user, counter FROM userstat")
        data = self.cursor.fetchall()
        return dict(data)

    def newDB(self):
        self.conn.execute("CREATE TABLE IF NOT EXISTS qrgstat (frequency TEXT(5), mode TEXT(5), counter INTEGER(12))")
        self.conn.execute("CREATE TABLE IF NOT EXISTS userstat (user TEXT(15), geo TEXT(40), extension TEXT(10), counter INTEGER(12))")


def get_json(url):
    r = requests.get(url=url)
    return r


def create_cloud(filename, qrgs):
    # colormaps from matplotlib: ['viridis', 'plasma', 'inferno', 'magma', 'cividis'])
    cloud = WordCloud(width=860, height=300, background_color="white", colormap='plasma').generate_from_frequencies(dict(qrgs))
    cloud.to_file(filename)


sqlitepath = pathlib.Path(filename)

database = db(sqlitepath)

while 1:
    now = datetime.datetime.now()
    print("|--->", now.strftime("%H:%M:%S"))

    jdata = get_json(kiwiserverurl)
    cont = json.loads(jdata.content.decode())
    for item in cont:
        counter += 1
        if not item.get('f') is None:
            # slot is in use
            username = item.get('n')
            if username == "":
                username = "unknown"
            printqrg = int(item.get('f')/1000)
            print("Slot", item.get('i'), "on", printqrg, "in use by", item.get('n') )
            #print("{:10.4f}".format(x))
            if item.get('n') in ident_skimmer and len(item.get('n')) >0:
                inuse_skimmer += 1
                if debug:
                    print("SKIMMER")
                    print(item.get('n'))
            else:
                inuse_human += 1
                frequency = int(item.get('f') / 1000)
                geo = item.get('g')
                geo = urllib.parse.unquote(geo)
                mode = item.get('m').lower()
                extension = item.get('e').lower()
                slot = item.get('i')

                # todo: blacklist initialfrequency shouldnt be fixed 6160!
                if not username in ident_blacklist and not frequency in frequency_blacklist:
                    if extension in extension_modes and len(extension) > 0:
                        if debug:
                            print("swapped mode ", mode, "for", extension)
                        mode = extension.upper()

                    conhash = database.add(slot, frequency, mode, username=username, location=geo, extension=extension)
                else:
                    if debug:
                        print(username," / ", frequency," prevented due blacklist")
        else:
            print("Slot", item.get('i'), "is idle")
            inuse_idle += 1

    qrgdata = database.readQrgFrequency()
    userdata = database.readUserData()

    if qrgdata:
        create_cloud("qrgcloud.png", qrgdata)
    if userdata:
        create_cloud("usercloud.png", userdata)

    time.sleep(30)
