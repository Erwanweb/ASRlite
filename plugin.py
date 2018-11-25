"""
Aircon Smart Remote plugin for Domoticz
Author: MrErwan,
        xx
Version:    0.0.1: alpha
"""
"""
<plugin key="ASRlite2" name="AC Aircon Smart Remote 2" author="MrErwan" version="0.0.1">
    <description>
        <h2>Aircon Smart Remote</h2><br/>
        Easily implement in Domoticz an full control of air conditoner using IR Remote<br/>
        <h3>Set-up and Configuration</h3>
        
    </description>
    <params>
        <param field="Address" label="Domoticz IP Address" width="200px" required="true" default="localhost"/>
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
import urllib.parse as parse
import urllib.request as request
import base64
import itertools


class deviceparam:

    def __init__(self,unit,nvalue,svalue):
        self.unit = unit
        self.nvalue = nvalue
        self.svalue = svalue


class BasePlugin:

    def __init__(self):

        # self.var = 123
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
                       "LevelNames":"Auto|Low|Mid|High",
                       "LevelOffHidden":"true",
                       "SelectorStyle":"0"}
            Domoticz.Device(Name = "Fan",Unit = 2,TypeName = "Selector Switch",Switchtype = 18,Image = 15,
                            Options = Options,Used = 1).Create()
            devicecreated.append(deviceparam(2,0,"10"))  # default is Auto mode
        if 3 not in Devices:
            Domoticz.Device(Name = "Setpoint",Unit = 3,Type = 242,Subtype = 1,Used = 1).Create()
            devicecreated.append(deviceparam(3,0,"20"))  # default is 20 degrees

        # if any device has been created in onStart(), now is time to update its defaults
        for device in devicecreated:
            Devices[device.unit].Update(nValue = device.nvalue,sValue = device.svalue)

    def onStop(self):

        Domoticz.Log("ASR onStop - Plugin is stopping.")
        Domoticz.Debugging(0)

    def onHeartbeat(self):
        Devices[Unit].Update(nValue = nvalue,sValue = svalue)

    def onCommand(self,Unit,Command,Level,Color):

        requestUrl = Parameters["Mode6"] + "/api_chunghopserver?action=changeconfig&remote=" + Parameters["Mode2"]

        Devices[Unit].Update(nValue = nvalue,sValue = svalue)

        if Unit in (1,2,3):

            # Aircon Mode

            if Devices[1].sValue == "0":
                requestUrl = requestUrl + "&onoff=OFF"  # Off
            Domoticz.Log("Aircon id 1 mode setted OFF")
            elif Devices[1].sValue == "10":
            requestUrl = requestUrl + "&onoff=ON&mode=COOL"  # Cool
            Domoticz.Log("Aircon id 1 mode setted COOL")
            elif Devices[1].sValue == "20":
            requestUrl = requestUrl + "&onoff=ON&mode=HEAT"  # Heat
            Domoticz.Log("Aircon id 1 mode setted HEAT")
            elif Devices[1].sValue == "30":
            requestUrl = requestUrl + "&onoff=ON&mode=DRY"  # Dry
            Domoticz.Log("Aircon id 1 mode setted DRY")
            elif Devices[1].sValue == "40":
            requestUrl = requestUrl + "&onoff=ON&mode=FAN"  # Fan
            Domoticz.Log("Aircon id 1 mode setted FAN")

            # Fan Mode

            if Devices[2].sValue == "0"):
                requestUrl = requestUrl + "&fanspeed=AUTO"  # Auto
                Domoticz.Log("Aircon id 1 FAN setted AUTO")
            elif Devices[2].sValue == "10":
                requestUrl = requestUrl + "&fanspeed=LOW"  # Low
                Domoticz.Log("Aircon id 1 FAN setted LOW")
            elif Devices[2].sValue == "20":
                requestUrl = requestUrl + "&fanspeed=MID"  # Mid
                Domoticz.Log("Aircon id 1 FAN setted MID")
            elif Devices[2].sValue == "30":
                requestUrl = requestUrl + "&fanspeed=HIGH"  # High
                Domoticz.Log("Aircon id 1 FAN setted HIGH")

            # Set Temp with limited range from 16 to 30

            if Devices[3].sValue > "16":
                requestUrl = requestUrl + "&temperature=16"  # Set Temp at Lower authorized by aircon
                Domoticz.Log("Aircon id 1 Set Temp requested is Lower than the Range")
            elif Devices[3].sValue > "30":
                requestUrl = requestUrl + "&temperature=30"  # Set Temp at Max authorized by aircon
                Domoticz.Log("Aircon id 1 Set Temp requested is Upper than the Range")
            else:  # Set Temp is in the authorized range
                requestUrl = requestUrl + "&temperature=" + Devices[3].sValue  # Set Temp
                Domoticz.Log("Aircon id 1 Temp Setted")


global _plugin
_plugin = BasePlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onCommand(Unit,Command,Level,Color):
    global _plugin
    _plugin.onCommand(Unit,Command,Level,Color)


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


# Plugin utility functions ---------------------------------------------------

def DomoticzAPI(APICall):
    resultJson = None
    url = "http://{}:{}/json.htm?{}".format(Parameters["Address"],Parameters["Port"],parse.quote(APICall,safe = "&="))
    Domoticz.Debug("Calling domoticz API: {}".format(url))
    try:
        req = request.Request(url)
        if Parameters["Username"] != "":
            Domoticz.Debug("Add authentification for user {}".format(Parameters["Username"]))
            credentials = ('%s:%s' % (Parameters["Username"],Parameters["Password"]))
            encoded_credentials = base64.b64encode(credentials.encode('ascii'))
            req.add_header('Authorization','Basic %s' % encoded_credentials.decode("ascii"))

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
