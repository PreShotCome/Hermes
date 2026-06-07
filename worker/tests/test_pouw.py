"""Tests for the Pearl PoUW reference engine.

These prove the engine does *real, correct* work: the noised tiled GEMM
reproduces the plain matrix product, the commitment binds data + header, and the
keyed-transcript search actually finds solutions at an easy target and rejects
them at the hardest target.
"""

from __future__ import annotations

import numpy as np

from pearl_worker import pouw


def _problem(seed: int = 0, m: int = 256, n: int = 256, k: int = 256, rank: int = 128):
    rng = np.random.default_rng(seed)
    a = rng.integers(-64, 64, size=(m, k), dtype=np.int8)
    b = rng.integers(-64, 64, size=(k, n), dtype=np.int8)
    cfg = pouw.MiningConfig(common_dim=k, rank=rank)
    header = b"pearl-test-header" + seed.to_bytes(4, "little")
    seed_a, seed_b = pouw.commitment(a, b, header, cfg)
    noise = pouw.NoiseGenerator(noise_rank=rank).generate(seed_a, seed_b, m, k, n)
    return a, b, cfg, header, seed_a, seed_b, noise


def test_noised_gemm_reproduces_plain_matmul():
    a, b, cfg, _header, seed_a, _seed_b, noise = _problem()
    c, _ = pouw.noisy_gemm_pow(a, b, noise, seed_a, pouw.MAX_TARGET, cfg)
    assert np.array_equal(c, a.astype(np.int32) @ b.astype(np.int32))


def test_easiest_target_always_finds_a_solution():
    a, b, cfg, _header, seed_a, _seed_b, noise = _problem(seed=1)
    _, solution = pouw.noisy_gemm_pow(a, b, noise, seed_a, pouw.MAX_TARGET, cfg)
    assert solution is not None
    assert solution.pow_hash_int <= pouw.MAX_TARGET
    assert len(solution.transcript) == pouw.TRANSCRIPT_SIZE_U32


def test_hardest_target_finds_nothing():
    a, b, cfg, _header, seed_a, _seed_b, noise = _problem(seed=2)
    _, solution = pouw.noisy_gemm_pow(a, b, noise, seed_a, 0, cfg)
    assert solution is None


def test_solution_is_independently_verifiable():
    a, b, cfg, header, seed_a, _seed_b, noise = _problem(seed=3)
    target = pouw.MAX_TARGET
    _, solution = pouw.noisy_gemm_pow(a, b, noise, seed_a, target, cfg)
    assert solution is not None
    # Re-derive the commitment from the data + header and re-hash the claimed
    # transcript: a verifier with only (A, B, header, transcript) agrees.
    re_seed_a, _ = pouw.commitment(a, b, header, cfg)
    assert re_seed_a == seed_a
    from blake3 import blake3

    transcript = np.array(solution.transcript, dtype=np.uint32)
    digest = blake3(transcript.astype("<u4").tobytes(), key=re_seed_a).digest()
    assert int.from_bytes(digest, "little") == solution.pow_hash_int
    assert solution.pow_hash_int <= target


def test_commitment_binds_header():
    a, b, cfg, _header, seed_a, _seed_b, _noise = _problem(seed=4)
    other_a, _ = pouw.commitment(a, b, b"different-header", cfg)
    assert other_a != seed_a


def test_noise_low_rank_stays_in_int8_range():
    _, _, _cfg, _header, seed_a, seed_b, noise = _problem(seed=5)
    e_al, e_ar, e_bl, e_br = noise
    e_a = e_al.astype(np.int32) @ e_ar.astype(np.int32)
    e_b = e_bl.astype(np.int32) @ e_br.astype(np.int32)
    assert e_a.min() >= -128 and e_a.max() <= 127
    assert e_b.min() >= -128 and e_b.max() <= 127
