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
ident_skimmer = "digiskr_0.35.1"
ident_myself = "dg7lan"

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

    def add(self, slot, frequency, mode, username, usertype, location="", extension=""):
        print(username, frequency, geo, mode)
        conhash = str(uuid.uuid4())[:8]

        self.cursor.execute("SELECT counter FROM qrgstat WHERE frequency = ?", (str(frequency),))
        data = self.cursor.fetchone()
        if data is None:
            self.conn.execute("INSERT INTO qrgstat (frequency, mode, counter) VALUES (?, ?, 1)", (str(frequency),str(mode)))
        else:
            print("adding")
            self.conn.execute("UPDATE qrgstat SET counter = counter +1 WHERE frequency = ?", (str(frequency),))

        self.conn.commit()

        self.cursor.execute("SELECT counter FROM userstat WHERE user = ?", (str(username),))
        data = self.cursor.fetchone()
        if not username == "unknown":
            if data is None:
                self.conn.execute("INSERT INTO userstat (user, counter) VALUES (?, 1)", (str(username),))
            else:
                self.conn.execute("UPDATE userstat SET counter = counter +1 WHERE user = ?", (str(username),))

            self.conn.commit()
        return conhash


    def readQrgFrequency(self):
        self.cursor.execute("SELECT frequency, counter FROM qrgstat")
        data = self.cursor.fetchall()
        return dict(data)

    def readUserData(self):
        self.cursor.execute("SELECT user, counter FROM userstat")
        data = self.cursor.fetchall()
        return dict(data)


    def newDB(self):
        self.conn.execute("CREATE TABLE IF NOT EXISTS qrgstat (frequency TEXT(5), mode TEXT(5), counter INTEGER(12))")
        self.conn.execute("CREATE TABLE IF NOT EXISTS userstat (user TEXT(15), counter INTEGER(12))")



def get_json(url):
    r = requests.get(url=url)
    return r

def create_cloud(filename, qrgs):
    cloud = WordCloud(width=860, height=300, background_color="white").generate_from_frequencies(dict(qrgs))
    cloud.to_file(filename)

sqlitepath = pathlib.Path(filename)

database = db(sqlitepath)

while (1):
    now = datetime.datetime.now()
    print("----->", now.strftime("%H:%M:%S"))

    jdata = get_json(kiwiserverurl)
    cont = json.loads(jdata.content.decode())
    for item in cont:
        counter += 1
        if not item.get('f') == None:
            # slot is in use
            print("Slot ",item.get('i'), " in use by ", item.get('n'))
            if item.get('n') == ident_skimmer:
                inuse_skimmer += 1
            else:
                inuse_human += 1
                username = item.get('n')
                if username == "":
                    username = "unknown"
                frequency = int(item.get('f')/1000)
                geo = item.get('g')
                geo = urllib.parse.unquote(geo)
                mode = item.get('m')
                extension = item.get('e')
                slot = item.get('i')

                # todo: blacklist initialfrequency shouldnt be fixed 6160!
                if not username == ident_myself and not frequency == 6160:
                    conhash = database.add(slot, frequency, mode, username, geo, extension)
        else:
            print("Slot ", item.get('i'), "is idle")
            inuse_idle += 1

    qrgdata = database.readQrgFrequency()
    userdata = database.readUserData()


    if qrgdata:
        create_cloud("qrgcloud.png", qrgdata)
    if userdata:
        create_cloud("usercloud.png", userdata)

    time.sleep(30)




