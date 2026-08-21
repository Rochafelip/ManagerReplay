from server.monitor_status import (
    parse_cpu_pct,
    parse_ram,
    parse_temp,
    parse_clock_mhz,
    parse_throttled_flags,
    parse_external_storage_mounts,
)


def test_parse_cpu_pct_reads_idle_with_trailing_comma():
    line = "%Cpu(s):  8.2 us,  2.1 sy,  0.0 ni, 89.7 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st"

    assert parse_cpu_pct(line) == 10.3


def test_parse_cpu_pct_reads_idle_without_trailing_comma():
    line = "Cpu(s): 5.0%us, 1.0%sy, 0.0%ni, 94.0%id, 0.0%wa"

    assert parse_cpu_pct(line) == 6.0


def test_parse_ram_reads_used_and_total():
    output = (
        "              total        used        free      shared  buff/cache   available\n"
        "Mem:            955         178         400           5         377         700\n"
        "Swap:             0           0           0\n"
    )

    used, total = parse_ram(output)

    assert used == 178
    assert total == 955


def test_parse_temp_extracts_float():
    assert parse_temp("temp=41.9'C\n") == 41.9


def test_parse_clock_mhz_converts_hz_to_mhz():
    assert parse_clock_mhz("frequency(48)=1200000000\n") == 1200


def test_parse_throttled_flags_all_clear():
    flags = parse_throttled_flags("throttled=0x0\n")

    assert flags == {
        "undervoltage_now": False,
        "freq_capped_now": False,
        "throttled_now": False,
        "undervoltage_ever": False,
    }


def test_parse_throttled_flags_undervoltage_now_and_ever():
    # bit 0 (undervoltage now) + bit 16 (undervoltage ever) set
    flags = parse_throttled_flags("throttled=0x10001\n")

    assert flags["undervoltage_now"] is True
    assert flags["undervoltage_ever"] is True
    assert flags["freq_capped_now"] is False
    assert flags["throttled_now"] is False


def test_parse_external_storage_mounts_picks_out_sdx_devices():
    mounts = (
        "/dev/mmcblk0p2 / ext4 rw,noatime 0 0\n"
        "/dev/mmcblk0p1 /boot vfat rw,relatime 0 2\n"
        "/dev/sda1 /media/rocha/SSD1 ext4 rw,nosuid,nodev,relatime 0 0\n"
        "tmpfs /run tmpfs rw,nosuid,size=98040k,mode=755 0 0\n"
    )

    devices = parse_external_storage_mounts(mounts)

    assert devices == [{"device": "/dev/sda1", "mountpoint": "/media/rocha/SSD1", "fstype": "ext4"}]


def test_parse_external_storage_mounts_returns_empty_when_only_sd_card(tmp_path):
    mounts = (
        "/dev/mmcblk0p2 / ext4 rw,noatime 0 0\n"
        "/dev/mmcblk0p1 /boot vfat rw,relatime 0 2\n"
    )

    assert parse_external_storage_mounts(mounts) == []


def test_parse_external_storage_mounts_supports_multiple_devices():
    mounts = (
        "/dev/sda1 /media/rocha/SSD1 ext4 rw 0 0\n"
        "/dev/sdb1 /media/rocha/PENDRIVE vfat rw 0 0\n"
    )

    devices = parse_external_storage_mounts(mounts)

    assert [d["device"] for d in devices] == ["/dev/sda1", "/dev/sdb1"]
