import os
import json
import urllib.request
import webbrowser
import wx
import gui
import config
from logHandler import log
import globalPluginHandler
import languageHandler
import gettext

# Yerelleştirme Mekanizması - Kesin Çözüm
_addonDir = os.path.join(os.path.dirname(__file__), "..")
_locDir = os.path.join(_addonDir, "locale")
_lang = languageHandler.getLanguage()

try:
	_trans = gettext.translation("nvda", localedir=_locDir, languages=[_lang])
	_ = _trans.gettext
except Exception:
	_ = lambda s: s

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super(GlobalPlugin, self).__init__()
		self.menu = gui.mainFrame.sysTrayIcon.menu
		self.item = self.menu.Append(wx.ID_ANY, _("GitLab Manager..."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.on_manager_open, self.item)
		
		if "gitlab" not in config.conf:
			config.conf["gitlab"] = {"token": "", "url": "https://gitlab.com/api/v4"}

	def on_manager_open(self, event):
		token = config.conf["gitlab"]["token"]
		if not token:
			dlg = GitLabSettingsDialog(gui.mainFrame)
			if dlg.ShowModal() == wx.ID_OK:
				wx.CallAfter(self.on_manager_open, None)
			return
		repos = self.fetch_repos(token)
		if repos:
			dlg = GitLabManagerDialog(gui.mainFrame, repos)
			dlg.ShowModal()

	def fetch_repos(self, token):
		api_url = config.conf["gitlab"]["url"]
		headers = {"PRIVATE-TOKEN": token}
		req = urllib.request.Request(f"{api_url}/projects?owned=true&per_page=100&simple=true", headers=headers)
		try:
			with urllib.request.urlopen(req) as response:
				return json.loads(response.read().decode())
		except Exception as e:
			log.error(f"GitLab API Error: {e}")
			gui.messageBox(_("Failed to fetch repositories. Please check your token."), _("Error"))
			return None

class CreateRepoDialog(wx.Dialog):
	def __init__(self, parent):
		super(CreateRepoDialog, self).__init__(parent, title=_("Create New Repository"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		sizer.Add(wx.StaticText(self, label=_("Repository &Name:")), 0, wx.ALL, 5)
		self.name_txt = wx.TextCtrl(self)
		sizer.Add(self.name_txt, 0, wx.EXPAND | wx.ALL, 5)
		
		sizer.Add(wx.StaticText(self, label=_("&Description:")), 0, wx.ALL, 5)
		self.desc_txt = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 60))
		sizer.Add(self.desc_txt, 0, wx.EXPAND | wx.ALL, 5)
		
		sizer.Add(wx.StaticText(self, label=_("&Visibility:")), 0, wx.ALL, 5)
		self.visibility_cb = wx.Choice(self, choices=["private", "internal", "public"])
		self.visibility_cb.SetSelection(0)
		sizer.Add(self.visibility_cb, 0, wx.EXPAND | wx.ALL, 5)
		
		self.readme_chk = wx.CheckBox(self, label=_("Initialize with a &README"))
		sizer.Add(self.readme_chk, 0, wx.ALL, 5)
		
		sizer.Add(wx.StaticText(self, label=_("&License:")), 0, wx.ALL, 5)
		self.lic_choices = ["none", "mit", "gpl-3.0", "apache-2.0"]
		self.license_cb = wx.Choice(self, choices=[_("none"), _("mit"), _("gpl-3.0"), _("apache-2.0")])
		self.license_cb.SetSelection(0)
		sizer.Add(self.license_cb, 0, wx.EXPAND | wx.ALL, 5)
		
		btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
		sizer.Add(btns, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		self.SetSizer(sizer)
		sizer.Fit(self)

class GitLabManagerDialog(wx.Dialog):
	def __init__(self, parent, repos):
		super(GitLabManagerDialog, self).__init__(parent, title=_("GitLab Manager"))
		self.repos = repos
		sizer = wx.BoxSizer(wx.VERTICAL)
		
		sizer.Add(wx.StaticText(self, label=_("&Repositories:")), 0, wx.ALL, 5)
		self.repo_list = wx.ListBox(self, choices=[r['name'] for r in repos])
		sizer.Add(self.repo_list, 1, wx.EXPAND | wx.ALL, 10)
		
		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.open_btn = wx.Button(self, label=_("&Open in Browser"))
		self.open_btn.Bind(wx.EVT_BUTTON, self.on_open)
		btn_sizer.Add(self.open_btn, 0, wx.ALL, 5)
		
		self.create_btn = wx.Button(self, label=_("&Create New..."))
		self.create_btn.Bind(wx.EVT_BUTTON, self.on_create_new)
		btn_sizer.Add(self.create_btn, 0, wx.ALL, 5)
		
		btn_sizer.Add(wx.Button(self, wx.ID_CLOSE, label=_("&Close")), 0, wx.ALL, 5)
		sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		self.SetSizer(sizer)
		self.repo_list.SetFocus()

	def on_open(self, event):
		idx = self.repo_list.GetSelection()
		if idx != wx.NOT_FOUND:
			webbrowser.open(self.repos[idx]['web_url'])

	def on_create_new(self, event):
		dlg = CreateRepoDialog(self)
		if dlg.ShowModal() == wx.ID_OK:
			data = {
				"name": dlg.name_txt.GetValue(),
				"description": dlg.desc_txt.GetValue(),
				"visibility": dlg.visibility_cb.GetStringSelection(),
				"initialize_with_readme": dlg.readme_chk.IsChecked()
			}
			lic = dlg.lic_choices[dlg.license_cb.GetSelection()]
			if lic != "none": data["license_template"] = lic
			self._do_api_create(data)

	def _do_api_create(self, data):
		token = config.conf["gitlab"]["token"]
		api_url = config.conf["gitlab"]["url"]
		post_data = json.dumps(data).encode("utf-8")
		headers = {"PRIVATE-TOKEN": token, "Content-Type": "application/json"}
		req = urllib.request.Request(f"{api_url}/projects", data=post_data, headers=headers, method="POST")
		try:
			urllib.request.urlopen(req)
			gui.messageBox(_("Repository created successfully."), _("Success"))
			self.EndModal(wx.ID_OK)
		except:
			gui.messageBox(_("Failed to create repository."), _("Error"))

class GitLabSettingsDialog(wx.Dialog):
	def __init__(self, parent):
		super(GitLabSettingsDialog, self).__init__(parent, title=_("GitLab Settings"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(self, label=_("Personal Access &Token:")), 0, wx.ALL, 5)
		self.token_txt = wx.TextCtrl(self, value=config.conf["gitlab"]["token"], style=wx.TE_PASSWORD)
		sizer.Add(self.token_txt, 0, wx.EXPAND | wx.ALL, 5)
		btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
		sizer.Add(btns, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		self.SetSizer(sizer)

	def EndModal(self, retCode):
		if retCode == wx.ID_OK:
			config.conf["gitlab"]["token"] = self.token_txt.GetValue()
		super().EndModal(retCode)