from arm.ui import db


class UISettings(db.Model):
    """
    Class to hold the A.R.M ui settings
    """
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    use_icons = db.Column(db.Boolean)
    save_remote_images = db.Column(db.Boolean)
    bootstrap_skin = db.Column(db.String(64))
    language = db.Column(db.String(4))
    index_refresh = db.Column(db.Integer)
    database_limit = db.Column(db.Integer)
    notify_refresh = db.Column(db.Integer)
    show_job_ripper = db.Column(db.Boolean, nullable=False, default=True)
    show_job_rip_method = db.Column(db.Boolean, nullable=False, default=True)
    show_job_main_feature = db.Column(db.Boolean, nullable=False, default=True)
    show_job_min_length = db.Column(db.Boolean, nullable=False, default=True)
    show_job_max_length = db.Column(db.Boolean, nullable=False, default=True)
    device_display_mode = db.Column(db.String(16), nullable=False, default="coded")
    start_date_format = db.Column(db.String(16), nullable=False, default="MM/DD/YYYY")
    start_time_format = db.Column(db.String(8), nullable=False, default="12h")
    smart_title_matching_enabled = db.Column(db.Boolean, nullable=False, default=False)
    smart_title_matching_url = db.Column(db.String(512), nullable=False, default="http://ollama:11434")
    smart_title_matching_model = db.Column(db.String(128), nullable=False, default="qwen2.5:3b")

    def __init__(self, use_icons=None, save_remote_images=None,
                 bootstrap_skin=None, language=None, index_refresh=None,
                 database_limit=None, notify_refresh=None, show_job_ripper=True,
                 show_job_rip_method=True, show_job_main_feature=True,
                 show_job_min_length=True, show_job_max_length=True,
                 device_display_mode="coded", start_date_format="MM/DD/YYYY",
                 start_time_format="12h", smart_title_matching_enabled=False,
                 smart_title_matching_url="http://ollama:11434",
                 smart_title_matching_model="qwen2.5:3b"):
        self.use_icons = use_icons
        self.save_remote_images = save_remote_images
        self.bootstrap_skin = bootstrap_skin
        self.language = language
        self.index_refresh = index_refresh
        self.database_limit = database_limit
        self.notify_refresh = notify_refresh
        self.show_job_ripper = bool(show_job_ripper)
        self.show_job_rip_method = bool(show_job_rip_method)
        self.show_job_main_feature = bool(show_job_main_feature)
        self.show_job_min_length = bool(show_job_min_length)
        self.show_job_max_length = bool(show_job_max_length)
        self.device_display_mode = device_display_mode or "coded"
        self.start_date_format = start_date_format or "MM/DD/YYYY"
        self.start_time_format = start_time_format or "12h"
        self.smart_title_matching_enabled = bool(smart_title_matching_enabled)
        self.smart_title_matching_url = smart_title_matching_url or "http://ollama:11434"
        self.smart_title_matching_model = smart_title_matching_model or "qwen2.5:3b"

    def __repr__(self):
        return f'<UISettings {self.id}>'

    def __str__(self):
        """Returns a string of the object"""

        return_string = self.__class__.__name__ + ": "
        for attr, value in self.__dict__.items():
            return_string = return_string + "(" + str(attr) + "=" + str(value) + ") "

        return return_string

    def get_d(self):
        """ Returns a dict of the object"""
        return_dict = {}
        for key, value in self.__dict__.items():
            if '_sa_instance_state' not in key:
                return_dict[str(key)] = str(value)
        return return_dict
