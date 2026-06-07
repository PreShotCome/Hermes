"""Pearl Proof-of-Useful-Work — a faithful, dependency-light reference engine.

Pearl secures its chain with *useful* work: instead of hashing nonces, a miner
runs a large int8 matrix multiplication (the same GEMM that underlies AI
inference), accumulates a keyed BLAKE3 *transcript* over the output tiles, and
wins a block when a tile's transcript hash falls below the network target.

This module re-implements that computation in pure ``numpy`` + ``blake3`` so the
worker does real, locally-verifiable Pearl work on any machine — no GPU, no
CUDA, no compiled ``pearl_mining`` extension required. It mirrors the upstream
algorithm in ``pearl-research-labs/pearl`` (``miner/miner-base``):

    noise matrices  ->  noised A, B  ->  tiled int8 GEMM
                    ->  per-tile XOR inner hash  ->  rotl-xor transcript
                    ->  keyed BLAKE3(transcript) <= target  ->  block found

The numbers it produces (matmul throughput, solutions found) are real. What it
does *not* do in reference mode is wrap the solution in a Plonky2 ZK proof and
submit it to a live ``pearld`` node — that is the job of ``live`` mode, which
delegates to the real ``pearl_mining`` bindings and ``pearl-gateway``.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np
from blake3 import blake3

# --- protocol constants (match upstream miner-base defaults) -----------------

NOISE_RANGE = 128  # noise values fit in uint7; data range is (256 - NOISE_RANGE)
HASH_ACCUMULATE_ROTATION = 13
TRANSCRIPT_SIZE_U32 = 16  # 64-byte transcript == blake3 message block
MAX_TARGET = 2**256 - 1

UINT32 = np.uint32(0xFFFFFFFF)


@dataclass(frozen=True)
class MiningConfig:
    """The shape of one mining problem. Bound into the commitment key."""

    common_dim: int  # k — the contracted dimension
    rank: int  # low-rank noise rank (also the matmul tile size over k)
    hash_tile_h: int = 16
    hash_tile_w: int = 16

    def to_bytes(self) -> bytes:
        # Stable serialization so the commitment key is reproducible by verifiers.
        return struct.pack(
            "<IIII", self.common_dim, self.rank, self.hash_tile_h, self.hash_tile_w
        )


@dataclass
class Solution:
    """A found Pearl block: the tile that won and enough to re-verify it."""

    row: int
    col: int
    transcript: list[int]
    pow_hash_int: int
    target: int
    seed_a: bytes
    seed_b: bytes


# --- bit twiddling -----------------------------------------------------------


def _mul_hi_u32(a: np.uint32, b: np.uint32) -> np.uint32:
    return np.uint32((np.uint64(a) * np.uint64(b)) >> np.uint64(32))


def _imatmul(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Exact integer matmul via BLAS.

    numpy has no optimized (BLAS) kernel for integer matmul — it falls back to a
    slow generic loop. Routing through floating point hits BLAS and is ~30x
    faster on CPU. We pick the smallest float dtype that represents the result
    *exactly* (no rounding): float32 is integer-exact below 2**24, float64 below
    2**53. The bound below is conservative, so the result is always exact.
    """
    if x.size == 0 or y.size == 0:
        return (x.astype(np.int32) @ y.astype(np.int32)).astype(np.int32)
    bound = int(np.abs(x).max()) * int(np.abs(y).max()) * x.shape[1]
    dtype = np.float32 if bound < (1 << 24) else np.float64
    return (x.astype(dtype) @ y.astype(dtype)).astype(np.int32)


# --- commitment --------------------------------------------------------------


def _matrix_root(mat: np.ndarray, key: bytes) -> bytes:
    """Keyed BLAKE3 of an int8 matrix (the CPU commitment hash upstream uses)."""
    return blake3(np.ascontiguousarray(mat, dtype=np.int8).tobytes(), key=key).digest()


def commitment(
    a: np.ndarray, b: np.ndarray, header_bytes: bytes, cfg: MiningConfig
) -> tuple[bytes, bytes]:
    """Derive (seed_A, seed_B) binding the data A, B and the block header.

    Mirrors ``CommitmentHasher``: a key over (header || config), Merkle/keyed
    hashes of A and B^T, then a two-step commitment chain. Binding the noise
    seeds to the committed data is what stops a miner from grinding noise for
    free — every attempt must commit to a real matmul input.
    """
    key = blake3(header_bytes + cfg.to_bytes()).digest()
    root_a = _matrix_root(a, key)
    root_b = _matrix_root(np.ascontiguousarray(b.T), key)
    commitment_b = blake3(key + root_b).digest()
    commitment_a = blake3(commitment_b + root_a).digest()
    return commitment_a, commitment_b  # (seed_A == pow_key, seed_B)


