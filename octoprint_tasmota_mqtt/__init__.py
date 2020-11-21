# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.server import user_permission
from octoprint.events import eventManager, Events
from octoprint.util import RepeatedTimer
from uptime import uptime
import threading
import time
import os
import re
import logging

try:
	from octoprint.util import ResettableTimer
except:
	class ResettableTimer(threading.Thread):
		def __init__(self, interval, function, args=None, kwargs=None, on_reset=None, on_cancelled=None):
			threading.Thread.__init__(self)
			self._event = threading.Event()
			self._mutex = threading.Lock()
			self.is_reset = True

			if args is None:
				args = []
			if kwargs is None:
				kwargs = dict()

			self.interval = interval
			self.function = function
			self.args = args
			self.kwargs = kwargs
			self.on_cancelled = on_cancelled
			self.on_reset = on_reset


		def run(self):
			while self.is_reset:
				with self._mutex:
					self.is_reset = False
				self._event.wait(self.interval)

			if not self._event.isSet():
				self.function(*self.args, **self.kwargs)
			with self._mutex:
				self._event.set()

		def cancel(self):
			with self._mutex:
				self._event.set()

			if callable(self.on_cancelled):
				self.on_cancelled()

		def reset(self, interval=None):
			with self._mutex:
				if interval:
					self.interval = interval

				self.is_reset = True
				self._event.set()
				self._event.clear()

			if callable(self.on_reset):
				self.on_reset()

