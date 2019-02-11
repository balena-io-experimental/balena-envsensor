import grovepi
import os
import sys
import time
from datetime import datetime, timedelta
from influxdb import InfluxDBClient
import math
import smbus
import RPi.GPIO as GPIO
#import grovepi
from grove_i2c_barometic_sensor_BMP180 import BMP085
import logging
logging.basicConfig()

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

class AirSensor():
    pin = 0

    def __init__(self, pin=0):
        self.pin = pin
        grovepi.pinMode(self.pin,"INPUT")

    def getReading(self):
        try:
            sensor_value = grovepi.analogRead(self.pin)
            return sensor_value
        except IOError:
            return -1

class BarometricSensor():
    sensor = None

    def __init__(self, address=0x77, mode=3):
        self.sensor = BMP085(address, mode)

    def getReading(self):
        temp = self.sensor.readTemperature()
        pressure = self.sensor.readPressure()
        return {"temperature": temp, "pressure": pressure}


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


def readAndSubmit(sensor, airsensor, barosensor, database, interval, tags):

    logger.info("reading starts")

    data = []

    try:
        if os.getenv('SENSOR_DHT22', default="true") != "false":
            readingtime = datetime.utcnow().isoformat()
            reading = sensor.getReading()
            logger.debug(reading)
            if not reading['error']:
                if reading['humidity'] > 0:

                    data.append({
                        "measurement": "temperature",
                        "time": readingtime,
                        "tags": {
                            'sensor': 'DHT22'
                        },
                        "fields": {
                            "value": reading['temperature']
                        }
                    })
                    data.append({
                        "measurement": "humidity",
                        "time": readingtime,
                        "tags": {
                            'sensor': 'DHT22'
                        },
                        "fields": {
                            "value": reading['humidity']
                        }
                    })
        else:
            logger.error("Error reading sensor: {}".format(reading['error']))
    except:
        logger.error("Couldn't read DHT sensor: ", sys.exc_info()[0])

    try:
        if os.getenv('SENSOR_AIRQUALITY', default="true") != "false":
            readingtime = datetime.utcnow().isoformat()
            air_reading = airsensor.getReading()
            if air_reading >0:
                data.append({
                    "measurement": "air_quality",
                    "time": readingtime,
                    "tags": {
                        'sensor': 'Grove Air Quality v1.3'
                    },
                    "fields": {
                        "value": air_reading
                    }
                })
    except:
        logger.error("Couldn't read Air sensor: ", sys.exc_info()[0])

    try:
        if os.getenv('SENSOR_BMP180', default="true") != "false":
            readingtime = datetime.utcnow().isoformat()
            baro_reading = barosensor.getReading()
            data.append({
                "measurement": "temperature",
                "time": readingtime,
                "tags": {
                    'sensor': 'BMP180'
                },
                "fields": {
                    "value": baro_reading['temperature']
                }
            })
            data.append({
                "measurement": "pressure",
                "time": readingtime,
                "tags": {
                    'sensor': 'BMP180'
                },
                "fields": {
                    "value": baro_reading['pressure']
                }
            })
    except:
        logger.error("Couldn't read barometric sensor: ", sys.exc_info()[0])

    if len(data) > 0:
        try:
            logger.debug(data)
            database.writeTo(points=data, tags=tags)
        except:
            logger.error("Couldn't write to database: ", sys.exc_info()[0])
    else:
        logger.debug("No data to write to the database")


if __name__ == "__main__":
    logger = logging.getLogger('sensor')
    if os.getenv('DEBUG', default=None):
        logger.setLevel(logging.DEBUG)

    host = os.getenv('RESIN_DEVICE_UUID')
    if not host:
        logger.error("Need 'RESIN_DEVICE_UUID' to set hostname")

    influxdb_host = os.getenv('INFLUXDB_HOST')
    if not influxdb_host:
        logger.error("Need 'INFLUXDB_HOST' to set database to connect to")
    try:
        influxdb_port = int(os.getenv('INFLUXDB_PORT', default="8086"))
    except TypeError:
        influxdb_port = 8086
    except ValueError:
        logger.error("Value of 'INFLUXDB_PORT' is incorrect, not a number?")

    database_name = os.getenv('DATABASE_NAME', default="environment")

    tags = { "host": os.environ['RESIN_DEVICE_UUID'] }
    location = os.getenv('LOCATION')
    if location:
        tags['location'] = location
    fine_location = os.getenv('FINE_LOCATION')
    if fine_location:
        tags['fine_location'] = fine_location
    database = Database(hostname=influxdb_host, port=influxdb_port, database=database_name)
    if os.getenv('SENSOR_DHT22', default="true") != "false":
        sensor = DHTSensor(4, 1)
    else:
        sensor = None
    if os.getenv('SENSOR_AIRQUALITY', default="true") != "false":
        airsensor = AirSensor(0)
    else:
        airsensor = None
    if os.getenv('SENSOR_BMP180', default="true") != "false":
        barosensor = BarometricSensor()
    else:
        barosensor = None
    interval = int(os.getenv("INTERVAL", default="5"))
    logger.debug("Measurement interval: {}s".format(interval))

    triggertime = time.monotonic()
    while True:
        triggertime = triggertime + interval
        readAndSubmit(sensor=sensor, airsensor=airsensor, barosensor=barosensor, database=database, interval=interval, tags=tags)
        sleeptime = triggertime - time.monotonic()
        if sleeptime > 0:
            time.sleep(sleeptime)
        else:
            # set up the reference again
            triggertime = time.monotonic()
