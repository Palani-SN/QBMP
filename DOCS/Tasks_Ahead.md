# QBMP - Tasks Ahead

A working backlog for QBMP at **v0.0.3**. Two sections: **Robustness** is about trusting what is
already here, **Improvement** is about what is not here yet.

Every status below was checked against the code in this repository rather than inferred from the
roadmap. Where a task is already done, the evidence is named so the claim can be re-checked.

## Status legend

| Status | Meaning |
|---|---|
| `Done` | In the repository and verifiable now |
| `Partial` | Exists but incomplete, or done for one case and not the general one |
| `Open` | Not started. Free to pick up |
| `Decision` | Not blocked on effort, blocked on a maintainer choosing. Say which way and it becomes `Open` |

<!-- The ID header is padded with &nbsp; on purpose. GFM tables size columns to
     their content, so without it the ID column collapses and a browser wraps
     IDs at the hyphen, rendering "R-105" over two lines. The padding sets a
     minimum column width. Do not remove it, and do not "fix" this by putting a
     non-breaking hyphen in the IDs themselves: that would stop them matching a
     plain grep for R-105, and copying one from the rendered page would paste a
     character that does not match the source. -->

Task IDs are stable. Quote one in an issue or PR title (`R-26: unit tests for _plan`) so the board
and the code stay tied together.

---

# Section 1 - Robustness

## 1.1 Correctness: schema validation at construction

`QBMP(seed)` binds engines and checks that wiring, and nothing else. Everything below currently
fails late, deep inside a sweep, with an error that does not name the declaration that caused it.
This is the highest-value cluster in the backlog: a bad model should be rejected at construction,
with a message naming the key at fault.

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-01 | Validate that every input named in an output's `weights` exists in `Inputs`. Today a typo raises `KeyError` mid-sweep | Open |
| R-02 | Validate that each engine's signature accepts exactly the inputs its `weights` names. Today a mismatch raises `TypeError` on the first row | Open |
| R-03 | Validate that each input's `default` lies inside its own `range` or `categories` | Open |
| R-04 | Reject a column declaring both `range` and `categories`. Today `_combinational` tests `categories` first and silently treats it as combinational | Open |
| R-05 | Validate `range` is a 2-tuple with `lo < hi`. Inverted or degenerate bounds are currently accepted and produce garbage | Open |
| R-06 | Validate that `categories` is non-empty and free of duplicates | Open |
| R-07 | Validate that `weights` is non-empty and that its values are numeric | Open |
| R-08 | Validate that every declared output has exactly one of `range` / `categories`, plus an `engine` key | Open |
| R-09 | Collect all schema errors and raise once rather than failing on the first. A model with three typos should report three | Open |
| R-10 | Decide where validation lives: eagerly in `__init__`, or in `__init_subclass__` so a bad class fails at import | Decision |

Already enforced today, for reference: the engine method exists; the engine carries `@rule` for
that output; the `outputs` selection is non-empty and names declared outputs; `min_rows >= 1`; at
least one continuational output is selected; `format` is csv or xlsx; `dataset` names a folder.

## 1.2 Correctness: known defects and rough edges

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-11 | Rows outside a declared output range are written to the dataset but counted nowhere on the datasheet: `_cavities`, `_provenance` and `_panel_range` all filter `lo <= value <= hi`, and `_ladder` cuts on declared edges so pandas drops them as `NaN`. Decide whether to warn, clamp or widen | Open |
| R-12 | `covered%` is `100 * (high - low) / (hi - lo)` over achieved extremes, so it reads above 100 when the model overshoots its declared range instead of flagging it | Open |
| R-13 | `_uniformity` returns `inf` for `spread` when any of the ten windows is empty. Decide on a representation that survives being put in a table or a JSON report | Open |
| R-14 | `self.rng = random.Random(seed)` is assigned and never read. `seed` is a required positional argument with no observable effect on output | Decision |
| R-15 | `__init__` initialises only `self.report`. `mix`, `drift`, `frame`, `origin`, `voids`, `bins`, `asked` and `requested` appear mid-run, which is why `_ladder` and `_card` guard with `getattr(self, ..., default)` | Open |
| R-16 | `self.frame` is set inside `_datasheet`, so it is absent under `datasheet=False` while the other reports are present | Partial |
| R-17 | `_panel_range` carries an `Inputs` branch that is unreachable: it is only ever called for outputs | Open |
| R-18 | `save(verbose=False)` still prints the two lines naming what was written. Documented as deliberate; confirm or gate them | Decision |
| R-19 | `MAX_BINS` is 2048 while the recorded measurement has the solver still filling cleanly at 8192. The ceiling is set by readability, not capability. Confirm, or expose a documented way to raise it | Decision |
| R-20 | `_generate` gives up after three stalls without telling the caller that `min_rows` was never reached. Surface it in the report | Open |

