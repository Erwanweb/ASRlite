"""
Aircon Smart Remote plugin for Domoticz
Author: Erwanweb,
        adapted from the SVT plugin by Logread, see :
        https://github.com/999LV/SmartVirtualThermostat
Version:    0.0.1: alpha
"""
"""
<plugin key="ASRlite" name="AC Aircon Smart Remote" author="MrErwan" version="0.0.1" externallink="https://github.com/Erwanweb/ASRlite.git">
    <description>
        <h2>Aircon Smart Remote</h2><br/>
        Easily implement in Domoticz an full control of air conditoner controled IR Remote using AC Smart remote<br/>
        <h3>Set-up and Configuration</h3>
    </description>
    <params>
        <param field="Address" label="Domoticz IP Address" width="200px" required="true" default="127.0.0.1"/>
        <param field="Port" label="Port" width="40px" required="true" default="8080"/>
        <param field="Username" label="Username" width="200px" required="false" default=""/>
        <param field="Password" label="Password" width="200px" required="false" default=""/>
        <param field="Mode1" label="ASR server IP Address" width="200px" required="true" default=""/>
        <param field="Mode2" label="ASR Index" width="40px" required="true" default=""/>
        <param field="Mode6" label="Logging Level" width="200px">
            <options>
                <option label="Normal" value="Normal"  default="true"/>
                <option label="Verbose" value="Verbose"/>
                <option label="Debug - Python Only" value="2"/>
                <option label="Debug - Basic" value="62"/>
                <option label="Debug - Basic+Messages" value="126"/>
                <option label="Debug - Connections Only" value="16"/>
                <option label="Debug - Connections+Queue" value="144"/>
                <option label="Debug - All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz
import json
import urllib
import urllib.parse as parse
import urllib.request as request
from datetime import datetime, timedelta
import time
import base64
import itertools


class deviceparam:

    def __init__(self,unit,nvalue,svalue):
        self.unit = unit
        self.nvalue = nvalue
        self.svalue = svalue


class BasePlugin:
    enabled = True
    powerOn = 0
    runCounter = 0
    httpConnSensorInfo = None
    httpConnControlInfo = None
    httpConnSetControl = None

    def __init__(self):
        self.debug = False
        return

    def onStart(self):

        # setup the appropriate logging level
        try:
            debuglevel = int(Parameters["Mode6"])
        except ValueError:
            debuglevel = 0
            self.loglevel = Parameters["Mode6"]
        if debuglevel != 0:
            self.debug = True
            Domoticz.Debugging(debuglevel)
            DumpConfigToLog()
            self.loglevel = "Verbose"
        else:
            self.debug = False
            Domoticz.Debugging(0)

        # create the child devices if these do not exist yet
        devicecreated = []
        if 1 not in Devices:
            Options = {"LevelActions":"||",
                       "LevelNames":"Off|Auto|Cool|Heat|Dry|Fan",
                       "LevelOffHidden":"false",
                       "SelectorStyle":"0"}
            Domoticz.Device(Name = "Mode",Unit = 1,TypeName = "Selector Switch",Switchtype = 18,Image = 15,
                            Options = Options,Used = 1).Create()
            devicecreated.append(deviceparam(1,0,"0"))  # default is Off state
        if 2 not in Devices:
            Options = {"LevelActions":"||",
                       "LevelNames":"Off|Auto|Low|Mid|High",
                       "LevelOffHidden":"true",
                       "SelectorStyle":"0"}
            Domoticz.Device(Name = "Fan",Unit = 2,TypeName = "Selector Switch",Switchtype = 18,Image = 15,
                            Options = Options,Used = 1).Create()
            devicecreated.append(deviceparam(2,0,"10"))  # default is Auto mode
        if 3 not in Devices:
            Domoticz.Device(Name = "Setpoint",Unit = 3,Type = 242,Subtype = 1,Used = 1).Create()
            devicecreated.append(deviceparam(3,0,"21"))  # default is 21 degrees

        # if any device has been created in onStart(), now is time to update its defaults
        for device in devicecreated:
            Devices[device.unit].Update(nValue = device.nvalue,sValue = device.svalue)

        self.httpConn = Domoticz.Connection(Name = "Set Control",Transport = "TCP/IP",Protocol = "HTTP",
                                                      Address = Parameters["Mode1"],Port = "80")
        self.httpConn.Connect()

    def onStop(self):
        Domoticz.Debugging(0)

    def onConnect(self,Connection,Status,Description):
        if (Status == 0):
            Domoticz.Debug("ASR Server connected successfully.")
            sendData = {'Verb':'GET',
                        'URL':'/',
                        'Headers':{'Content-Type':'text/xml; charset=utf-8', \
                                   'Connection':'keep-alive', \
                                   'Accept':'Content-Type: text/html; charset=UTF-8', \
                                   'Host':Parameters["Mode1"] + "/api_chunghopserver?status=full:80", \
                                   'User-Agent':'Domoticz/1.0'}
                        }
            Connection.Send(sendData)
        else:
            Domoticz.Log("Failed to connect (" + str(Status) + ") to: " + Parameters["Address"] + ":" + Parameters[
                "Mode1"] + " with error: " + Description)

    def onCommand(self,Unit,Command,Level,Color):
        Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

        if Unit == 1:  # Aircon Mode
            if Command == 'Off':
               Domoticz.Log("Aircon is Off !")
            elif Command == 'Set Level':
                if Level == 10: # Aircon Mode is AUTO
                    Domoticz.Log("Aircon is in Auto Mode !")
                if Level == 20: # Aircon Mode is COOL
                    Domoticz.Log("Aircon is in Cooling Mode !")
                if Level == 30: # Aircon Mode is HEAT
                    Domoticz.Log("Aircon is in Heating Mode !")
                if Level == 40: # Aircon Mode is DRY
                    Domoticz.Log("Aircon is in Dry Mode !")
                if Level == 50: # Aircon Mode is FAN
                    Domoticz.Log("Aircon is in Fan Mode !")

        if Unit == 2:  # Fan Mode
            if Command == 'Set Level':
                if Level == 10: # Fan Mode is AUTO
                    Domoticz.Log("Fan is Auto !")
                if Level == 20: # Aircon Mode is LOW
                    Domoticz.Log("Fan is Low !")
                if Level == 30: # Aircon Mode is MID
                    Domoticz.Log("Fan is Mid !")
                if Level == 40: # Aircon Mode is HIGH
                    Domoticz.Log("Fan is high !")

        if Unit == 3:  # Set Temp
            if Command == 'Set Level':
                if Level < 16: # Set temp Lower than range
                    Domoticz.Log("Set temp is lower than authorized range !")
                if Level > 30: # Set temp Lower than range
                    Domoticz.Log("Set temp is upper than authorized range !")
                else:
                    Domoticz.Log("temp setted !")

    def onHeartbeat(self):

        # fool proof checking.... based on users feedback
        if not all(device in Devices for device in (1,2,3)):
            Domoticz.Error(
                "one or more devices required by the plugin is/are missing, please check domoticz device creation settings and restart !")
            return

        if Devices[1].sValue == "0":  # Aircon is off
            Domoticz.Log("Aircon is Off when onheartbeat !")

        if (self.httpConn != None and (self.httpConn.Connecting() or self.httpConn.Connected())):
            Domoticz.Debug("onHeartbeat called, Connection is alive.")
        else:
            self.runAgain = self.runAgain - 1
            if self.runAgain <= 0:
                if (self.httpConn == None):
                    self.httpConn = Domoticz.Connection(Name = "Set Control",Transport = "TCP/IP",Protocol = "HTTP",
                                                      Address = Parameters["Mode1"],Port = "80")
                self.httpConn.Connect()
                self.runAgain = 6
            else:
                Domoticz.Debug("onHeartbeat called, run again in " + str(self.runAgain) + " heartbeats.")

    def WriteLog(self, message, level="Normal"):

        if self.loglevel == "Verbose" and level == "Verbose":
            Domoticz.Log(message)
        elif level == "Normal":
            Domoticz.Log(message)

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection,Status,Description):
    global _plugin
    _plugin.onConnect(Connection,Status,Description)

def onCommand(Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Color)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


# Plugin utility functions ---------------------------------------------------

def parseCSV(strCSV):

    listvals = []
    for value in strCSV.split(","):
        try:
            val = int(value)
        except:
            pass
        else:
            listvals.append(val)
    return listvals


def DomoticzAPI(APICall):

    resultJson = None
    url = "http://{}:{}/json.htm?{}".format(Parameters["Address"], Parameters["Port"], parse.quote(APICall, safe="&="))
    Domoticz.Debug("Calling domoticz API: {}".format(url))
    try:
        req = request.Request(url)
        if Parameters["Username"] != "":
            Domoticz.Debug("Add authentification for user {}".format(Parameters["Username"]))
            credentials = ('%s:%s' % (Parameters["Username"], Parameters["Password"]))
            encoded_credentials = base64.b64encode(credentials.encode('ascii'))
            req.add_header('Authorization', 'Basic %s' % encoded_credentials.decode("ascii"))

        response = request.urlopen(req)
        if response.status == 200:
            resultJson = json.loads(response.read().decode('utf-8'))
            if resultJson["status"] != "OK":
                Domoticz.Error("Domoticz API returned an error: status = {}".format(resultJson["status"]))
                resultJson = None
        else:
            Domoticz.Error("Domoticz API: http error = {}".format(response.status))
    except:
        Domoticz.Error("Error calling '{}'".format(url))
    return resultJson


def CheckParam(name, value, default):

    try:
        param = int(value)
    except ValueError:
        param = default
        Domoticz.Error("Parameter '{}' has an invalid value of '{}' ! defaut of '{}' is instead used.".format(name, value, default))
    return param


# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return
