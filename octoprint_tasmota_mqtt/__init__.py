# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.server import user_permission


class TasmotaMQTTPlugin(octoprint.plugin.SettingsPlugin,
                         octoprint.plugin.AssetPlugin,
                         octoprint.plugin.TemplatePlugin,
						 octoprint.plugin.StartupPlugin,
						 octoprint.plugin.SimpleApiPlugin,
						 octoprint.plugin.EventHandlerPlugin,
						 octoprint.plugin.WizardPlugin):

	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			arrRelays = [dict(index=1,topic="sonoff",relayN=1,warn=True,gcode=False,currentstate="UNKNOWN",gcodeOnDelay=0)]
		)
		
	def get_settings_version(self):
		return 1
		
	def on_settings_migrate(self, target, current=None):
		if current is None or current < self.get_settings_version():
			self._settings.set(['arrRelays'], self.get_settings_defaults()["arrRelays"])
		
	##~~ StartupPlugin mixin
	
	def on_after_startup(self):
		helpers = self._plugin_manager.get_helpers("mqtt", "mqtt_publish", "mqtt_subscribe", "mqtt_unsubscribe")
		if helpers:
			if "mqtt_publish" in helpers:
				self.mqtt_publish = helpers["mqtt_publish"]
				self.mqtt_publish("octoprint/plugin/tasmota", "OctoPrint-TasmotaMQTT publishing.")
			if "mqtt_subscribe" in helpers:
				self.mqtt_subscribe = helpers["mqtt_subscribe"]
				for relay in self._settings.get(["arrRelays"]):
					self._logger.info("%s/stat/POWER%s" % (relay["topic"],relay["relayN"]))
					self.mqtt_subscribe("%s/stat/POWER%s" % (relay["topic"],relay["relayN"]), self._on_mqtt_subscription, kwargs=dict(top=relay["topic"],relayN=relay["relayN"]))
			if "mqtt_unsubscribe" in helpers:
				self.mqtt_unsubscribe = helpers["mqtt_unsubscribe"]
		else:
			self._plugin_manager.send_plugin_message(self._identifier, dict(noMQTT=True))

	def _on_mqtt_subscription(self, topic, message, retained=None, qos=None, *args, **kwargs):
		self._logger.info("Received message for {topic}: {message}".format(**locals()))
		self.mqtt_publish("octoprint/plugin/tasmota", "echo: " + message)
		# self._settings.set(["%s" % topic],message)
		# self._settings.save()
		# self._plugin_manager.send_plugin_message(self._identifier, dict(topic="{top}".format(**kwargs),relayN="{relayN}".format(**kwargs),currentstate=message))	
		newrelays = []
		bolRelayStateChanged = False
		for relay in self._settings.get(["arrRelays"]):
			if relay["topic"] == "{top}".format(**kwargs) and relay["relayN"] == "{relayN}".format(**kwargs) and relay["currentstate"] != message:
				bolRelayStateChanged = True
				relay["currentstate"] = message
				self._plugin_manager.send_plugin_message(self._identifier, dict(topic="{top}".format(**kwargs),relayN="{relayN}".format(**kwargs),currentstate=message))
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
					self.mqtt_subscribe("%s/stat/POWER%s" % (relay["topic"],relay["relayN"]), self._on_mqtt_subscription, kwargs=dict(top=relay["topic"],relayN=relay["relayN"]))
			except:
				self._plugin_manager.send_plugin_message(self._identifier, dict(noMQTT=True))

	##~~ AssetPlugin mixin

	def get_assets(self):
		# Define your plugin's asset files to automatically include in the
		# core UI here.
		return dict(
			js=["js/tasmota_mqtt.js"],
			css=["css/tasmota_mqtt.css"]
		)
		
	##~~ TemplatePlugin mixin
	
	def get_template_configs(self):
		return [
			dict(type="navbar", custom_bindings=True),
			dict(type="settings", custom_bindings=True)
		]
		
	##~~ SimpleApiPlugin mixin
	
	def get_api_commands(self):
		return dict(toggleRelay=["topic","relayN"],checkRelay=["topic","relayN"],checkStatus=[],removeRelay=["topic","relayN"])
		
	def on_api_command(self, command, data):
		if not user_permission.can():
			from flask import make_response
			return make_response("Insufficient rights", 403)
			
		if command == 'toggleRelay':
			self._logger.info("toggling {topic} relay {relayN}".format(**data))
			self.mqtt_publish("{topic}/cmnd/Power{relayN}".format(**data), "TOGGLE")
			
		if command == 'checkStatus':
			for relay in self._settings.get(["arrRelays"]):
				self._logger.info("checking status of %s relay %s" % (relay["topic"],relay["relayN"]))
				self.mqtt_publish("%s/cmnd/POWER%s" % (relay["topic"],relay["relayN"]),"")
					
		if command == 'checkRelay':
			self._logger.info("subscribing to {topic} relay {relayN}".format(**data))
			self.mqtt_subscribe("{topic}/stat/POWER{relayN}".format(**data), self._on_mqtt_subscription, kwargs=dict(top="{topic}".format(**data),relayN="{relayN}".format(**data)))
			self._logger.info("checking {topic} relay {relayN}".format(**data))
			self.mqtt_publish("{topic}/cmnd/Power{relayN}".format(**data), "")
			
		if command == 'removeRelay':
			self.mqtt_unsubscribe(self._on_mqtt_subscription,topic="{topic}/stat/POWER{relayN}".format(**data))
			
	##~~ WizardPlugin mixin
			
	def is_wizard_required(self):
		helpers = self._plugin_manager.get_helpers("mqtt")
		if helpers:
			return False
		return True 
	
	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
		# for details.
		return dict(
			tasmota_mqtt=dict(
				displayName="Tasmota-MQTT",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="jneilliii",
				repo="OctoPrint-TasmotaMQTT",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/jneilliii/OctoPrint-TasmotaMQTT/archive/{target_version}.zip"
			)
		)


# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Tasmota-MQTT"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = TasmotaMQTTPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}