## 1.3 Test framework setup

There is no test suite. `pytest` is already declared in `extras_require["dev"]`, and `.gitignore`
reserves `TESTS/res_files/*`, so the intended location is `TESTS/`.

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-21 | `pytest` declared as a dev dependency | Done |
| R-22 | Create `TESTS/` and settle the import path story: `SRCS` on `PYTHONPATH`, or an editable install | Open |
| R-23 | `conftest.py` with a tiny fixture model: two inputs, one continuational output, one combinational output. Fast enough to use everywhere | Open |
| R-24 | Add pytest configuration and register markers | Open |
| R-25 | A `slow` marker, so the full seven-output Demo run stays out of the default suite | Open |

## 1.4 Unit tests by unit

One row per function or tight cluster, so they can be claimed independently.

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-26 | `_plan`: the product reaches `min_rows`, counts stay balanced, every pass gets at least 2, and the final overshoot step picks the smallest | Open |
| R-27 | `_grid`: continuational spacing including the `count == 1` midpoint case; combinational returns the option list regardless of `count` | Open |
| R-28 | `_nearest` and `_solve`: targets met within tolerance, the cascade falls through when an input saturates, interior targets met by the first input alone | Open |
| R-29 | `_refine`: converges finer than the `PROBE` grid step, and works on a deliberately non-monotonic engine | Open |
| R-30 | `_quoins` and `_widen`: landmarks equidistant across the declared range, and widened windows tiling the gap with no doubling or loss at the ends | Open |
| R-31 | `_resolution`: largest power of two at or below the row count, capped by `max_bins` | Open |
| R-32 | `_cavities`, `_mortar`, `_unreachable_at`: cavities found, filled where reachable, recorded in `voids` where not, plus coarse and fine inheritance of the unreachable verdict | Open |
| R-33 | `_combos` and `_categoricals`: full cartesian product, ordering by weight, and the empty case returning `[{}]` | Open |
| R-34 | `_ranked` and `_tiers`: the first selected output sets the order, extras rank by the highest weight any other output gives them | Open |
| R-35 | `_selected`: string, list, `None`, duplicates, empty and unknown names | Open |
| R-36 | `rule` decorator: kwargs completed from defaults, keys outside the weights dict dropped, `_qbmp_output` marker set | Open |
| R-37 | `_coherence`: returns 0.0 on a clean frame and a non-zero worst disagreement on a deliberately corrupted one | Open |
| R-38 | `_qualify`, `_compose`, `_composition`: column names, absent-option reporting, and the percentage arithmetic | Open |
| R-39 | `_ladder`, `_provenance`, `_slices`: rung counts, provenance split by course, and equal row-count slicing | Open |
| R-40 | `_weight`, `_tick`, `_palette`, `_cell`, `_table`: formatting helpers, including HTML escaping of a hostile column name | Open |

