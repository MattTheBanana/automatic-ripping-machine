import yaml

from arm.config.config_utils import arm_yaml_test_bool


def test_arm_yaml_test_bool_round_trips_special_characters():
    values = [
        'title: with colon',
        'quote " and apostrophe \'',
        'line one\nline two',
        'true',
        'false',
        '',
    ]

    for value in values:
        rendered = arm_yaml_test_bool('TEST_VALUE', value)
        assert yaml.safe_load(rendered)['TEST_VALUE'] == value


def test_arm_yaml_test_bool_keeps_boolean_and_ip_conventions():
    assert arm_yaml_test_bool('FLAG', 'TRUE') == 'FLAG: true\n'
    assert arm_yaml_test_bool('WEBSERVER_IP', 'X.X.X.X') == 'WEBSERVER_IP: x.x.x.x\n'
