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
        <param field="Mode2" label="ASR id" width="200px" required="false" default=""/>
        <param field="Mode3" label="ASR Mac" width="200px" required="false" default="f0:fe:6b:eb:2e:7d"/>
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
    index = 0
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
            Domoticz.Device(Name="Connexion", Unit=1, TypeName = "Selector Switch",Switchtype = 2, Used =1).Create()
            devicecreated.append(deviceparam(1, 0, ""))  # default is Off
        if 2 not in Devices:
            Domoticz.Device(Name="On/Off", Unit=2, TypeName="Switch", Image=9, Used=1).Create()
            devicecreated.append(deviceparam(2, 0, ""))  # default is Off
        if 3 not in Devices:
            Options = {"LevelActions":"||",
                       "LevelNames":"Off|Auto|Cool|Heat|Dry|Fan",
                       "LevelOffHidden":"true",
                       "SelectorStyle":"0"}
            Domoticz.Device(Name = "Mode",Unit=3,TypeName = "Selector Switch",Switchtype = 18,Image = 15,
                            Options = Options,Used = 1).Create()
            devicecreated.append(deviceparam(3,0,"30"))  # default is Heating mode
        if 4 not in Devices:
            Options = {"LevelActions":"||",
                       "LevelNames":"Off|Auto|Low|Mid|High",
                       "LevelOffHidden":"true",
                       "SelectorStyle":"0"}
            Domoticz.Device(Name = "Fan",Unit=4,TypeName = "Selector Switch",Switchtype = 18,Image = 15,
                            Options = Options,Used = 1).Create()
            devicecreated.append(deviceparam(4,0,"10"))  # default is Auto mode
        if 5 not in Devices:
            Domoticz.Device(Name = "Setpoint",Unit=5,Type = 242,Subtype = 1,Used = 1).Create()
            devicecreated.append(deviceparam(5,0,"21"))  # default is 21 degrees

        # if any device has been created in onStart(), now is time to update its defaults
        for device in devicecreated:
            Devices[device.unit].Update(nValue = device.nvalue,sValue = device.svalue)

        self.httpConnControlInfo = Domoticz.Connection(Name = "Control Info",Transport = "TCP/IP",Protocol = "HTTP",
                                                      Address = Parameters["Mode1"],Port = "80")
        self.httpConnControlInfo.Connect()

        self.httpConnSetControl = Domoticz.Connection(Name = "Set Control",Transport = "TCP/IP",Protocol = "HTTP",
                                                      Address = Parameters["Mode1"],Port = "80")

    def onStop(self):
        Domoticz.Debugging(0)

    def onConnect(self,Connection,Status,Description):
        if (Status == 0):
            Domoticz.Debug("Connection successful")

            data = ''
            headers = {'Content-Type':'text/xml; charset=utf-8', \
                       'Connection':'keep-alive', \
                       'Accept':'Content-Type: text/html; charset=UTF-8', \
                       'Host':Parameters["Mode1"] + ":80", \
                       'User-Agent':'Domoticz/1.0'}

            if (Connection == self.httpConnControlInfo):
                Domoticz.Debug("Control connection created")
                requestUrl = "/api_chunghopserver?status=minify"
                Connection.Send({"Verb":"GET","URL":requestUrl,"Headers":headers})
            elif (Connection == self.httpConnSetControl):
                Domoticz.Debug("Set connection created")
                requestUrl = self.buildCommandString()
                Connection.Send({"Verb":"POST","URL":requestUrl,"Headers":headers})
        else:
            Domoticz.Debug("Connection failed")

    def onMessage(self,Connection,Data):
        Domoticz.Log("onMessage called")

        dataDecoded = Data["Data"].decode("utf-8","ignore")

        Domoticz.Debug("Received data from connection " + Connection.Name + ": " + dataDecoded)

        if (Connection == self.httpConnControlInfo):

            position = dataDecoded.find(Parameters["Mode3"])
            id = dataDecoded[position - 65: position - 64]

            position = dataDecoded.find(Parameters["Mode3"])
            connex = dataDecoded[position - 45: position - 44]

            position = dataDecoded.find("MACAddress")
            mac = dataDecoded[position + 13: position + 30]

            position = dataDecoded.find("OnOff")
            onoff = dataDecoded[position + 8: position + 10]

            position = dataDecoded.find("Mode")
            mode = dataDecoded[position + 7: position + 10]

            position = dataDecoded.find("FanSpeed")
            fanspeed = dataDecoded[position + 11: position + 14]

            position = dataDecoded.find("Temperature")
            stemp = dataDecoded[position + 13: position + 16]

            Domoticz.Debug(
                "mac: " + mac + ";Index: " + id + ";connex:" + connex)
            Domoticz.Debug(
                "Power: " + onoff + "; Mode: " + mode + "; FanSpeed: " + fanspeed + "; AC Set temp: " + stemp)

            # Server SR index
            self.index = int(id)

            # SR connexion
            if (connex == "0"):
                Devices[1].Update(nValue = 0,sValue = "0")
                Devices[2].Update(nValue = 0,sValue = "0")
                Devices[3].Update(nValue = 0,sValue = "0")
                Devices[4].Update(nValue = 0,sValue = "0")
            else:
                Devices[1].Update(nValue = 1,sValue = "100")

                # Power
                if (onoff == "ON"):
                    self.powerOn = 1
                    sValueNew = "100"  # on
                else:
                    self.powerOn = 0
                    sValueNew = "0"  # off

                if (Devices[2].nValue != self.powerOn or Devices[2].sValue != sValueNew):
                    Devices[2].Update(nValue = self.powerOn,sValue = sValueNew)

                # Mode
                if (mode == "AUT"):
                   sValueNew = "10"  # Auto
                elif (mode == "COO"):
                   sValueNew = "20"  # Cool
                elif (mode == "HEA"):
                   sValueNew = "30"  # Heat
                elif (mode == "DRY"):
                   sValueNew = "40"  # Dry
                elif (mode == "FAN"):
                   sValueNew = "50"  # Fan

                if (Devices[3].nValue != self.powerOn or Devices[3].sValue != sValueNew):
                   Devices[3].Update(nValue = self.powerOn,sValue = sValueNew)

                # fanspeed
                if (fanspeed == "AUT"):
                   sValueNew = "10"  # Auto
                elif (fanspeed == "LOW"):
                   sValueNew = "20"  # Low
                elif (fanspeed == "MID"):
                   sValueNew = "30"  # Low
                elif (fanspeed == "HIG"):
                   sValueNew = "40"  # Low

                if (Devices[4].nValue != self.powerOn or Devices[4].sValue != sValueNew):
                    Devices[4].Update(nValue = self.powerOn,sValue = sValueNew)

                Devices[5].Update(nValue = 0,sValue = stemp)

        # Force disconnect, in case the ASR unit doesn't disconnect
        if (Connection.Connected()):
           Domoticz.Debug("Close connection")
           Connection.Disconnect()

    def onCommand(self,Unit,Command,Level,Color):
        Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

        if (Unit == 2):
            if (Command == "On"):
                self.powerOn = 1
                Devices[2].Update(nValue = 1,sValue = "100")
            else:
                self.powerOn = 0
                Devices[2].Update(nValue = 0,sValue = "0")

                # Update state of all other devices
            Devices[3].Update(nValue = self.powerOn,sValue = Devices[3].sValue)
            Devices[4].Update(nValue = self.powerOn,sValue = Devices[4].sValue)
            Devices[5].Update(nValue = self.powerOn,sValue = Devices[5].sValue)

        if (Unit == 3):
            Devices[3].Update(nValue = self.powerOn,sValue = str(Level))

        if (Unit == 4):
            Devices[4].Update(nValue = self.powerOn,sValue = str(Level))

        if (Unit == 5):
            Devices[5].Update(nValue = self.powerOn,sValue = str(Level))

        self.httpConnSetControl.Connect()

    def onDisconnect(self,Connection):
        Domoticz.Debug("Connection " + Connection.Name + " closed.")

    def onHeartbeat(self):

        # fool proof checking.... based on users feedback
        if not all(device in Devices for device in (1, 2, 3 ,4 , 5)):
            Domoticz.Error(
                "one or more devices required by the plugin is/are missing, please check domoticz device creation settings and restart !")
            return

        self.httpConnControlInfo.Connect()

    def WriteLog(self, message, level="Normal"):

        if self.loglevel == "Verbose" and level == "Verbose":
            Domoticz.Log(message)
        elif level == "Normal":
            Domoticz.Log(message)

    def buildCommandString(self):
        # Minimal string: pow=1&mode=1&stemp=26&shum=0&f_rate=B&f_dir=3

        requestUrl = "/api_chunghopserver?action=changeconfig&remote=" + self.index +"&onoff="

        if (self.powerOn):
            requestUrl = requestUrl + "ON"
        else:
            requestUrl = requestUrl + "0FF"

        requestUrl = requestUrl + "&mode="

        if (Devices[3].sValue == "0"):
            requestUrl = requestUrl + "AUTO"
        elif (Devices[3].sValue == "10"):
            requestUrl = requestUrl + "AUTO"
        elif (Devices[3].sValue == "20"):
            requestUrl = requestUrl + "COOL"
        elif (Devices[3].sValue == "30"):
            requestUrl = requestUrl + "HEAT"
        elif (Devices[3].sValue == "40"):
            requestUrl = requestUrl + "DRY"
        elif (Devices[3].sValue == "50"):
            requestUrl = requestUrl + "FAN"

        requestUrl = requestUrl + "&fanspeed="

        if (Devices[4].sValue == "0"):
            requestUrl = requestUrl + "AUTO"
        elif (Devices[4].sValue == "10"):
            requestUrl = requestUrl + "AUTO"
        elif (Devices[4].sValue == "20"):
            requestUrl = requestUrl + "LOW"
        elif (Devices[4].sValue == "30"):
            requestUrl = requestUrl + "MID"
        elif (Devices[4].sValue == "40"):
            requestUrl = requestUrl + "HIGH"

        requestUrl = requestUrl + "&temperature="

        if (Devices[5].sValue < "16"):  # Set temp Lower than range
            Domoticz.Log("Set temp is lower than authorized range !")
            requestUrl = requestUrl + "16"
        elif (Devices[5].sValue > "30"):  # Set temp Lower than range
            Domoticz.Log("Set temp is upper than authorized range !")
            requestUrl = requestUrl + "30"
        else:
            requestUrl = requestUrl + Devices[5].sValue

        return requestUrl

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

def onMessage(Connection,Data):
    global _plugin
    _plugin.onMessage(Connection,Data)

def onCommand(Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Color)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def buildCommandString():
    global _plugin
    _plugin.buildCommandString()


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