## 1.5 Integration, invariant and regression tests

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-41 | The coherence invariant as a property test: for any generated frame, re-deriving every output from its own row reproduces it exactly | Open |
| R-42 | Determinism: the same model, seed and arguments produce a byte-identical CSV across two runs and two processes | Open |
| R-43 | Cross-platform determinism: the same across Windows and Linux. Float formatting is the risk | Open |
| R-44 | `min_rows` floor: the returned frame is never shorter than asked, or the shortfall is reported | Open |
| R-45 | Coverage guarantee: at the granted resolution, no continuational output has an empty reachable bin | Open |
| R-46 | Unreachable bins: the Demo model's `annual_maintenance` reports exactly the bins outside `(1125, 26460)` as unreachable, not as gaps | Open |
| R-47 | Every declared category of every combinational column appears at least once | Open |
| R-48 | `save()` I/O: folder creation including a nested `dataset="out/prices"`, both writers, and the `index.html` name | Open |
| R-49 | Error paths: one test per `ValueError` in the codebase, asserting the message names the offending key | Open |
| R-50 | Golden-file regression on the small fixture model, comparing the CSV and the report tables | Open |
| R-51 | Datasheet output: parses as HTML, contains no `http` reference, and inlines its CSS, SVG and script | Open |
| R-52 | Property-based tests with `hypothesis` over randomly generated valid models | Open |
| R-53 | Both documented examples, in README and in the Functional Requirements quick start, execute as written. Both were broken at one point and only running them caught it | Open |

## 1.6 Coverage

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-54 | Add `coverage.py`, wire it to the pytest run, and record the starting number | Open |
| R-55 | Agree a minimum threshold and fail CI below it | Decision |
| R-56 | Exclude the datasheet CSS and JS string constants from the coverage denominator | Open |
| R-57 | Publish an HTML coverage report as a CI artifact, and a badge in the README | Open |

## 1.7 Static analysis, typing and style

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-58 | Choose and configure a linter. `ruff` is the recommendation: it subsumes flake8, isort and more | Decision |
| R-59 | Fix the first clean pass, including the unreachable branch in R-17 | Open |
| R-60 | Choose a formatter and apply it once as a single reviewable commit | Decision |
| R-61 | Add type hints to the public surface: `rule`, `QBMP.__init__`, `save` | Open |
| R-62 | Add type hints to internals and turn on `mypy` in non-strict mode | Open |
| R-63 | Tighten `mypy` toward strict once the internals are annotated | Open |
| R-64 | Enforce the repository's ASCII-only rule for Markdown in CI. An em dash previously reached the PyPI page as mojibake | Open |
| R-65 | Add `.gitattributes` to pin line endings. The tree is currently CRLF in the working copy and LF in the index by `core.autocrlf` alone | Open |

## 1.8 CI/CD, DevOps and release process

Nothing is automated today. There is no `.github/` directory.

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-66 | `.github/workflows/test.yml`: run the suite on push and pull request | Open |
| R-67 | Matrix the test job across Python 3.11, 3.12, 3.13 and 3.14, the versions `setup.py` advertises but nothing verifies | Open |
| R-68 | Matrix across Windows, Linux and macOS. `Operating System :: OS Independent` is currently an unverified claim | Open |
| R-69 | A lint and type-check job, kept separate from tests so failures are distinguishable | Open |
| R-70 | A build job: `python -m build`, then `twine check dist/*` | Open |
| R-71 | Run `check-manifest` in CI. It is already in the dev extra and will flag `DOCS/` and `EXAMPLES/` as tracked-but-not-shipped, which is deliberate and needs an ignore entry | Open |
| R-72 | A publish workflow triggered on a version tag, using PyPI Trusted Publishing rather than a stored API token | Open |
| R-73 | Verify the built sdist and wheel install cleanly in a fresh environment and that `from QBMP.engine import QBMP, rule` works | Open |
| R-74 | Dependabot or Renovate for GitHub Actions and dev dependencies | Open |
| R-75 | Branch protection on `main` with the test job required | Open |
| R-76 | Pre-commit hooks mirroring the CI lint, so failures are caught locally | Open |
| R-77 | A documented release procedure. A checklist exists in the Functional Requirements but is not tied to tags or a changelog | Partial |

