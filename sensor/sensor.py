import grovepi
import os
import time
import threading
from datetime import datetime
from influxdb import InfluxDBClient

NEXT_CALL = None

class DHTSensor():
    port = None
    type = None

    def __init__(self, port=4, type=1):
        """

        port: digital port
        type: 0 - blue, 1 - white sensor
        """
        self.port = port
        self.type = type

    def getReading(self):
        try:
            [temp, humidity] = grovepi.dht(self.port, self.type)
            if math.isnan(temp) == False and math.isnan(humidity) == False:
                return { "temperature": temp, "humidity": humidity, "error": None}
            else:
                return { "error": "ValueError" }
        except IOError:
            return { "error": "IOError" }

class Database():
    client = None
    database = None

    def __init__(self, hostname="localhost", port=8086, username="root", password="root", database=None):
        self.client = InfluxDBClient(hostname, port, username, password, database)
        self.database = database

    def setDatabase(self, database):
        self.database = database;

    def writeTo(self, points=[], database=None, tags=None):
        if not database:
            database = self.database
        self.client.create_database(database)
        self.client.write_points(points, database=database, tags=tags)
        # Need to handle errors here: influxdb.exceptions.InfluxDBClientError


def readAndSubmit(sensor, database, interval, tags):
    reading = sensor.getReading()
    if not reading['error']:
        readingtime = datetime.utcnow().isoformat()
        data = [{
            "measurement": "temperature",
            "time": readingtime,
            "fields": {
                "value": reading['temperature']
            }
        }, {
            "measurement": "humidity",
            "time": readingtime,
            "fields": {
                "value": reading['humidity']
            }
        }]
        database.writeTo(points=data, tags=tags)
    else:
        print("Error reading sensor: {}".format(reading['error']))

    global NEXT_CALL
    if not NEXT_CALL:
        NEXT_CALL = datetime.datetime.now() + interval
    else:
        NEXT_CALL = NEXT_CALL + interval
    threading.Timer( NEXT_CALL - time.time(), readAndSubmit, {"sensor": sensor, "database": database, "interval": interval, "tags": tags} ).start()


if __name__ == "__main__":
    host = os.getenv('RESIN_DEVICE_UUID')
    if not host:
        print("Need 'RESIN_DEVICE_UUID' to set hostname")

    influxdb_host = os.getenv('INFLUXDB_HOST')
    if not influxdb_host:
        print("Need 'INFLUXDB_HOST' to set database to connect to")
    try:
        influxdb_port = int(os.getenv('INFLUXDB_PORT', default="8086"))
    except TypeError:
        influxdb_port = 8086
    except ValueError:
        print("Value of 'INFLUXDB_PORT' is incorrect, not a number?")

    database_name = os.getenv('DATABASE_NAME', default="environment")

    tags = { "host": os.environ['RESIN_DEVICE_UUID'], 'sensor': 'grove_dht_pro'}
    location = os.getenv('LOCATION')
    if location:
        tags['location'] = location
    fine_location = os.getenv('FINE_LOCATION')
    if fine_location:
        tags['fine_location'] = fine_location
    database = Database(hostname=nfluxdb_host, port=influxdb_port, database=database)
    sensor = DHTSensor(4, 1);
    interval = int(os.getenv("INTERVAL", default="5"))

    readAndSubmit(sensor=sensor, database=database, interval=interval, tags=tags)
