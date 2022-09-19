# coding=utf-8
from __future__ import absolute_import


import octoprint.plugin
import octoprint.util
import re
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
from urllib.error import URLError, HTTPError


BASE_PARAM = '/cgi-bin/configManager.cgi?action=setConfig&VideoWidget[0].CustomTitle[1].Text='
UPDATE_INTERVAL = 10.0
SEND_DAHUA = True
LOG_THRESHOLD = 200
WAIT_THRESHOLD = 60


class DahuaCamOverlayPlugin(octoprint.plugin.StartupPlugin,
							octoprint.plugin.SettingsPlugin,
                            octoprint.plugin.TemplatePlugin,
							octoprint.plugin.ProgressPlugin,
							octoprint.plugin.EventHandlerPlugin,
							octoprint.plugin.RestartNeedingPlugin):

	def __init__(self):
		super().__init__()
		self.progress_percent = 0
		self.progress_remaining_minutes = 0
		self.last_update = datetime.now()
		self.timer = None
		self.print_name = ""
		self.print_started = None
		self.print_done    = None
		self.print_duration = 0
		self.print_state = ""
		self.print_estimated_print_time = 0.0
		self.temps = (0,0,0,0) # actual hot end / target hot end / actual bed / target bed
		self.useM73 = True
		self.log_info_count = 0
		self.log_warn_count = 0
		self.log_error_count = 0
		self.worker_wait_until = datetime.now() + timedelta(seconds=WAIT_THRESHOLD)

	def log_info(self, message):
		self.log_info_count += 1
		if self.log_info_count < LOG_THRESHOLD:
			self._logger.info(message)

	def log_warn(self, message):
		self.log_warn_count += 1
		if self.log_warn_count < LOG_THRESHOLD:
			self._logger.warn(message)

	def log_error(self, message):
		self.log_error_count += 1
		if self.log_error_count < LOG_THRESHOLD:
			self._logger.error(message)

	def send_to_dahua(self, data):
		url = self.base_url + data
		if SEND_DAHUA:
			try:
				self.log_info(url)		
				res = urllib.request.urlopen(url, timeout=5)
				res_body = res.read()
				self.log_info("Response: %s" % res_body.decode('utf-8'))
			
			except HTTPError as e:
				self.log_error("HTTPError with code %d" % e.code)

			except URLError as e:
				self.log_error("URLError with reason %s" % e.reason)
			except:
				self.log_error("Error sending overlay!")


	def update_overlay(self):
		self.last_update = datetime.now()
		#self._logger.info("current progress: %d " % self.progress_percent)
		#self._logger.info("remaining minutes: %d " % self.progress_remaining_minutes)
		#self._logger.info("state: %s " % self.print_state)
		#self._logger.info("name: %s " % self.print_name)
		#self._logger.info("temps: %d/%d - %d/%d" % self.temps)
		#self._logger.info("print time: %d" % self.print_duration)
		td = timedelta(minutes=self.progress_remaining_minutes)
        finish_time = self.last_update + td      
        ps = finish_time.strftime('%Y-%m-%d %H:%M')        
		
		if self.print_started:
			ps = self.print_started.strftime("%Y-%m-%d %H:%M:%S") 

		if self.print_state in "Operational":
			hours, remainder = divmod(self.print_duration, 3600)
			minutes, seconds = divmod(remainder, 60)			
			ps = '%d:%02d:%02d' % (hours, minutes, seconds)

		line1 = "%s" % self.print_state
		line2 = "%d/%d - %d/%d" % self.temps
		line3 = "%d%% - %s" % (self.progress_percent, str(td)[:-3])
		line4 = "%s" % ps
		line5 = self.print_name

		if len(line5) > 22:
			line5 = line5[:22]

		self._logger.debug(line1)
		self._logger.debug(line2)
		self._logger.debug(line3)
		self._logger.debug(line4)
		self._logger.debug(line5)

		text_params = "%s|%s|%s|%s|%s" % (
			urllib.parse.quote(line1),
			urllib.parse.quote(line2),
			urllib.parse.quote(line3),
			urllib.parse.quote(line4),
			urllib.parse.quote(line5)
			)

		self.send_to_dahua(text_params)


	def handle_m73(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
		if self.useM73 and gcode and gcode == "M73":
			self._logger.debug("Receiving M73")					
			m_r = re.search('(?<=R)\w+', cmd)
			if m_r:
				self.progress_remaining_minutes = int(m_r.group(0))
			m_p = re.search('(?<=P)\w+', cmd)
			if m_p:
				self.progress_percent = int(m_p.group(0))

	def on_print_progress(self,storage,path,progress):		
		if not self.useM73:
			self.progress_percent = progress
			self.progress_remaining_minutes = int(((100-progress) * self.print_estimated_print_time / 60))
			pass

	def on_event(self,event,payload):			
		if event in "PrintStarted":
			self.print_started = datetime.now()
			self.print_duration = 0
			self.print_estimated_print_time = 0.0
			self.progress_percent = 0
			self.progress_remaining_minutes = 0
		if event in "PrintDone":
			self.print_done = datetime.now()
			self.print_duration = payload['time']


	def _worker(self):
		if datetime.now() < self.worker_wait_until:
			self._logger.info("waiting ...")
			return

		self.print_state = self._printer.get_state_string()
		current_job = self._printer.get_current_job()
		current_temps = self._printer.get_current_temperatures()


		if current_job:
			#self._logger.info("job: %s " % current_job)
			name = current_job['file']['name']
			ept = current_job['estimatedPrintTime']
			if name:
				self.print_name = name
			if ept:
				self.print_estimated_print_time = ept	
		if current_temps:
			self.temps = (
				current_temps['tool0']['actual'],
				current_temps['tool0']['target'],
				current_temps['bed']['actual'],
				current_temps['bed']['target']
			)

		self.update_overlay()
		

	def init_http_auth(self, base_url, auth_user, auth_passwd):
		passman = urllib.request.HTTPPasswordMgrWithDefaultRealm()
		passman.add_password(None, base_url, auth_user, auth_passwd)
		authhandler = urllib.request.HTTPDigestAuthHandler(passman)
		opener = urllib.request.build_opener(authhandler)
		urllib.request.install_opener(opener)		

	def initialize(self):
		host = self._settings.get(["host"])
		user = self._settings.get(["user"])
		password = self._settings.get(["password"])
		self.useM73 = self._settings.getBoolean(["useM73"])
		self.base_url = "http://%s%s" % (host, BASE_PARAM)
		self.init_http_auth(self.base_url, user, password)
		self.timer = octoprint.util.RepeatedTimer(UPDATE_INTERVAL, self._worker)
		self.timer.start()
		self.print_name = "BOOT: %s" % datetime.now().strftime("%y-%m-%d %H:%M")
		self._logger.info(self.print_name)


	def on_after_startup(self):
		self._logger.debug("DahuaCamOverlayPlugin started")

	def get_settings_defaults(self):
		return dict(
            host="localhost",
            user="admin",
            password="password",
            useM73=True)

	def get_template_configs(self):
		return [dict(type="settings", custom_bindings=False)]
	
	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
		# for details.
		return dict(
			dahuacamoverlay=dict(
				displayName="Dahuacamoverlay Plugin",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="hdo",
				repo="OctoPrint-DahuaCamOverlay",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/hdo/OctoPrint-DahuaCamOverlay/archive/{target_version}.zip"
			)
		)



__plugin_name__ = "Dahua Cam Overlay Plugin"
__plugin_pythoncompat__ = ">=3.7,<4"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = DahuaCamOverlayPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
		"octoprint.comm.protocol.gcode.sent": __plugin_implementation__.handle_m73,
	}