## 1.9 Packaging hardening

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-78 | `LICENSE.txt` present and carried into metadata as `License-File` | Done |
| R-79 | Licence declared as an SPDX expression on `license=`, with no deprecated `License ::` classifier | Done |
| R-80 | `MANIFEST.in` controlling sdist contents | Done |
| R-81 | `README.md` read as UTF-8 explicitly, so non-ASCII cannot corrupt the PyPI page | Done |
| R-82 | Add `pyproject.toml` with a `[build-system]` table. `setup.py`-only builds are on the way out | Open |
| R-83 | Once R-82 lands, pin `setuptools>=77` and move to `license_expression` for the modern `License-Expression` field. Unsafe before the pin: on older setuptools it is dropped silently, leaving no licence metadata at all | Open |
| R-84 | Single-source the version. `__version__` reads installed distribution metadata, so a working copy edited past its last install reports the older number | Open |
| R-85 | Revisit the `pandas>=3.0.5` floor. Nothing in `engine.py` needs pandas 3 | Decision |
| R-86 | Revisit `openpyxl` as a hard dependency versus an `[excel]` extra. Moving it later is a breaking change for anyone writing xlsx | Decision |
| R-87 | Decide whether `SRCS/QBMP/__init__.py` should re-export `QBMP` and `rule`. Today only `QBMP.engine` works, and the package name shadows the class name | Decision |
| R-88 | Remove the dead `sys.version_info >= (3, 8)` branch in `__init__.py`, unreachable under `python_requires>=3.11` | Open |

## 1.10 Project governance

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-89 | `CONTRIBUTING.md`: how to set up, how to run the tests, and what is expected of a pull request | Open |
| R-90 | `CHANGELOG.md`, retroactively covering 0.0.1 through 0.0.3 | Open |
| R-91 | Issue templates for bug and feature, plus a pull request template | Open |
| R-92 | `CODE_OF_CONDUCT.md` | Open |
| R-93 | `SECURITY.md`. Small surface area, but `save()` writes to caller-supplied paths | Open |
| R-94 | Label taxonomy: `good-first-issue`, `robustness`, `improvement`, and one label per area | Open |
| R-95 | Seed the issue tracker from this document, one issue per task ID | Open |
| R-96 | An architecture note for contributors: the four courses, and which function owns each | Partial |

## 1.11 Performance and optimisation

Measured baseline: the seven-output Demo model at `min_rows=1000, max_bins=2048` produces 4,864
rows in roughly 20 seconds, and its `index.html` is about 2.4 MB.

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-97 | Profile a full `save()` and publish where the time actually goes, before optimising anything | Open |
| R-98 | Count engine invocations per row. `_solve` probes `PROBE` (400) points per tier, and `_refine` adds six rounds of nine on top of each | Open |
| R-99 | Memoise or vectorise repeated engine evaluation. `_mortar` recomputes `[engine(**row) for row in rows + placed]` for every continuational output | Open |
| R-100 | Cache `_defaults()`, `_ranked()` and `_tiers()`, which are recomputed inside loops and depend only on the model | Open |
| R-101 | Reconsider `_build` re-running from scratch on each budget escalation, discarding the previous pass entirely | Open |
| R-102 | Reduce datasheet size. Every rung of every ladder is emitted as SVG, which is what produces multi-megabyte files | Open |
| R-103 | Document the complexity in terms of inputs, outputs, categorical product and `min_rows`, and publish a scaling curve | Open |
| R-104 | Establish a performance regression guard in CI, even a coarse wall-clock ceiling | Open |

## 1.12 Comparative benchmarking and the research write-up

