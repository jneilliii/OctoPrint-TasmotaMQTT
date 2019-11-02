# OctoPrint-TasmotaMQTT

This plugin allows the control of [Tasmota](https://github.com/arendst/Sonoff-Tasmota) devices from within OctoPrint via [MQTT](https://github.com/arendst/Sonoff-Tasmota/wiki/MQTT-Overview#mqtt-overview) commands.

## Prerequisites

Install the [MQTT](https://github.com/OctoPrint/OctoPrint-MQTT) plugin via the Plugin Manager or manually using this url:

	https://github.com/OctoPrint/OctoPrint-MQTT/archive/master.zip
	
## Setup

Install via the Plugin Manager or manually using this URL:

    https://github.com/jneilliii/OctoPrint-TasmotaMQTT/archive/master.zip

## Configuration

- Once installed you need to configure the "Full Topic" EXACTLY the same way like in your Tasmota devices. It can be found at the Tasmota device web-service page under information. Copy it over to make sure it is identical. E.g., **%topic%/%prefix%/**
- add a Relay device and configure
 - **Topic** is the name of the Tasmota device
 - **Relay #** For multiple relay devices enter the index number that matches your desired relay. For single relay devices like the [iTead Sonoff S20 Smart Socket](https://www.itead.cc/smart-socket.html), leave it blank.
 - **Icon class** lets you select the icon to be shown on the front page.
 - **Warning Prompt** Issues always an addtional warning to avoid accidentally switching.
 - **Warn While Printing** Issues an addtional warning only if a print is in progress. 
 - **Auto Connect** Connect to the printer N seconds after power was switched on. The time delays can help to establish a stable connection. 	
 - **Auto Disconnect** Disconnects the printer N seconds prior of switching off the power.  
 - **GCODE Trigger** Enable the switching via M80 and M81 code. See below.
 - **GCODE On Delay** Time delay after receiving M80 before switching on.
 - **GCODE Off Delay** Time delay after receving M81 before switching off. 
 - **Run System Command After On** Issue a system command after switching on. 
 - **Run System Command Before Off** Issue a system command after switching off.

### GCODE config
M80|M81 TOPIC RELAY#

M80 -- Switch on
M81 -- Switch off

Arguments:
TOPIC: Name of the device to be switched (Same as in Tasmota)
RELAY#: Number of the relay to be switched. Leave it empty for single relay units 


## Screenshots

![screenshot](navbar.png)

![screenshot](settings.png)

![screenshot](relay_editor.png)

## Support My Efforts
I programmed this plugin for fun and do my best effort to support those that have issues with it, please return the favor and support me.

[![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://paypal.me/jneilliii)
