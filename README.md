# OctoPrint-TasmotaMQTT

This plugin allows the control of [Tasmota](https://github.com/arendst/Sonoff-Tasmota) devices from within OctoPrint via [MQTT](https://github.com/arendst/Sonoff-Tasmota/wiki/MQTT-Overview#mqtt-overview) commands.

## Prerequisites

Install the [MQTT](https://github.com/OctoPrint/OctoPrint-MQTT) plugin via the Plugin Manager or manually using this url:

	https://github.com/OctoPrint/OctoPrint-MQTT/archive/master.zip
	
## Setup

Install via the Plugin Manager or manually using this URL:

    https://github.com/jneilliii/OctoPrint-TasmotaMQTT/archive/master.zip

## Configuration

- Once installed your Tasmota devices will need to have the FullTopic configured as **%topic%/%prefix%/**
- Use the Tasmota device's topic in the Tasmota-MQTT Plugin settings for the individual relays.
- For multiple relay devices enter the index number that matches your desired relay.
- For single relay devices like the [iTead Sonoff S20 Smart Socket](https://www.itead.cc/smart-socket.html), leave Relay # blank.

## Screenshots

![screenshot](navbar.png)

![screenshot](settings.png)

![screenshot](relay_editor.png)