class TasmotaMQTTPlugin(octoprint.plugin.SettingsPlugin,
						octoprint.plugin.AssetPlugin,
						octoprint.plugin.TemplatePlugin,
						octoprint.plugin.StartupPlugin,
						octoprint.plugin.SimpleApiPlugin,
						octoprint.plugin.EventHandlerPlugin,
						octoprint.plugin.WizardPlugin):

	def __init__(self):
		self._logger = logging.getLogger("octoprint.plugins.tasmota_mqtt")
		self._tasmota_mqtt_logger = logging.getLogger("octoprint.plugins.tasmota_mqtt.debug")
		self.abortTimeout = 0
		self._timeout_value = None
		self._abort_timer = None
		self._countdown_active = False
		self._waitForHeaters = False
		self._waitForTimelapse = False
		self._timelapse_active = False
		self._skipIdleTimer = False
		self.powerOffWhenIdle = False
		self._idleTimer = None
		self._autostart_file = None

	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			arrRelays = [],
			full_topic_pattern='%topic%/%prefix%/',
			abortTimeout = 30,
			powerOffWhenIdle = False,
			idleTimeout = 30,
			idleIgnoreCommands = 'M105',
			idleTimeoutWaitTemp = 50,
			debug_logging = False
		)

	def get_settings_version(self):
		return 5

	def on_settings_migrate(self, target, current=None):
		if current is None or current < 3:
			self._settings.set(['arrRelays'], self.get_settings_defaults()["arrRelays"])

		if current == 2:
			# Add new fields
			arrRelays_new = []
			for relay in self._settings.get(['arrRelays']):
				relay["automaticShutdownEnabled"] = False
				arrRelays_new.append(relay)
			self._settings.set(["arrRelays"],arrRelays_new)

		if current <= 3:
			# Add new fields
			arrRelays_new = []
			for relay in self._settings.get(['arrRelays']):
				relay["errorEvent"] = False
				arrRelays_new.append(relay)
			self._settings.set(["arrRelays"],arrRelays_new)

		if current <= 4:
			# Add new fields
			arrRelays_new = []
			for relay in self._settings.get(['arrRelays']):
				relay["event_on_upload"] = False
				relay["event_on_startup"] = False
				arrRelays_new.append(relay)
			self._settings.set(["arrRelays"],arrRelays_new)

	def on_settings_save(self, data):
		old_debug_logging = self._settings.get_boolean(["debug_logging"])
		old_powerOffWhenIdle = self._settings.get_boolean(["powerOffWhenIdle"])
		old_idleTimeout = self._settings.get_int(["idleTimeout"])
		old_idleIgnoreCommands = self._settings.get(["idleIgnoreCommands"])
		old_idleTimeoutWaitTemp = self._settings.get_int(["idleTimeoutWaitTemp"])

		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

		self.abortTimeout = self._settings.get_int(["abortTimeout"])
		self.powerOffWhenIdle = self._settings.get_boolean(["powerOffWhenIdle"])

		self.idleTimeout = self._settings.get_int(["idleTimeout"])
		self.idleIgnoreCommands = self._settings.get(["idleIgnoreCommands"])
		self._idleIgnoreCommandsArray = self.idleIgnoreCommands.split(',')
		self.idleTimeoutWaitTemp = self._settings.get_int(["idleTimeoutWaitTemp"])

		if self.powerOffWhenIdle != old_powerOffWhenIdle:
			self._plugin_manager.send_plugin_message(self._identifier, dict(powerOffWhenIdle=self.powerOffWhenIdle, type="timeout", timeout_value=self._timeout_value))

		if self.powerOffWhenIdle == True:
			self._tasmota_mqtt_logger.debug("Settings saved, Automatic Power Off Endabled, starting idle timer...")
			self._reset_idle_timer()

		new_debug_logging = self._settings.get_boolean(["debug_logging"])

		if old_debug_logging != new_debug_logging:
			if new_debug_logging:
				self._tasmota_mqtt_logger.setLevel(logging.DEBUG)
			else:
				self._tasmota_mqtt_logger.setLevel(logging.INFO)

	##~~ StartupPlugin mixin

	def on_startup(self, host, port):
		# setup customized logger
		from octoprint.logging.handlers import CleaningTimedRotatingFileHandler
		tasmota_mqtt_logging_hnadler = CleaningTimedRotatingFileHandler(self._settings.get_plugin_logfile_path(postfix="debug"), when="D", backupCount=3)
		tasmota_mqtt_logging_hnadler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
		tasmota_mqtt_logging_hnadler.setLevel(logging.DEBUG)

		self._tasmota_mqtt_logger.addHandler(tasmota_mqtt_logging_hnadler)
		self._tasmota_mqtt_logger.setLevel(logging.DEBUG if self._settings.get_boolean(["debug_logging"]) else logging.INFO)
		self._tasmota_mqtt_logger.propagate = False

	def on_after_startup(self):
		helpers = self._plugin_manager.get_helpers("mqtt", "mqtt_publish", "mqtt_subscribe", "mqtt_unsubscribe")
		if helpers:
			if "mqtt_subscribe" in helpers:
				self.mqtt_subscribe = helpers["mqtt_subscribe"]
				for relay in self._settings.get(["arrRelays"]):
					self._tasmota_mqtt_logger.debug(self.generate_mqtt_full_topic(relay, "stat"))
					self.mqtt_subscribe(self.generate_mqtt_full_topic(relay, "stat"), self._on_mqtt_subscription, kwargs=dict(top=relay["topic"],relayN=relay["relayN"]))
			if "mqtt_publish" in helpers:
				self.mqtt_publish = helpers["mqtt_publish"]
				self.mqtt_publish("octoprint/plugin/tasmota", "OctoPrint-TasmotaMQTT publishing.")
				if any(map(lambda r: r["event_on_startup"] == True, self._settings.get(["arrRelays"]))):
					for relay in self._settings.get(["arrRelays"]):
						self._tasmota_mqtt_logger.debug("powering on {} due to startup.".format(relay["topic"]))
						self.turn_on(relay)
			if "mqtt_unsubscribe" in helpers:
				self.mqtt_unsubscribe = helpers["mqtt_unsubscribe"]
		else:
			self._plugin_manager.send_plugin_message(self._identifier, dict(noMQTT=True))

		self.abortTimeout = self._settings.get_int(["abortTimeout"])
		self._tasmota_mqtt_logger.debug("abortTimeout: %s" % self.abortTimeout)

		self.powerOffWhenIdle = self._settings.get_boolean(["powerOffWhenIdle"])
		self._tasmota_mqtt_logger.debug("powerOffWhenIdle: %s" % self.powerOffWhenIdle)

		self.idleTimeout = self._settings.get_int(["idleTimeout"])
		self._tasmota_mqtt_logger.debug("idleTimeout: %s" % self.idleTimeout)
		self.idleIgnoreCommands = self._settings.get(["idleIgnoreCommands"])
		self._idleIgnoreCommandsArray = self.idleIgnoreCommands.split(',')
		self._tasmota_mqtt_logger.debug("idleIgnoreCommands: %s" % self.idleIgnoreCommands)
		self.idleTimeoutWaitTemp = self._settings.get_int(["idleTimeoutWaitTemp"])
		self._tasmota_mqtt_logger.debug("idleTimeoutWaitTemp: %s" % self.idleTimeoutWaitTemp)

		if self.powerOffWhenIdle == True:
			self._tasmota_mqtt_logger.debug("Starting idle timer due to startup")
			self._reset_idle_timer()

	def _on_mqtt_subscription(self, topic, message, retained=None, qos=None, *args, **kwargs):
		self._tasmota_mqtt_logger.debug("Received message for {topic}: {message}".format(**locals()))
		self.mqtt_publish("octoprint/plugin/tasmota", "echo: " + message.decode("utf-8"))
		newrelays = []
		bolRelayStateChanged = False
		for relay in self._settings.get(["arrRelays"]):
			if relay["topic"] == "{top}".format(**kwargs) and relay["relayN"] == "{relayN}".format(**kwargs) and relay["currentstate"] != message.decode("utf-8"):
				bolRelayStateChanged = True
				relay["currentstate"] = message.decode("utf-8")
				self._plugin_manager.send_plugin_message(self._identifier, dict(topic="{top}".format(**kwargs),relayN="{relayN}".format(**kwargs),currentstate=message.decode("utf-8")))
			newrelays.append(relay)

		if bolRelayStateChanged:
			self._settings.set(["arrRelays"],newrelays)
			self._settings.save()

	##~~ EventHandlerPlugin mixin

	def on_event(self, event, payload):
		if event == "WHERE":
			try:
				self.mqtt_unsubscribe(self._on_mqtt_subscription)
				for relay in self._settings.get(["arrRelays"]):
					self.mqtt_subscribe(self.generate_mqtt_full_topic(relay, "stat"), self._on_mqtt_subscription, kwargs=dict(top=relay["topic"],relayN=relay["relayN"]))
			except:
				self._plugin_manager.send_plugin_message(self._identifier, dict(noMQTT=True))

		# Client Opened Event
		if event == Events.CLIENT_OPENED:
			self._plugin_manager.send_plugin_message(self._identifier, dict(powerOffWhenIdle=self.powerOffWhenIdle, type="timeout", timeout_value=self._timeout_value))
			return

		# Print Started Event
		if event == Events.PRINT_STARTED and self.powerOffWhenIdle == True:
			if self._abort_timer is not None:
				self._abort_timer.cancel()
				self._abort_timer = None
				self._tasmota_mqtt_logger.debug("Power off aborted because starting new print.")
			if self._idleTimer is not None:
				self._reset_idle_timer()
			self._timeout_value = None
			self._plugin_manager.send_plugin_message(self._identifier, dict(powerOffWhenIdle=self.powerOffWhenIdle, type="timeout", timeout_value=self._timeout_value))

		# Print Error Event
		if event == Events.ERROR:
			self._tasmota_mqtt_logger.debug("Powering off enabled plugs because there was an error.")
			for relay in self._settings.get(['arrRelays']):
				if relay.get("errorEvent", False):
					self.turn_off(relay)

		# Timeplapse Events
		if self.powerOffWhenIdle == True and event == Events.MOVIE_RENDERING:
			self._tasmota_mqtt_logger.debug("Timelapse generation started: %s" % payload.get("movie_basename", ""))
			self._timelapse_active = True

		if self._timelapse_active and event == Events.MOVIE_DONE or event == Events.MOVIE_FAILED:
			self._tasmota_mqtt_logger.debug("Timelapse generation finished: %s. Return Code: %s" % (payload.get("movie_basename", ""), payload.get("returncode", "completed")))
			self._timelapse_active = False

		# Printer Connected Event
		if event == Events.CONNECTED:
			if self._autostart_file:
				self._tasmota_mqtt_logger.debug("printer connected starting print of %s" % self._autostart_file)
				self._printer.select_file(self._autostart_file, False, printAfterSelect=True)
				self._autostart_file = None
		# File Uploaded Event
		if event == Events.UPLOAD and any(map(lambda r: r["event_on_upload"] == True, self._settings.get(["arrRelays"]))):
			if payload.get("print", False):  # implemented in OctoPrint version 1.4.1
				self._tasmota_mqtt_logger.debug(
					"File uploaded: %s. Turning enabled relays on." % payload.get("name", ""))
				self._tasmota_mqtt_logger.debug(payload)
				for relay in self._settings.get(['arrRelays']):
					self._tasmota_mqtt_logger.debug(relay)
					if relay["event_on_upload"] is True and not self._printer.is_ready():
						self._tasmota_mqtt_logger.debug("powering on %s due to %s event." % (relay["topic"], event))
						if payload.get("path", False) and payload.get("target") == "local":
							self._autostart_file = payload.get("path")
							self.turn_on(relay)

	##~~ AssetPlugin mixin

	def get_assets(self):
		return dict(
			js=["js/jquery-ui.min.js","js/knockout-sortable.1.2.0.js","js/fontawesome-iconpicker.js","js/ko.iconpicker.js","js/tasmota_mqtt.js"],
			css=["css/font-awesome.min.css","css/font-awesome-v4-shims.min.css","css/fontawesome-iconpicker.css","css/tasmota_mqtt.css"]
		)

	##~~ TemplatePlugin mixin

	def get_template_configs(self):
		return [
			dict(type="navbar", custom_bindings=True),
			dict(type="settings", custom_bindings=True),
			dict(type="sidebar", icon="plug", custom_bindings=True, data_bind="visible: filteredSmartplugs().length > 0", template="tasmota_mqtt_sidebar.jinja2", template_header="tasmota_mqtt_sidebar_header.jinja2")
		]

	##~~ SimpleApiPlugin mixin

	def get_api_commands(self):
		return dict(
			turnOn=["topic","relayN"],
			turnOff=["topic","relayN"],
			toggleRelay=["topic","relayN"],
			checkRelay=["topic","relayN"],
			checkStatus=[],
			removeRelay=["topic","relayN"],
			enableAutomaticShutdown=[],
			disableAutomaticShutdown=[],
			abortAutomaticShutdown=[])

	def on_api_command(self, command, data):
		if not user_permission.can():
			from flask import make_response
			return make_response("Insufficient rights", 403)

		if command == 'toggleRelay' or command == 'turnOn' or command == 'turnOff':
			for relay in self._settings.get(["arrRelays"]):
				if relay["topic"] == "{topic}".format(**data) and relay["relayN"] == "{relayN}".format(**data):
					if command == "turnOff" or (command == "toggleRelay" and relay["currentstate"] == "ON"):
						self._tasmota_mqtt_logger.debug("turning off {topic} relay {relayN}".format(**data))
						self.turn_off(relay)
					if command == "turnOn" or (command == "toggleRelay" and relay["currentstate"] == "OFF"):
						self._tasmota_mqtt_logger.debug("turning on {topic} relay {relayN}".format(**data))
						self.turn_on(relay)
		if command == 'checkStatus':
			for relay in self._settings.get(["arrRelays"]):
				self._tasmota_mqtt_logger.debug("checking status of %s relay %s" % (relay["topic"],relay["relayN"]))
				try:
					self.mqtt_publish(self.generate_mqtt_full_topic(relay, "cmnd"),"")
				except:
					self._plugin_manager.send_plugin_message(self._identifier, dict(noMQTT=True))

		if command == 'checkRelay':
			self._tasmota_mqtt_logger.debug("subscribing to {topic} relay {relayN}".format(**data))
			for relay in self._settings.get(["arrRelays"]):
				if relay["topic"] == "{topic}".format(**data) and relay["relayN"] == "{relayN}".format(**data):
					self.mqtt_subscribe(self.generate_mqtt_full_topic(relay, "stat"), self._on_mqtt_subscription, kwargs=dict(top="{topic}".format(**data),relayN="{relayN}".format(**data)))
					self._tasmota_mqtt_logger.debug("checking {topic} relay {relayN}".format(**data))
					self.mqtt_publish(self.generate_mqtt_full_topic(relay, "cmnd"), "")

		if command == 'removeRelay':
			for relay in self._settings.get(["arrRelays"]):
				if relay["topic"] == "{topic}".format(**data) and relay["relayN"] == "{relayN}".format(**data):
					self.mqtt_unsubscribe(self._on_mqtt_subscription,topic=self.generate_mqtt_full_topic(relay, "stat"))

		if command == 'enableAutomaticShutdown':
			self.powerOffWhenIdle = True
			self._tasmota_mqtt_logger.debug("Automatic Power Off enabled, starting idle timer.")
			self._start_idle_timer()

		if command == 'disableAutomaticShutdown':
			self.powerOffWhenIdle = False
			if self._abort_timer is not None:
				self._abort_timer.cancel()
				self._abort_timer = None
			self._timeout_value = None
			self._tasmota_mqtt_logger.debug("Automatic Power Off disabled, stopping idle and abort timers.")
			self._stop_idle_timer()

		if command == 'abortAutomaticShutdown':
			if self._abort_timer is not None:
				self._abort_timer.cancel()
				self._abort_timer = None
			self._timeout_value = None
			self._tasmota_mqtt_logger.debug("Power off aborted.")
			self._tasmota_mqtt_logger.debug("Restarting idle timer.")
			self._reset_idle_timer()

		if command == "enableAutomaticShutdown" or command == "disableAutomaticShutdown":
			self._tasmota_mqtt_logger.debug("Automatic power off setting changed: %s" % self.powerOffWhenIdle)
			self._settings.set_boolean(["powerOffWhenIdle"], self.powerOffWhenIdle)
			self._settings.save()

		if command == "enableAutomaticShutdown" or command == "disableAutomaticShutdown" or command == "abortAutomaticShutdown":
			self._plugin_manager.send_plugin_message(self._identifier, dict(powerOffWhenIdle=self.powerOffWhenIdle, type="timeout", timeout_value=self._timeout_value))

	def turn_on(self, relay):
		self.mqtt_publish(self.generate_mqtt_full_topic(relay, "cmnd"), "ON")
		if relay["sysCmdOn"]:
			t = threading.Timer(int(relay["sysCmdOnDelay"]),os.system,args=[relay["sysCmdRunOn"]])
			t.start()
		if relay["connect"] and self._printer.is_closed_or_error():
			t = threading.Timer(int(relay["connectOnDelay"]),self._printer.connect)
			t.start()
		if self.powerOffWhenIdle == True and relay["automaticShutdownEnabled"] == True:
			self._tasmota_mqtt_logger.debug("Resetting idle timer since relay %s | %s was just turned on." % (relay["topic"], relay["relayN"]))
			self._waitForHeaters = False
			self._reset_idle_timer()

	def turn_off(self, relay):
		if relay["sysCmdOff"]:
			t = threading.Timer(int(relay["sysCmdOffDelay"]),os.system,args=[relay["sysCmdRunOff"]])
			t.start()
		if relay["disconnect"]:
			self._printer.disconnect()
			time.sleep(int(relay["disconnectOffDelay"]))
		self.mqtt_publish(self.generate_mqtt_full_topic(relay, "cmnd"), "OFF")

	##~~ Gcode processing hook

	def gcode_turn_off(self, relay):
		if relay["warnPrinting"] and self._printer.is_printing():
			self._tasmota_mqtt_logger.debug("Not powering off %s | %s because printer is printing." % (relay["topic"],relay["relayN"]))
		else:
			self.turn_off(relay)

	def processGCODE(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
		if gcode:
			if cmd.startswith("M8") and cmd.count(" ") >= 1:
				topic = cmd.split()[1]
				if cmd.count(" ") == 2:
					relayN = cmd.split()[2]
				else:
					relayN = ""
				for relay in self._settings.get(["arrRelays"]):
					if relay["topic"].upper() == topic.upper() and relay["relayN"] == relayN and relay["gcode"]:
						if cmd.startswith("M80"):
							t = threading.Timer(int(relay["gcodeOnDelay"]),self.turn_on,[relay])
							t.start()
							return "M80"
						elif cmd.startswith("M81"):
							## t = threading.Timer(int(relay["gcodeOffDelay"]),self.mqtt_publish,[relay["topic"] + "/cmnd/Power" + relay["relayN"], "OFF"])
							t = threading.Timer(int(relay["gcodeOffDelay"]),self.gcode_turn_off,[relay])
							t.start()
							return "M81"
			elif self.powerOffWhenIdle and not (gcode in self._idleIgnoreCommandsArray):
				self._waitForHeaters = False
				self._reset_idle_timer()
				return
			else:
				return
		else:
			return

	##~~ Idle Timeout

	def _start_idle_timer(self):
		self._stop_idle_timer()

		if self.powerOffWhenIdle and any(map(lambda r: r["currentstate"] == "ON", self._settings.get(["arrRelays"]))):
			self._idleTimer = ResettableTimer(self.idleTimeout * 60, self._idle_poweroff)
			self._idleTimer.start()

	def _stop_idle_timer(self):
		if self._idleTimer:
			self._idleTimer.cancel()
			self._idleTimer = None

	def _reset_idle_timer(self):
		try:
			if self._idleTimer.is_alive():
				self._idleTimer.reset()
			else:
				raise Exception()
		except:
			self._start_idle_timer()

	def _idle_poweroff(self):
		if not self.powerOffWhenIdle:
			return

		if self._waitForHeaters:
			return

		if self._waitForTimelapse:
			return

		if self._printer.is_printing() or self._printer.is_paused():
			return

		if (uptime()/60) <= (self._settings.get_int(["idleTimeout"])):
			self._tasmota_mqtt_logger.debug("Just booted so wait for time sync.")
			self._tasmota_mqtt_logger.debug("uptime: {}, comparison: {}".format((uptime()/60), (self._settings.get_int(["idleTimeout"]))))
			self._reset_idle_timer()
			return

		self._tasmota_mqtt_logger.debug("Idle timeout reached after %s minute(s). Turning heaters off prior to powering off plugs." % self.idleTimeout)
		if self._wait_for_heaters():
			self._tasmota_mqtt_logger.debug("Heaters below temperature.")
			if self._wait_for_timelapse():
				self._timer_start()
		else:
			self._tasmota_mqtt_logger.debug("Aborted power off due to activity.")

	##~~ Timelapse Monitoring

	def _wait_for_timelapse(self):
		self._waitForTimelapse = True
		self._tasmota_mqtt_logger.debug("Checking timelapse status before shutting off power...")

		while True:
			if not self._waitForTimelapse:
				return False

			if not self._timelapse_active:
				self._waitForTimelapse = False
				return True

			self._tasmota_mqtt_logger.debug("Waiting for timelapse before shutting off power...")
			time.sleep(5)

	##~~ Temperature Cooldown

	def _wait_for_heaters(self):
		self._waitForHeaters = True
		heaters = self._printer.get_current_temperatures()

		for heater, entry in heaters.items():
			target = entry.get("target")
			if target is None:
				# heater doesn't exist in fw
				continue

			try:
				temp = float(target)
			except ValueError:
				# not a float for some reason, skip it
				continue

			if temp != 0:
				self._tasmota_mqtt_logger.debug("Turning off heater: %s" % heater)
				self._skipIdleTimer = True
				self._printer.set_temperature(heater, 0)
				self._skipIdleTimer = False
			else:
				self._tasmota_mqtt_logger.debug("Heater %s already off." % heater)

		while True:
			if not self._waitForHeaters:
				return False

			heaters = self._printer.get_current_temperatures()

			highest_temp = 0
			heaters_above_waittemp = []
			for heater, entry in heaters.items():
				if not heater.startswith("tool"):
					continue

				actual = entry.get("actual")
				if actual is None:
					# heater doesn't exist in fw
					continue

				try:
					temp = float(actual)
				except ValueError:
					# not a float for some reason, skip it
					continue

				self._tasmota_mqtt_logger.debug("Heater %s = %sC" % (heater,temp))
				if temp > self.idleTimeoutWaitTemp:
					heaters_above_waittemp.append(heater)

				if temp > highest_temp:
					highest_temp = temp

			if highest_temp <= self.idleTimeoutWaitTemp:
				self._waitForHeaters = False
				return True

			self._tasmota_mqtt_logger.debug("Waiting for heaters(%s) before shutting power off..." % ', '.join(heaters_above_waittemp))
			time.sleep(5)

	##~~ Abort Power Off Timer

	def _timer_start(self):
		if self._abort_timer is not None:
			return

		self._tasmota_mqtt_logger.debug("Starting abort power off timer.")

		self._timeout_value = self.abortTimeout
		self._abort_timer = RepeatedTimer(1, self._timer_task)
		self._abort_timer.start()

	def _timer_task(self):
		if self._timeout_value is None:
			return

		self._timeout_value -= 1
		self._plugin_manager.send_plugin_message(self._identifier, dict(powerOffWhenIdle=self.powerOffWhenIdle, type="timeout", timeout_value=self._timeout_value))
		if self._timeout_value <= 0:
			if self._abort_timer is not None:
				self._abort_timer.cancel()
				self._abort_timer = None
			self._shutdown_system()

	def _shutdown_system(self):
		self._tasmota_mqtt_logger.debug("Automatically powering off enabled plugs.")
		for relay in self._settings.get(['arrRelays']):
			if relay.get("automaticShutdownEnabled", False):
				self.turn_off(relay)

	##~~ Utility functions

	def generate_mqtt_full_topic(self, relay, prefix):
		full_topic = re.sub(r'%topic%', relay["topic"], self._settings.get(["full_topic_pattern"]))
		full_topic = re.sub(r'%prefix%', prefix, full_topic)
		full_topic = full_topic + "POWER" + relay["relayN"]
		return full_topic

	##~~ WizardPlugin mixin

	def is_wizard_required(self):
		helpers = self._plugin_manager.get_helpers("mqtt")
		if helpers:
			return False
		return True

	##~~ Softwareupdate hook

	def get_update_information(self):
		return dict(
			tasmota_mqtt=dict(
				displayName="Tasmota-MQTT",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="jneilliii",
				repo="OctoPrint-TasmotaMQTT",
				current=self._plugin_version,
				stable_branch=dict(
					name="Stable", branch="master", comittish=["master"]
				),
				prerelease_branches=[
					dict(
						name="Release Candidate",
						branch="rc",
						comittish=["rc", "master"],
					)
				],

				# update method: pip
				pip="https://github.com/jneilliii/OctoPrint-TasmotaMQTT/archive/{target_version}.zip"
			)
		)

__plugin_name__ = "Tasmota-MQTT"
__plugin_pythoncompat__ = ">=2.7,<4"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = TasmotaMQTTPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.processGCODE,
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}

