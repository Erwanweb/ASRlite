"""
AC Aircon Smart Remote plugin for Domoticz
Author: MrErwan,
Version:    0.0.1: alpha
"""
"""
<plugin key="AC-ASRlite" name="AC Aircon Smart Remote LITE" author="MrErwan" version="0.0.1" externallink="https://github.com/Erwanweb/ASRlite.git">
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
        <param field="Mode2" label="ASR Mac" width="200px" required="true" default=""/>
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
#uniquement pour les besoins de cette appli
import getopt, sys
#pour lire le json
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
        self.debug = False




class BasePlugin:
    enabled = True
    powerOn = 0
    SRindex = 1
    runCounter = 0
    httpConnSensorInfo = None
    httpConnControlInfo = None
    httpConnSetControl = None

    def __init__(self):
        self.debug = False
        return

    def onStart(self):
        Domoticz.Log("onStart called")
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
            Domoticz.Device(Name = "ASR Index",Unit=2,Type = 243,Subtype = 6,).Create()
            devicecreated.append(deviceparam(2,0,"1"))  # default is Index 1
        if 3 not in Devices:
            Domoticz.Device(Name="On/Off", Unit=3, TypeName="Switch", Image=9, Used=1).Create()
            devicecreated.append(deviceparam(3, 0, ""))  # default is Off
        if 4 not in Devices:
            Options = {"LevelActions":"||",
                       "LevelNames":"Off|Auto|Cool|Heat|Dry|Fan",
                       "LevelOffHidden":"true",
                       "SelectorStyle":"0"}
            Domoticz.Device(Name = "Mode",Unit=4,TypeName = "Selector Switch",Switchtype = 18,Image = 15,
                            Options = Options,Used = 1).Create()
            devicecreated.append(deviceparam(4,0,"30"))  # default is Heating mode
        if 5 not in Devices:
            Options = {"LevelActions":"||",
                       "LevelNames":"Off|Auto|Low|Mid|High",
                       "LevelOffHidden":"true",
                       "SelectorStyle":"0"}
            Domoticz.Device(Name = "Fan",Unit=5,TypeName = "Selector Switch",Switchtype = 18,Image = 15,
                            Options = Options,Used = 1).Create()
            devicecreated.append(deviceparam(5,0,"10"))  # default is Auto mode
        if 6 not in Devices:
            Domoticz.Device(Name = "Setpoint",Unit=6,Type = 242,Subtype = 1,Used = 1).Create()
            devicecreated.append(deviceparam(6,0,"21"))  # default is 21 degrees
        if 7 not in Devices:
            Options = {"LevelActions":"||",
                       "LevelNames":"Off|Auto",
                       "LevelOffHidden":"false",
                       "SelectorStyle":"0"}
            Domoticz.Device(Name = "Wind direction (swing)",Unit=7,TypeName = "Selector Switch",Switchtype = 18,Image = 15,
                            Options = Options,Used = 1).Create()
            devicecreated.append(deviceparam(7,0,"0"))  # default is Off

        # if any device has been created in onStart(), now is time to update its defaults
        for device in devicecreated:
            Devices[device.unit].Update(nValue = device.nvalue,sValue = device.svalue)

        self.httpConnControlInfo = Domoticz.Connection(Name = "Control Info",Transport = "TCP/IP",Protocol = "HTTP",
                                                      Address = Parameters["Mode1"],Port = "80")
        self.httpConnControlInfo.Connect()

        self.httpConnSetControl = Domoticz.Connection(Name = "Set Control",Transport = "TCP/IP",Protocol = "HTTP",
                                                      Address = Parameters["Mode1"],Port = "80")

    def onStop(self):
        Domoticz.Log("onStop called")
        Domoticz.Debugging(0)

    def onConnect(self,Connection,Status,Description):
        Domoticz.Log("onMConnect called")
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
        # on lit Data comme du json

        jsonStatus = json.loads(dataDecoded)

        # Domoticz.Debug("Received data from connection " + Connection.Name + ": " + jsonStatus)

        if (Connection == self.httpConnControlInfo):

            # on met id a -1 pour valider que l'on a bien trouve la telecommande

            id = -1

            # on parcourt toute la liste des telecommandes

            for remoteObject in jsonStatus["Remotes"]:

                # on regarde si c'est la bonne adresse MAC

                if Parameters["Mode2"] == remoteObject["MACAddress"]:
                    # on releve les valeurs

                    id = remoteObject["Index"]

                    connex = remoteObject["ActiveReception"]

                    mac = remoteObject["MACAddress"]

                    onoff = remoteObject["OnOff"]

                    mode = remoteObject["Mode"]

                    fanspeed = remoteObject["FanSpeed"]

                    stemp = remoteObject["Temperature"]

                    winmode = remoteObject["WindDirection"]


            # si la telecommande est trouvee...

            if id > -1:

                Domoticz.Debug(
                    "mac: " + mac + ";Index: " + str(id) + ";connex:" + str(connex))

                Domoticz.Debug(
                    "Power: " + onoff + "; Mode: " + mode + "; FanSpeed:" + fanspeed + "; AC Set temp: " + str(stemp)+ "; Wmode: " + winmode )

            # Server SR index
            Devices[2].Update(nValue = 0,sValue = str(id))

            # SR connexion
            if (connex == 0):
                Devices[1].Update(nValue = 0,sValue = "0")
                Devices[3].Update(nValue = 0,sValue = "0")
                Devices[4].Update(nValue = 0,sValue = "0")
                Devices[5].Update(nValue = 0,sValue = "0")
                Devices[7].Update(nValue = 0,sValue = "0
            else:
                Devices[1].Update(nValue = 1,sValue = "100")

                # Power
                if (onoff == "ON"):
                    self.powerOn = 1
                    sValueNew = "100"  # on
                else:
                    self.powerOn = 0
                    sValueNew = "0"  # off

                if (Devices[3].nValue != self.powerOn or Devices[2].sValue != sValueNew):
                    Devices[3].Update(nValue = self.powerOn,sValue = sValueNew)

                # Mode
                if (mode == "AUTO"):
                   sValueNew = "10"  # Auto
                elif (mode == "COOL"):
                   sValueNew = "20"  # Cool
                elif (mode == "HEAT"):
                   sValueNew = "30"  # Heat
                elif (mode == "DRY"):
                   sValueNew = "40"  # Dry
                elif (mode == "FAN"):
                   sValueNew = "50"  # Fan

                if (Devices[4].nValue != self.powerOn or Devices[4].sValue != sValueNew):
                   Devices[4].Update(nValue = self.powerOn,sValue = sValueNew)

                # fanspeed
                if (fanspeed == "AUTO"):
                   sValueNew = "10"  # Auto
                elif (fanspeed == "LOW"):
                   sValueNew = "20"  # Low
                elif (fanspeed == "MID"):
                   sValueNew = "30"  # Low
                elif (fanspeed == "HIGH"):
                   sValueNew = "40"  # Low

                if (Devices[5].nValue != self.powerOn or Devices[5].sValue != sValueNew):
                    Devices[5].Update(nValue = self.powerOn,sValue = sValueNew)

                Devices[6].Update(nValue = 0,sValue = str(stemp))

                # wind direction auto (swing)
                if (winmode == "MANU"):
                   sValueNew = "0"  # Off
                elif (winmode == "AUTO"):
                   sValueNew = "10"  # Auto

                if (Devices[7].nValue != self.powerOn or Devices[7].sValue != sValueNew):
                    Devices[7].Update(nValue = self.powerOn,sValue = sValueNew)

        # Force disconnect, in case the ASR unit doesn't disconnect
        if (Connection.Connected()):
           Domoticz.Debug("Close connection")
           Connection.Disconnect()

    def onCommand(self,Unit,Command,Level,Color):
        Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

        if (Unit == 3):
            if (Command == "On"):
                self.powerOn = 1
                Devices[3].Update(nValue = 1,sValue = "100")
            else:
                self.powerOn = 0
                Devices[3].Update(nValue = 0,sValue = "0")

                # Update state of all other devices
            Devices[4].Update(nValue = self.powerOn,sValue = Devices[4].sValue)
            Devices[5].Update(nValue = self.powerOn,sValue = Devices[5].sValue)
            Devices[6].Update(nValue = self.powerOn,sValue = Devices[6].sValue)
            Devices[7].Update(nValue = self.powerOn,sValue = Devices[7].sValue)

        if (Unit == 4):
            Devices[4].Update(nValue = self.powerOn,sValue = str(Level))

        if (Unit == 5):
            Devices[5].Update(nValue = self.powerOn,sValue = str(Level))

        if (Unit == 6):
            Devices[6].Update(nValue = self.powerOn,sValue = str(Level))

        if (Unit == 7):
            Devices[7].Update(nValue = self.powerOn,sValue = str(Level))

        self.httpConnSetControl.Connect()

    def onDisconnect(self,Connection):
        Domoticz.Log("onDisconnect called")
        Domoticz.Debug("Connection " + Connection.Name + " closed.")

    def onHeartbeat(self):
        Domoticz.Log("onHeartbeat called")
        # fool proof checking.... based on users feedback
        if not all(device in Devices for device in (1, 2, 3 ,4 , 5, 6, 7)):
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
        Domoticz.Log("onbuildCommandString called")

        # Select good Index of the ASR from 1 to 16
        requestUrl = "/api_chunghopserver?action=changeconfig&remote="

        if (Devices[2].sValue == "1"):
           requestUrl = requestUrl + "1"
        elif (Devices[2].sValue == "2"):
           requestUrl = requestUrl + "2"
        elif (Devices[2].sValue == "3"):
           requestUrl = requestUrl + "3"
        elif (Devices[2].sValue == "4"):
           requestUrl = requestUrl + "4"
        elif (Devices[2].sValue == "5"):
           requestUrl = requestUrl + "5"
        elif (Devices[2].sValue == "6"):
           requestUrl = requestUrl + "6"
        elif (Devices[2].sValue == "7"):
           requestUrl = requestUrl + "7"
        elif (Devices[2].sValue == "8"):
           requestUrl = requestUrl + "8"
        elif (Devices[2].sValue == "9"):
           requestUrl = requestUrl + "9"
        elif (Devices[2].sValue == "10"):
           requestUrl = requestUrl + "10"
        elif (Devices[2].sValue == "11"):
           requestUrl = requestUrl + "11"
        elif (Devices[2].sValue == "12"):
           requestUrl = requestUrl + "12"
        elif (Devices[2].sValue == "13"):
           requestUrl = requestUrl + "13"
        elif (Devices[2].sValue == "14"):
           requestUrl = requestUrl + "14"
        elif (Devices[2].sValue == "15"):
           requestUrl = requestUrl + "15"
        elif (Devices[2].sValue == "16"):
           requestUrl = requestUrl + "16"

        # Set power
        requestUrl = requestUrl + "&onoff="

        if (self.powerOn):
            requestUrl = requestUrl + "ON"
        else:
            requestUrl = requestUrl + "0FF"

        # Set mode
        requestUrl = requestUrl + "&mode="

        if (Devices[4].sValue == "0"):
            requestUrl = requestUrl + "AUTO"
        elif (Devices[4].sValue == "10"):
            requestUrl = requestUrl + "AUTO"
        elif (Devices[4].sValue == "20"):
            requestUrl = requestUrl + "COOL"
        elif (Devices[4].sValue == "30"):
            requestUrl = requestUrl + "HEAT"
        elif (Devices[4].sValue == "40"):
            requestUrl = requestUrl + "DRY"
        elif (Devices[4].sValue == "50"):
            requestUrl = requestUrl + "FAN"

        # Set fanspeed
        requestUrl = requestUrl + "&fanspeed="

        if (Devices[5].sValue == "0"):
            requestUrl = requestUrl + "AUTO"
        elif (Devices[5].sValue == "10"):
            requestUrl = requestUrl + "AUTO"
        elif (Devices[5].sValue == "20"):
            requestUrl = requestUrl + "LOW"
        elif (Devices[5].sValue == "30"):
            requestUrl = requestUrl + "MID"
        elif (Devices[5].sValue == "40"):
            requestUrl = requestUrl + "HIGH"

        # Set temp
        requestUrl = requestUrl + "&temperature="

        if (Devices[6].sValue < "16"):  # Set temp Lower than range
            Domoticz.Log("Set temp is lower than authorized range !")
            requestUrl = requestUrl + "16"
        elif (Devices[6].sValue > "30"):  # Set temp Upper than range
            Domoticz.Log("Set temp is upper than authorized range !")
            requestUrl = requestUrl + "30"
        else:
            requestUrl = requestUrl + Devices[6].sValue

        # Set windDirection (swing)
        requestUrl = requestUrl + "&winddirection="

        if (Devices[7].sValue == "0"):
            requestUrl = requestUrl + "MANU"
        elif (Devices[7].sValue == "10"):
            requestUrl = requestUrl + "AUTO"

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

