/*
 * View model for OctoPrint-TasmotaMQTT
 *
 * Author: jneilliii
 * License: AGPLv3
 */
$(function() {
    function TasmotaMQTTViewModel(parameters) {
        var self = this;

        self.loginStateViewModel = parameters[0];
        self.settingsViewModel = parameters[1];

        self.topic = ko.observable();
		self.currentstate = ko.observable('UNKNOWN');
		self.processing = ko.observable('');
		self.arrRelays = ko.observableArray();
		
		self.onBeforeBinding = function() {
			self.topic(self.settingsViewModel.settings.plugins.tasmota_mqtt.topic());
			self.arrRelays(self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays());
			//self.currentstate(self.settingsViewModel.settings.plugins.tasmota_mqtt.currentstate());
        }
		
		self.onDataUpdaterPluginMessage = function(plugin, data) {
			if (plugin != "tasmota_mqtt") {
				self.processing('');
				return;
			}
			
			if (data.noMQTT) {
				new PNotify({
							title: 'Tasmota-MQTT Error',
							text: 'Missing the <a href="https:\/\/plugins.octoprint.org\/plugins\/mqtt\/" target="_blank">MQTT<\/a> plugin. Please install that plugin to make this plugin operational.',
							type: 'error',
							hide: false
							});
			} else {				
				self.currentstate(data.currentstate);
			}
			self.processing('');
        };
		
		self.toggleRelay = function(data) {
			console.log(data);
			self.processing(data.topic());
            $.ajax({
                url: API_BASEURL + "plugin/tasmota_mqtt",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "toggleRelay",
					topic: data.topic()
                }),
                contentType: "application/json; charset=UTF-8"
            }).done(function(){
				console.log('command was sent to '+data.topic());
				});
        };
		
		self.addRelay = function() {
			var arrRelaysLength = self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays().length;
			var nextIndex = self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays()[arrRelaysLength-1].index()+1;
			self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays.push( {'index':ko.observable(nextIndex),'topic':ko.observable('sonoff'),'warn':ko.observable(true),'gcode':ko.observable(false)} );
		}
		
		self.removeRelay = function(data) {
			console.log(data);
			self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays.remove(data);
		}
    }

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: TasmotaMQTTViewModel,
        // ViewModels your plugin depends on, e.g. loginStateViewModel, settingsViewModel, ...
        dependencies: ["loginStateViewModel", "settingsViewModel"],
        // Elements to bind to, e.g. #settings_plugin_tasmota-mqtt, #tab_plugin_tasmota-mqtt, ...
        elements: ["#settings_plugin_tasmota_mqtt","#navbar_plugin_tasmota_mqtt"]
    });
});
