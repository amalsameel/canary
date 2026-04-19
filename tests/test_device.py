from canary.device import DeviceProfile


def test_device_profile_recommends_local_for_apple_silicon():
    profile = DeviceProfile(
        system="Darwin",
        machine="arm64",
        cpu_count=8,
        memory_gb=16,
        has_discrete_gpu_hint=False,
        apple_silicon=True,
    )
    assert profile.local_recommended
    assert profile.recommended_mode == "local"


def test_device_profile_warns_for_small_cpu_machine():
    profile = DeviceProfile(
        system="Linux",
        machine="x86_64",
        cpu_count=4,
        memory_gb=8,
        has_discrete_gpu_hint=False,
        apple_silicon=False,
    )
    assert profile.local_warning
    assert profile.recommended_mode == "online"