The claim worth defending is narrow and testable: for a declared output range, QBMP reaches **zero
empty bins at a stated resolution** using fewer rows than sampling methods that never look at
where the gaps are. The list below is the baseline set to measure against.

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| R-105 | Fix the metrics before running anything: `solid@bins`, rows needed to reach zero gaps at a target resolution, `covered%`, `spread`, wall time, engine-call count | Open |
| R-106 | Baseline: uniform random sampling of the input space | Open |
| R-107 | Baseline: full grid or systematic sweep. Deterministic and gap-free per axis, exponential in dimension | Open |
| R-108 | Baseline: Latin Hypercube Sampling. Uniform marginals from far fewer points than a dense grid | Open |
| R-109 | Baseline: low-discrepancy sequences, Sobol and Halton | Open |
| R-110 | Baseline: rejection sampling against a target output distribution | Open |
| R-111 | Baseline: a copula-based tabular generator, as the statistical-fidelity comparison rather than a coverage one | Open |
| R-112 | State explicitly why generative baselines (GAN, VAE, diffusion, autoregressive) are out of scope: they learn from data, whereas QBMP starts from a declared model and has no training set | Open |
| R-113 | Build a harness that runs every method against the same model and emits one comparable table | Open |
| R-114 | Assemble a benchmark model suite: monotonic, non-monotonic, discontinuous, high-dimensional, categorical-heavy, and one declaring a range wider than achievable | Open |
| R-115 | Run the sweep and produce results tables and plots: rows needed against resolution reached, per method | Open |
| R-116 | Report where QBMP loses. Anchoring in output space should cost it on uniformity, and the categorical cartesian product should cost it on high categorical dimensionality | Open |
| R-117 | Package the benchmark for reproduction: pinned environment, seeds, single entry point | Open |
| R-118 | Write the article: problem statement, the courses, the coherence invariant, results, threats to validity | Open |
| R-119 | Position against existing tools by intent rather than quality. `Faker` produces plausible values with no model; SDV and copulas learn from data; `Hypothesis` falsifies properties; QBMP starts from a declared model and certifies coverage | Open |
| R-120 | Decide the venue, and whether a preprint comes first | Decision |

---

# Section 2 - Improvement

## 2.1 The declared roadmap

These four are already described in the Functional Requirements. Broken here into claimable
pieces.

### Pointing, the fourth course

The `P` in QBMP, and the only letter with nothing behind it yet. Coverage is solved; flatness is
not.

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| I-01 | Purge: drop rows from over-full bins. The easy half, a sort and a slice | Open |
| I-02 | Populate thin bins by rejection sampling. Cheapest, and the first to try | Open |
| I-03 | Populate by a constrained solve into a corner-biased sub-box | Open |
| I-04 | Populate by a level-set walk from a row already inside the bin | Open |
| I-05 | Rebalance fine but validate coarse, so the metric cannot become self-fulfilling | Open |
| I-06 | Preserve the coherence invariant throughout: populating is legal only when it solves for inputs | Open |
| I-07 | Report before-and-after `spread` on the datasheet so the effect is visible | Open |
| I-08 | Handle the known ceiling: once inputs are genuinely discrete (I-16), an extreme bin's pre-image may hold only a handful of legal points, and filling will fail on exactly the bins that need it most | Open |

### Pairwise covering for categoricals

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| I-09 | Replace the full cartesian product in `_combos` with a pairwise covering array, guaranteeing every option and every pair while growing logarithmically rather than multiplicatively. `_combos` is the single place it slots in | Open |

### Multi-output rebalancing

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| I-10 | Minimise the worst `spread` across the selected outputs rather than perfecting any single one | Open |

### Multi-level dependencies

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| I-11 | Let a `weights` key name another output, turning the bipartite graph into a DAG | Open |
| I-12 | Settle shared inputs across sibling branches first: if two outputs share an input, the branches are coupled and cannot be solved independently. This decides whether the whole feature is easy or hard | Open |
| I-13 | Compose reachable ranges bottom-up. A parent's achievable range depends on its children's achievable ranges, and the error compounds at every level | Open |
| I-14 | Cycle detection at bind time, with a readable error | Open |
| I-15 | Distribute the row budget across the DAG's leaves rather than across a flat tier list | Open |

## 2.2 Modelling features

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| I-16 | Integer and discrete inputs. `bedrooms` currently takes values like `1.34`, which is physically nonsense. Blocks I-08 and affects every sampler | Open |
| I-17 | Stepped inputs: a range plus an increment | Open |
| I-18 | Disjoint and multi-interval ranges, so an output space can carry structural holes the sampler respects | Open |
| I-19 | Cross-input constraints, for example `area_sqft >= 300 * bedrooms`, so impossible combinations are never emitted | Open |
| I-20 | Ordered categoricals, where the option list carries a meaningful sequence | Open |
| I-21 | Per-input distributions or priors, for callers who want a shape rather than coverage | Open |
| I-22 | Derived inputs: computed from other inputs but presented as an input column | Open |
| I-23 | Missing-value injection at a declared rate, for testing null handling downstream | Open |
| I-24 | Noise injection on outputs, with the coherence invariant explicitly relaxed and reported rather than silently broken | Open |
| I-25 | Units and display metadata per column, carried through to the datasheet | Open |
| I-26 | Datetime and duration column types | Open |
| I-27 | Text and identifier columns, for example a formatted ID, without taking on a faker dependency | Open |

