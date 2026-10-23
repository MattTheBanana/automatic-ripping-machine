import arm.config.config as cfg
from arm.models.job import Job


def test_hybrid_bluray_is_not_misclassified_as_dvd(tmp_path, monkeypatch):
    (tmp_path / "BDMV").mkdir()
    (tmp_path / "VIDEO_TS").mkdir()

    # Keep the test independent of actual optical-drive hardware.
    def fake_parse_udev(job):
        job.disctype = "dvd"
        job.label = "test-disc"

    monkeypatch.setattr(Job, "parse_udev", fake_parse_udev)
    monkeypatch.setitem(cfg.arm_config, "VIDEOTYPE", "auto")

    job = Job(devpath="/dev/test")
    job.mountpoint = str(tmp_path)

    job.get_disc_type(found_hvdvd_ts=False)

    assert job.disctype == "bluray"
