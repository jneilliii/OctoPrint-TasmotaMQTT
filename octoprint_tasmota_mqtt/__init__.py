# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.server import user_permission


class TasmotaMQTTPlugin(octoprint.plugin.SettingsPlugin,
                         octoprint.plugin.AssetPlugin,
                         octoprint.plugin.TemplatePlugin,
						 octoprint.plugin.StartupPlugin,
						 octoprint.plugin.SimpleApiPlugin,
						 octoprint.plugin.EventHandlerPlugin):

	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			topic = "sonoff",
			arrRelays = [dict(index=1,topic="sonoff",warn=True,gcode=False)]
		)
		
	##~~ StartupPlugin mixin
	
	def on_after_startup(self):
		helpers = self._plugin_manager.get_helpers("mqtt", "mqtt_publish", "mqtt_subscribe", "mqtt_unsubscribe")
		if helpers:
			if "mqtt_publish" in helpers:
				self.mqtt_publish = helpers["mqtt_publish"]
			if "mqtt_subscribe" in helpers:
				self.mqtt_subscribe = helpers["mqtt_subscribe"]
			if "mqtt_unsubscribe" in helpers:
				self.mqtt_unsubscribe = helpers["mqtt_unsubscribe"]

		self.mqtt_publish("octoprint/plugin/tasmota/pub", "OctoPrint-TasmotaMQTT publishing.")
		self.mqtt_subscribe("%s/stat/POWER" % self._settings.get(["topic"]), self._on_mqtt_subscription)

	def _on_mqtt_subscription(self, topic, message, retained=None, qos=None, *args, **kwargs):
		self._logger.info("Received message for {topic}: {message}".format(**locals()))
		self.mqtt_publish("octoprint/plugin/tasmota/pub", "echo: " + message)
		self._settings.set(["%s" % topic],message)
		self._settings.save()
		self._plugin_manager.send_plugin_message(self._identifier, dict(currentstate=message))
		
	##~~ EventHandlerPlugin mixin
		
	def on_event(self, event, payload):
		if event == "ClientOpened":
			self.mqtt_publish("%s/cmnd/POWER" % self._settings.get(["topic"]),"")

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
		return dict(toggleRelay=["topic"],addTopic=["topic"])
		
	def on_api_command(self, command, data):
		if not user_permission.can():
			from flask import make_response
			return make_response("Insufficient rights", 403)
			
		if command == 'toggleRelay':
			self.logger.info("toggling {topic}".format(**data))
			self.mqtt_publish("%s/cmnd/Power" % "{topic}".format(**data), "TOGGLE")
			
		if command == 'addTopic':
			self.logger.info("adding {topic}".format(**data))
			relays = self._settings.get(["arrRelays"])
			relays.append(dict(topic="{topic}".format(**data),warn=True,gcode=False))			
			self._settings.set(["arrRelays"],relays,True)
	
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

