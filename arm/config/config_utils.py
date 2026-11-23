import yaml


def arm_yaml_check_groups(comments, key):
    """
    Check the current key to be added to arm.yaml and insert the group
    separator comment, if the key matches.
    """
    comment_groups = {'COMPLETED_PATH': "\n" + comments['ARM_CFG_GROUPS']['DIR_SETUP'],
                      'WEBSERVER_IP': "\n" + comments['ARM_CFG_GROUPS']['WEB_SERVER'],
                      'SET_MEDIA_PERMISSIONS': "\n" + comments['ARM_CFG_GROUPS']['FILE_PERMS'],
                      'RIPMETHOD': "\n" + comments['ARM_CFG_GROUPS']['MAKE_MKV'],
                      'HB_PRESET_DVD': "\n" + comments['ARM_CFG_GROUPS']['HANDBRAKE'],
                      'EMBY_REFRESH': "\n" + comments['ARM_CFG_GROUPS']['EMBY']
                                      + "\n" + comments['ARM_CFG_GROUPS']['EMBY_ADDITIONAL'],
                      'NOTIFY_RIP': "\n" + comments['ARM_CFG_GROUPS']['NOTIFY_PERMS'],
                      'APPRISE': "\n" + comments['ARM_CFG_GROUPS']['APPRISE']}
    return comment_groups.get(key, "")


def arm_yaml_test_bool(key, value):
    """
    Serialize one ARM config value as a valid YAML scalar.

    Boolean values and WEBSERVER_IP retain their established unquoted form.
    All other values are quoted by PyYAML so embedded quotes, colons, and
    newlines cannot corrupt the generated arm.yaml file.
    """
    if value.lower() in ('false', 'true'):
        return f"{key}: {value.lower()}\n"
    if key == "WEBSERVER_IP":
        return f"{key}: {value.lower()}\n"

    scalar = yaml.safe_dump(value, default_style='"', default_flow_style=True).splitlines()[0]
    return f"{key}: {scalar}\n"
