"""Shared DSP for air-gap covert channel labs."""

from .framing import (
    add_crc16,
    bits_to_bytes,
    bytes_to_bits,
    check_crc16,
    decode_payload,
    encode_payload,
    hamming74_decode,
    hamming74_encode,
)
from .modulation import (
    ask_demod,
    ask_mod,
    bpsk_demod,
    bpsk_mod,
    find_preamble,
    fsk_demod,
    fsk_mod,
    nrz_decode,
    nrz_encode,
)
from .channel import awgn_channel, ber, covert_channel_sim, fading_channel, multipath_channel
from .metrics import save_result

__all__ = [
    "bytes_to_bits",
    "bits_to_bytes",
    "add_crc16",
    "check_crc16",
    "hamming74_encode",
    "hamming74_decode",
    "encode_payload",
    "decode_payload",
    "bpsk_mod",
    "bpsk_demod",
    "fsk_mod",
    "fsk_demod",
    "ask_mod",
    "ask_demod",
    "nrz_encode",
    "nrz_decode",
    "awgn_channel",
    "multipath_channel",
    "fading_channel",
    "covert_channel_sim",
    "ber",
    "save_result",
    "find_preamble",
]