## 2.3 API and architecture

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| I-28 | Separate the generation engine from the export layer, so the core can run without pandas or openpyxl in embedded environments. `_build` currently constructs a DataFrame directly | Open |
| I-29 | A public generate-only entry point. `_generate` already returns a frame without writing, but it is private | Open |
| I-30 | Replace the nested-dict model with a parsed and validated structure. Relates directly to R-01 through R-10. Weigh a dataclass-based parser against a Pydantic dependency: Pydantic gives better errors for free, but the package currently has a very small dependency surface and that is part of its appeal | Decision |
| I-31 | Streaming or chunked generation, so datasets larger than memory become possible | Open |
| I-32 | A progress callback, replacing prints for long runs | Open |
| I-33 | Route diagnostics through `logging` rather than `print`, keeping today's output as the default handler | Open |
| I-34 | A command-line interface: point it at a module and a model class, get the folder | Open |
| I-35 | Multiprocessing across categorical combinations, which are independent by construction | Open |
| I-36 | Let the caller supply the resolution ladder rather than always doubling from 1 | Open |
| I-37 | Make `MAX_BINS`, `PROBE` and `TOL` settable per instance, with the class attribute as the default | Open |

## 2.4 Output formats

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| I-38 | Parquet output | Open |
| I-39 | JSON and JSONL output | Open |
| I-40 | SQLite or SQL insert output | Open |
| I-41 | Optional compression for csv | Open |
| I-42 | Deterministic train/validation/test splitting that preserves coverage within each split, which is harder than it sounds and is the interesting part | Open |
| I-43 | Let the caller pass writer options through to pandas | Open |

## 2.5 The datasheet

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| I-44 | Emit the report as machine-readable JSON alongside the HTML, so CI can assert on coverage | Open |
| I-45 | Produce a datasheet for an existing dataset without regenerating it | Open |
| I-46 | Diff two datasheets, to show what changed between runs or versions | Open |
| I-47 | Accessibility pass. The ladders are colour-coded, and red versus grey currently carries meaning that colour alone conveys | Open |
| I-48 | A compact datasheet mode for large runs, addressing R-102 from the user-facing side | Open |
| I-49 | Print and PDF stylesheet | Open |
| I-50 | Make the datasheet template overridable, beyond the existing `SHEET_CSS` and `SHEET_JS` hooks | Open |

## 2.6 Documentation and adoption

| ID&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Task | Status |
|---|---|---|
| I-51 | A rendered documentation site, mkdocs or Sphinx, rather than two long Markdown files | Open |
| I-52 | A worked tutorial that builds a model from scratch and explains each metric as it appears | Open |
| I-53 | More examples beyond real estate: a sensor or physical model, a finance model, and one with deliberate structural holes | Open |
| I-54 | A page on when *not* to use QBMP, which is the fastest way to be trusted by the people it does suit | Open |
| I-55 | Publish the comparison from R-119 as user-facing documentation, not only inside the article | Open |
| I-56 | A short screencast or animated walkthrough of the datasheet, since it is the least obvious part of the project | Open |

---

## Suggested order

Nothing here is sequenced by dependency except where stated, but the leverage is uneven.

1. **R-21 to R-25, plus R-41.** A test harness and the coherence invariant. Everything else
   becomes safer to change once these exist.
2. **R-66 to R-68.** CI across the advertised Python versions and operating systems, so the
   classifiers stop being unverified claims.
3. **R-01 to R-10.** Schema validation: the highest ratio of user pain to implementation effort,
   and R-02 describes a bug that shipped in this project's own README.
4. **R-89 to R-95.** Governance, at the point external contributors are actually wanted.
5. **I-16.** Discrete inputs, which several roadmap items are waiting on.
6. **R-105 onward.** The benchmark, once there are tests to trust the numbers with.