# --- noise generation (port of miner_base.noise_generation.NoiseGenerator) ---


class NoiseGenerator:
    """Deterministic low-rank int8 noise derived from the commitment seeds."""

    def __init__(self, noise_rank: int = 128, noise_range: int = NOISE_RANGE) -> None:
        if noise_rank & (noise_rank - 1) or noise_rank == 0:
            raise ValueError("noise_rank must be a power of two")
        if noise_range & (noise_range - 1) or noise_range == 0:
            raise ValueError("noise_range must be a power of two")
        if noise_rank % 32 != 0:
            raise ValueError("noise_rank must be divisible by blake3 digest size (32)")
        self.noise_rank = noise_rank
        # upstream: _noise_range = noise_range // 2; zero_point = _noise_range // 2
        _noise_range = noise_range // 2
        self.zero_point = _noise_range // 2
        self.range_mask = _noise_range - 1
        self.rank_mask = noise_rank - 1

    def _hash(self, index: int, seed: bytes, key: bytes, prepend_index: int) -> bytes:
        prep = np.zeros(8, dtype=np.int32)
        prep[prepend_index] = 1 + index
        return blake3(prep.tobytes() + seed, key=key).digest()

    def _uniform(self, seed: bytes, key: bytes, rows: int) -> np.ndarray:
        cols = self.noise_rank
        draws = -(-rows * cols // 32)  # ceil
        raw = b"".join(self._hash(i, seed, key, 0) for i in range(draws))
        arr = np.frombuffer(raw, dtype=np.uint8)[: rows * cols].astype(np.int16)
        vals = (arr & self.range_mask) - self.zero_point
        return vals.astype(np.int8).reshape(rows, cols)

    def _permutation(
        self, seed: bytes, key: bytes, rows: int, cols: int, assign_columns: bool
    ) -> np.ndarray:
        out = np.zeros((rows, cols), dtype=np.int8)
        required = cols if assign_columns else rows
        draws = -(-required * 4 // 32)  # ceil(required*4 / 32)
        raw = b"".join(self._hash(i, seed, key, 1) for i in range(draws))
        # One word per line; each places a +1 and a -1 in its rank-length vector.
        words = np.frombuffer(raw, dtype=np.uint32)[:required]
        mask = np.uint32(self.rank_mask)
        first_u = words & mask
        mul_hi = (
            (np.uint64(self.noise_rank - 1) * words.astype(np.uint64)) >> np.uint64(32)
        ).astype(np.uint32)
        second_u = (first_u ^ (np.uint32(1) + mul_hi)) & mask
        first = first_u.astype(np.intp)
        second = second_u.astype(np.intp)
        lines = np.arange(required)
        if assign_columns:  # vectors are columns: out[row, line]
            out[first, lines] = 1
            out[second, lines] = -1
        else:  # vectors are rows: out[line, col]
            out[lines, first] = 1
            out[lines, second] = -1
        return out

    def generate(
        self, seed_a: bytes, seed_b: bytes, m: int, k: int, n: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        sa = (b"A_tensor" + b"\x00" * 24)[:32]
        sb = (b"B_tensor" + b"\x00" * 24)[:32]
        e_al = self._uniform(sa, seed_a, m)
        e_ar = self._permutation(sa, seed_a, self.noise_rank, k, assign_columns=True)
        e_bl = self._permutation(sb, seed_b, k, self.noise_rank, assign_columns=False)
        e_br = self._uniform(sb, seed_b, n).T
        return e_al, e_ar, e_bl, e_br


# --- the proof-of-useful-work search ----------------------------------------


def _inner_hash_all_tiles(c: np.ndarray, hth: int, htw: int) -> np.ndarray:
    """XOR-reduce every hash tile of an int32 matrix at once.

    Returns an ``(n_tiles_h, n_tiles_w)`` uint32 array — one combined word per
    hash tile — in a single vectorized numpy pass (no per-tile Python loop).
    """
    nth, ntw = c.shape[0] // hth, c.shape[1] // htw
    grouped = c.view(np.uint32).reshape(nth, hth, ntw, htw)
    return np.bitwise_xor.reduce(grouped, axis=(1, 3))


def _rotl32_arr(x: np.ndarray) -> np.ndarray:
    n = np.uint32(HASH_ACCUMULATE_ROTATION)
    return (x << n) | (x >> np.uint32(32 - HASH_ACCUMULATE_ROTATION))


def noisy_gemm_pow(
    a: np.ndarray,
    b: np.ndarray,
    noise: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    pow_key: bytes,
    target: int,
    cfg: MiningConfig,
    *,
    compute_product: bool = False,
) -> tuple[np.ndarray | None, Solution | None]:
    """Run the noised tiled GEMM and search its transcripts for a winning tile.

    The hot path is fully vectorized: one BLAS matmul per k-reduction over the
    *whole* output, then a single numpy pass to fold every hash tile into its
    transcript. Output-element partial sums are independent of tiling, so this is
    identical to the per-output-tile upstream loop for aligned shapes — but with
    almost no Python overhead.

    By default it does **only** the work the proof needs: the noised matmul and
    the transcript search. Pass ``compute_product=True`` to also return the
    denoised product C (== A @ B); skip it in the mining loop to avoid three
    redundant matmuls per attempt.

    Requires m and n divisible by ``rank`` and ``rank`` divisible by the hash
    tile size (the reference engine's defaults satisfy this).
    """
    e_al, e_ar, e_bl, e_br = noise
    rank = cfg.rank
    m, k = a.shape
    n = b.shape[1]
    hth, htw = cfg.hash_tile_h, cfg.hash_tile_w
    if m % rank or n % rank or rank % hth or rank % htw:
        raise ValueError("reference engine requires rank-aligned m, n and tile-aligned rank")

    # Noise the inputs (int8). These two small products are the only matmuls
    # besides the PoUW matmul itself.
    e_a = _imatmul(e_al, e_ar).astype(np.int8)
    e_b = _imatmul(e_bl, e_br).astype(np.int8)
    a_n = np.ascontiguousarray(a + e_a, dtype=np.int8)
    b_n = np.ascontiguousarray(b + e_b, dtype=np.int8)

    nth, ntw = m // hth, n // htw
    transcripts = np.zeros((nth, ntw, TRANSCRIPT_SIZE_U32), dtype=np.uint32)
    c = np.zeros((m, n), dtype=np.int32)
    for reduction, p in enumerate(range(0, k, rank)):
        c += _imatmul(a_n[:, p : p + rank], b_n[p : p + rank, :])
        combined = _inner_hash_all_tiles(c, hth, htw)  # (nth, ntw) uint32
        idx = reduction % TRANSCRIPT_SIZE_U32
        transcripts[:, :, idx] = _rotl32_arr(transcripts[:, :, idx]) ^ combined

    # PoW check: keyed BLAKE3 over each 64-byte transcript, scanned in order.
    flat = transcripts.reshape(-1, TRANSCRIPT_SIZE_U32).astype("<u4")
    solution: Solution | None = None
    for t in range(flat.shape[0]):
        h = int.from_bytes(blake3(flat[t].tobytes(), key=pow_key).digest(), "little")
        if h <= target:
            solution = Solution(
                row=(t // ntw) * hth,
                col=(t % ntw) * htw,
                transcript=[int(x) for x in flat[t]],
                pow_hash_int=h,
                target=target,
                seed_a=pow_key,
                seed_b=b"",
            )
            break

    product = denoise_product(a, b, c, noise) if compute_product else None
    return product, solution


def denoise_product(
    a: np.ndarray,
    b: np.ndarray,
    c_noised: np.ndarray,
    noise: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
) -> np.ndarray:
    """Recover the true product C == A @ B from the noised accumulation.

    Used for verification/tests and, in a real miner, to consume the useful AI
    output — but never needed just to search for a solution.
    """
    e_al, e_ar, e_bl, e_br = noise
    e_b = _imatmul(e_bl, e_br).astype(np.int8)
    b_n = (b + e_b).astype(np.int8)
    a_ebl = _imatmul(a, e_bl)
    ear_bn = _imatmul(e_ar, b_n)
    denoise = _imatmul(a_ebl, e_br) + _imatmul(e_al, ear_bn)
    return c_noised - denoise


def matmul_ops(m: int, n: int, k: int) -> int:
    """Multiply-accumulate operations in one m×k · k×n int8 GEMM attempt."""
    return 2 * m * n * k
