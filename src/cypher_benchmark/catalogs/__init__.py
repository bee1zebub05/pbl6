"""Ba bộ Cypher, chọn bằng `--source`:

    samples    regression trên 17 văn bản mẫu (assert số dòng)
    benchmark  đo hiệu năng trên data thật (chỉ đo, không assert)
    scenarios  20 kịch bản dễ -> khó trên data thật, có ground truth (P/R/F1)
"""

from . import benchmark, samples, scenarios

SOURCES = {
    "samples": samples.QUERIES,
    "benchmark": benchmark.QUERIES,
    "scenarios": scenarios.QUERIES,
}
