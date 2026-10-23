from arm.models.job import Job


def test_hybrid_bluray_is_not_misclassified_as_dvd(tmp_path):
    (tmp_path / "BDMV").mkdir()
    (tmp_path / "VIDEO_TS").mkdir()
    job = Job(mountpoint=str(tmp_path), disctype="dvd")

    job.get_disc_type(found_hvdvd_ts=False)

    assert job.disctype == "bluray"
