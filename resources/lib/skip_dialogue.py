import xbmcgui, xbmc, xbmcaddon

import helper.utils as utils
from helper import LazyLogger

OK_BUTTON = 2101
DISMISS_BUTTON = 2102

ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
INSTRUCTION_LABEL = 203
AUTHCODE_LABEL = 204
WARNING_LABEL = 205
CENTER_Y = 6
CENTER_X = 2

MIN_REMAINING_SECONDS = 5
AUTOSKIP = None
NETFLIX_STYLE = None
NETFLIX_COUNTDOWN = None
LOG = LazyLogger(__name__)

class SkipSegmentDialogue(xbmcgui.WindowXMLDialog):

    def __init__(self, xmlFile, resourcePath, seek_time_seconds, segment_type):
        self.seek_time_seconds = seek_time_seconds
        self.segment_type = segment_type
        self.player = xbmc.Player()
        self._countdown_cancel = False
        self._netflix_active = False

    def onInit(self):
        # Read current settings at runtime so changes take effect immediately
        try:
            addon = xbmcaddon.Addon('service.jellyskip')
            # Prefer new enum setting `skip_mode` if present (0=Autoskip,1=Netflix-style)
            try:
                skip_mode = addon.getSettingInt('skip_mode')
                autoskip = (skip_mode == 0)
                netflix_style = (skip_mode == 1)
            except Exception:
                # fallback to older boolean settings
                autoskip = bool(addon.getSettingBool('autoskip'))
                netflix_style = bool(addon.getSettingBool('netflix_style'))

            try:
                netflix_countdown = addon.getSettingInt('netflix_countdown')
            except Exception:
                netflix_countdown = int(addon.getSetting('netflix_countdown') or 3)
        except Exception:
            autoskip = False
            netflix_style = False
            netflix_countdown = 3

        if autoskip:
            self.onClick(OK_BUTTON)
            return

        skip_button = self.getControl(OK_BUTTON)
        # try to get dismiss button (added to skin)
        try:
            dismiss_button = self.getControl(DISMISS_BUTTON)
        except Exception:
            dismiss_button = None

        if netflix_style:
            total = max(1, int(netflix_countdown))

            def countdown():
                steps = 12
                interval = float(total) / steps
                for i in range(steps + 1):
                    if getattr(self, '_countdown_cancel', False):
                        # cancelled by dismiss
                        return
                    remaining = max(0, int(round(total - (i * interval))))
                    try:
                        label = "Skip {}  {}s".format(self.segment_type, remaining)
                        skip_button.setLabel(label)
                    except Exception:
                        pass
                    xbmc.sleep(int(interval * 1000))

                try:
                    if getattr(self, '_countdown_cancel', False):
                        return
                    if self.player.isPlaying():
                        self.onClick(OK_BUTTON)
                except Exception:
                    pass

            try:
                skip_button.setLabel('Skip ' + str(self.segment_type))
            except Exception:
                pass

            # mark netflix countdown active so focus events can cancel it
            self._countdown_cancel = False
            self._netflix_active = True

            # set dismiss label if available
            try:
                if dismiss_button:
                    try:
                        dismiss_label = addon.getLocalizedString(30022)
                    except Exception:
                        dismiss_label = 'Dismiss'
                    dismiss_button.setLabel(dismiss_label)
            except Exception:
                pass

            utils.run_threaded(countdown)
            self.schedule_close_action()
            return

        # default behaviour: static button
        skip_label = 'Skip ' + str(self.segment_type)
        try:
            skip_button.setLabel(skip_label)
        except Exception:
            pass
        self.schedule_close_action()

    def get_seconds_till_segment_end(self):
        return self.seek_time_seconds - self.player.getTime()

    def schedule_close_action(self):
        """
        Schedule the dialog to close automatically when the segment ends.
        :return: None
        """

        seconds_till_segment_end = self.get_seconds_till_segment_end()

        if seconds_till_segment_end > 0:
            utils.run_threaded(self.on_automatic_close, delay=seconds_till_segment_end, kwargs={})

    def on_automatic_close(self):
        """
        Close the dialog automatically. This is called by the scheduled thread.
        :return: None
        """

        self.close()

        LOG.info("JellySkip: Auto closing dialogue")
        sender = "service.jellyskip"
        xbmc.executebuiltin("NotifyAll(%s, %s, %s)" % (sender, "Jellyskip.DialogueClosed", {}))

    def onAction(self, action):
        if action == ACTION_PREVIOUS_MENU or action == ACTION_BACK:
            self.close()

    def onControl(self, control):
        pass

    def onFocus(self, control):
        try:
            # control may be an int id or control object
            try:
                cid = control.getId()
            except Exception:
                cid = int(control)
        except Exception:
            return

        # If netflix countdown is active and focus moved away from Skip button, cancel autoskip
        if getattr(self, '_netflix_active', False) and cid != OK_BUTTON:
            try:
                self._countdown_cancel = True
                self._netflix_active = False
            except Exception:
                pass

    def onClick(self, control):
        if not self.player.isPlaying():
            self.close()
            return

        if control == DISMISS_BUTTON:
            # cancel any running countdown and dismiss without skipping
            try:
                self._countdown_cancel = True
            except Exception:
                pass
            self.close()
            return

        if control == OK_BUTTON:
            remaining_seconds = self.player.getTotalTime() - self.seek_time_seconds

            # We don't want to skip to the end of the video (give other addons time to play, like nextup service)
            if remaining_seconds < MIN_REMAINING_SECONDS:
                self.player.seekTime(self.player.getTotalTime() - MIN_REMAINING_SECONDS)
                self.close()
            else:
                self.player.seekTime(self.seek_time_seconds)

        self.close()
