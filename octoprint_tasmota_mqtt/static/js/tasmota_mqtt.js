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
		self.currentstate = ko.observable();
		self.processing = ko.observable('');
		
		self.onBeforeBinding = function() {		
			self.topic(self.settingsViewModel.settings.plugins.tasmota_mqtt.topic());
			self.currentstate(self.settingsViewModel.settings.plugins.tasmota_mqtt.currentstate());
        }
		
		self.onDataUpdaterPluginMessage = function(plugin, data) {
			if (plugin != "tasmota_mqtt") {
				console.log(plugin);
				return;
			}
			console.log(data)
			self.currentstate(data.currentstate);
        };
		
		self.toggleRelay = function(data) {
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
				console.log('command sent to '+data.topic());
				self.processing('');
				});
        };
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
