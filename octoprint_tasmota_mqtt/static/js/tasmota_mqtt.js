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

		self.processing = ko.observableArray([]);
		self.arrRelays = ko.observableArray();
		self.selectedRelay = ko.observable();
		
		self.onBeforeBinding = function() {
			self.arrRelays(self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays());
        }
		
		self.onAfterBinding = function() {
            $.ajax({
                url: API_BASEURL + "plugin/tasmota_mqtt",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "checkStatus"
                }),
                contentType: "application/json; charset=UTF-8"
            });
		}
		
		self.onEventSettingsUpdated = function(payload) {
			self.settingsViewModel.requestData();
			self.arrRelays(self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays());
		}
		
		self.onDataUpdaterPluginMessage = function(plugin, data) {
			if (plugin != "tasmota_mqtt") {
				return;
			}
			console.log(data);
			if (data.noMQTT) {
				new PNotify({
							title: 'Tasmota-MQTT Error',
							text: 'Missing the <a href="https:\/\/plugins.octoprint.org\/plugins\/mqtt\/" target="_blank">MQTT<\/a> plugin. Please install that plugin to make this plugin operational.',
							type: 'error',
							hide: false
							});
			} else {
				var relay = ko.utils.arrayFirst(self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays(),function(item){
					return (item.topic() == data.topic) && (item.relayN() == data.relayN);
					}) || {'topic':data.topic,'relayN':data.relayN,'currentstate':'UNKNOWN'};
				if(relay.currentstate != data.currentstate) {
					relay.currentstate(data.currentstate);
				}
				
			}
			self.processing.remove(data.topic + '|' + data.relayN);
        };
		
		self.toggleRelay = function(data) {
			if(data.currentstate()=="UNKNOWN"){
				$.ajax({
					url: API_BASEURL + "plugin/tasmota_mqtt",
					type: "POST",
					dataType: "json",
					data: JSON.stringify({
						command: "checkRelay",
						topic: data.topic(),
						relayN: data.relayN()
					}),
					contentType: "application/json; charset=UTF-8"
				});	
			} else {
				self.processing.push(data.topic() + '|' + data.relayN());
				$.ajax({
					url: API_BASEURL + "plugin/tasmota_mqtt",
					type: "POST",
					dataType: "json",
					data: JSON.stringify({
						command: "toggleRelay",
						topic: data.topic(),
						relayN: data.relayN()
					}),
					contentType: "application/json; charset=UTF-8"
				});
			}
        };
		
		self.addRelay = function() {
			var arrRelaysLength = self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays().length;
			var nextIndex = self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays()[arrRelaysLength-1].index()+1;
			self.selectedRelay( {'index':ko.observable(nextIndex),
								'topic':ko.observable('sonoff'),
								'relayN':ko.observable('1'),
								'warn':ko.observable(true),
								'warnPrinting':ko.observable(true),
								'gcode':ko.observable(false),
								'gcodeOnDelay':ko.observable(0),
								'gcodeOffDelay':ko.observable(0),
								'connect':ko.observable(false),
								'connectOnDelay':ko.observable(15),
								'disconnect':ko.observable(false),
								'disconnectOffDelay':ko.observable(0),
								'sysCmdOn':ko.observable(false),
								'sysCmdRunOn':ko.observable(""),
								'sysCmdOnDelay':ko.observable(0),
								'sysCmdOff':ko.observable(false),
								'sysCmdRunOff':ko.observable(""),
								'sysCmdOffDelay':ko.observable(0),
								'currentstate':ko.observable('UNKNOWN')} );
			self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays.push(self.selectedRelay());
			$("#TasmotaMQTTRelayEditor").modal("show");																							
		}
		
		self.removeRelay = function(data) {
			self.settingsViewModel.settings.plugins.tasmota_mqtt.arrRelays.remove(data);
			$.ajax({
					url: API_BASEURL + "plugin/tasmota_mqtt",
					type: "POST",
					dataType: "json",
					data: JSON.stringify({
						command: "removeRelay",
						topic: data.topic(),
						relayN: data.relayN()
					}),
					contentType: "application/json; charset=UTF-8"
				});
		}
		
		self.editRelay = function(data) {
			self.selectedRelay(data);
			$("#TasmotaMQTTRelayEditor").modal("show");
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
