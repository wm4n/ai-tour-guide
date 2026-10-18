from buddy_host.narration.memory import parse_swap_used_bytes, parse_vm_stat_used_bytes

VM_STAT = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                               10000.
Pages active:                            200000.
Pages inactive:                          150000.
Pages speculative:                         5000.
Pages throttled:                              0.
Pages wired down:                         100000.
Pages purgeable:                           3000.
Pages occupied by compressor:              50000.
"""


def test_used_is_active_plus_wired_plus_compressor():
    assert parse_vm_stat_used_bytes(VM_STAT) == (200000 + 100000 + 50000) * 16384


def test_swap_used_in_megabytes():
    out = "total = 2048.00M  used = 1024.50M  free = 1023.50M  (encrypted)"

    assert parse_swap_used_bytes(out) == int(1024.5 * 1024 * 1024)


def test_swap_used_in_gigabytes_and_zero():
    assert parse_swap_used_bytes("total = 3.00G  used = 1.50G  free = 1.50G") == int(1.5 * 1024**3)
    assert parse_swap_used_bytes("total = 0.00M  used = 0.00M  free = 0.00M") == 0


def test_unexpected_vm_stat_output_is_a_clear_error():
    import pytest

    with pytest.raises(ValueError, match="vm_stat"):
        parse_vm_stat_used_bytes("something else entirely")
