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


def _rotl32(x: np.uint32, n: int) -> np.uint32:
    x = np.uint32(x)
    return np.uint32((x << np.uint32(n)) | (x >> np.uint32(32 - n)))


def _mul_hi_u32(a: np.uint32, b: np.uint32) -> np.uint32:
    return np.uint32((np.uint64(a) * np.uint64(b)) >> np.uint64(32))


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
        for i in range(draws):
            words = np.frombuffer(self._hash(i, seed, key, 1), dtype=np.uint32)
            for k in range(8):  # 32 bytes / 4 bytes per line
                assignment_index = i * 8 + k
                if assignment_index >= required:
                    break
                w = words[k]
                first = int(w & np.uint32(self.rank_mask))
                second = first ^ int(
                    np.uint32(1) + _mul_hi_u32(np.uint32(self.noise_rank - 1), w)
                )
                second &= self.rank_mask
                col = np.zeros(self.noise_rank, dtype=np.int8)
                col[first] = 1
                col[second] = -1
                if assign_columns:
                    out[:, assignment_index] = col
                else:
                    out[assignment_index, :] = col
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


def _inner_hash_tile(tile: np.ndarray) -> np.uint32:
    """XOR-reduce an int32 tile, viewed as uint32, to a single word."""
    return np.bitwise_xor.reduce(tile.astype(np.int32).reshape(-1).view(np.uint32))


def _transcript_bytes(transcript: np.ndarray) -> bytes:
    return transcript.astype("<u4").tobytes()


def noisy_gemm_pow(
    a: np.ndarray,
    b: np.ndarray,
    noise: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    pow_key: bytes,
    target: int,
    cfg: MiningConfig,
) -> tuple[np.ndarray, Solution | None]:
    """Run the noised tiled GEMM and search its transcripts for a winning tile.

    Returns the (denoised) product C — equal to A @ B, proving the noisy
    computation did the real matmul — and the first ``Solution`` whose keyed
    transcript hash meets ``target`` (or ``None``).
    """
    e_al, e_ar, e_bl, e_br = noise
    rank = cfg.rank
    m, k = a.shape
    n = b.shape[1]
    hth, htw = cfg.hash_tile_h, cfg.hash_tile_w

    # Noise the inputs (int8) and pre-compute the denoising terms (int32).
    e_a = (e_al.astype(np.int32) @ e_ar.astype(np.int32)).astype(np.int8)
    e_b = (e_bl.astype(np.int32) @ e_br.astype(np.int32)).astype(np.int8)
    a_n = (a + e_a).astype(np.int8)
    b_n = (b + e_b).astype(np.int8)
    a_ebl = a.astype(np.int32) @ e_bl.astype(np.int32)
    ear_bn = e_ar.astype(np.int32) @ b_n.astype(np.int32)
    denoise = (a_ebl @ e_br.astype(np.int32)) + (e_al.astype(np.int32) @ ear_bn)

    c = np.zeros((m, n), dtype=np.int32)
    solution: Solution | None = None

    for i in range(0, m, rank):
        i_max = min(i + rank, m)
        for j in range(0, n, rank):
            j_max = min(j + rank, n)
            block_h, block_w = i_max - i, j_max - j
            nth, ntw = block_h // hth, block_w // htw
            transcripts = np.zeros((nth, ntw, TRANSCRIPT_SIZE_U32), dtype=np.uint32)
            c_block = np.zeros((block_h, block_w), dtype=np.int32)
            reduction = 0
            for p in range(0, k, rank):
                p_max = min(p + rank, k)
                c_block = c_block + (
                    a_n[i:i_max, p:p_max].astype(np.int32)
                    @ b_n[p:p_max, j:j_max].astype(np.int32)
                )
                is_full = block_h >= hth and block_w >= htw and (p_max - p) == rank
                if not is_full:
                    continue
                idx = reduction % TRANSCRIPT_SIZE_U32
                for hi in range(nth):
                    for wi in range(ntw):
                        tile = c_block[hi * hth : (hi + 1) * hth, wi * htw : (wi + 1) * htw]
                        combined = _inner_hash_tile(tile)
                        t = transcripts[hi, wi]
                        t[idx] = _rotl32(t[idx], HASH_ACCUMULATE_ROTATION) ^ combined
                reduction += 1

            if solution is None and reduction > 0:
                for hi in range(nth):
                    for wi in range(ntw):
                        digest = blake3(
                            _transcript_bytes(transcripts[hi, wi]), key=pow_key
                        ).digest()
                        h = int.from_bytes(digest, "little")
                        if h <= target:
                            solution = Solution(
                                row=i + hi * hth,
                                col=j + wi * htw,
                                transcript=[int(x) for x in transcripts[hi, wi]],
                                pow_hash_int=h,
                                target=target,
                                seed_a=pow_key,
                                seed_b=b"",
                            )
                            break
                    if solution is not None:
                        break

            c[i:i_max, j:j_max] = c_block - denoise[i:i_max, j:j_max]

    return c, solution


def matmul_ops(m: int, n: int, k: int) -> int:
    """Multiply-accumulate operations in one m×k · k×n int8 GEMM attempt."""
    return 2 * m * n * k
