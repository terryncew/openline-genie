# Sources, provenance, adaptations, and exclusions

## Source archives

The research in this section comes from four archives and several
supporting files. Every archive was verified by SHA-256 before use.

| Archive | SHA-256 | Size | Contents |
| --- | --- | --- | --- |
| `OPENLINE_CIVILIZATION_RATCHET_003_COMPLETE_PACKAGE.zip` | `72802ddb9237cab72b3c219f31b2d3ac38684ed770b629b090b547957c3f8beb` | 4,476,595 B | The tournament model and the original research package (99 files). Its inner manifest verifies 98/98. |
| `OPENLINE_MIF_PWS_V2_PHYSICAL_EXPERIMENT_004_PACKAGE.zip` | `d0feb99bdbdc9d695de5acc6ec33e8f645eb2a2ca4854ed972eb15cd0a63ae4b` | 574,280 B | The physical screening package: simulation, CAD generation, bill of materials, test suite (27 files). Its manifest verifies 26/26. |
| `OPENLINE_CIVILIZATION_RATCHET_003_GPT6_INDEPENDENT_FALSIFICATION.zip` | `1007f46313725344d9ea9f3bea055b4bc8c7c78e7c6f4d72712f84ef5c21802e` | 15,625 B | The independent falsification: acceptance report, ablation script and results, replay log (7 files). Its manifest verifies 6/6. |
| `OPENLINE_MIF_PWS_004_GPT6_INDEPENDENT_REVIEW.zip` | `a62d9322736931d0946d29f66fa6c52077eb6fb85ab9305a385979930bf8546c` | 9,445 B | The independent audit: review, challenge script and results, source receipt (5 files). Its manifest verifies 4/4. |
| `OPENLINE_CIVILIZATION_RATCHET_004_DOGFOOD_REPRO.zip` | `ae3d85cc3abc69d6983ce3f9b1cd88bd3f6b952099e37a8c4de1d8b964e43904` | 4,476,934 B | The repair round: split-plane variants, first-principles gates, reproduction script (9 files). Its manifest verifies 8/8. It contains an unchanged copy of the first archive above. |
| `OPENLINE_CIVILIZATION_RATCHET_003_REPAIRED_FULL_STACK.zip` | `ca322f0ac0637ca223fe88655b112b7280b6e3ab9b9fc06d6d9aebd15e3bbc1f` | 6,797,637 B | A repaired full stack used only as a cross-check (377 files). Its top-level manifest verifies 329/343: 14 listed files are missing (case-packet demo archives and test evidence images) and 11 entries carry stale hashes from before the repair. Neither defect affects the chip research. No file from this archive is published here. |

Supporting files (all SHA-verified):

- `INDEPENDENT_REVIEW_004.md` — `5a67e431c9ae05c9b0a6a240433aed01444ad625826835825e53274d936605b9` (8,119 B), the audit text, also inside the review archive.
- `OPENLINE_CIVILIZATION_RATCHET_004_REPAIR_ROUND.md` — `ff58df869e55186b9071cac179959d39a37466f51e29d0b3f59589c1ddd74a39` (8,691 B), the repair-round analysis.
- `OPENLINE_CIVILIZATION_RATCHET_003_REPORT.md` — `d368bb7402b964c688ed603a10b3e31d26ad9be2ada1e8ac392906c7dc09d703` (6,958 B), the original research report. Used only as a source of numbers; not published (see exclusions).
- `OPENLINE_CIVILIZATION_RATCHET_003_MASTER_EVIDENCE.json` — retrieved as JSON text; the retrieval path re-serializes JSON, so its byte hash cannot be confirmed against the hash cited in the report. Its content was verified by inspection and its numbers cross-checked against the SHA-verified archives. Not published (see exclusions).
- `MIF_PWS_V2_PHYSICAL_EXPERIMENT_004_MASTER_EVIDENCE.json` — the copy inside the screening package is authoritative: `7f84efe061072a534d1bd64df597f4332dae0945a020320c3e31a16de5cb8b76` (64,515 B), matching the package manifest. A separately retrieved copy differs only by an added `retrieved_at` field.
- `MIF_PWS_V2_ITEMIZED_BOM_004.csv` — `17e40efcb004d1e0df8fa5f974ac0196d4b1e9c23c07ab5696087dad04cdc085` (7,519 B), 17 rows. Cross-checked against the bill of materials inside the screening package; the totals agree.
- Figures: `fig1_manufacturing_tournament_comparison.png` — `b49753669fd882b5ca49a8f86ab25bf0490a7199d570315951d335b49e739fc0` (354,234 B); `fig2_test_fixture_and_surrogate_protocol.png` — `16b2fc041ec811552cc328c4351ac385d227932410a5701dc9cbc64e734f46dc` (162,672 B); `mif_pws_v2_fabrication_blueprint.svg` — `1d06be36914427cfa23312420d102bffff4a5ac73a9a7116861755775f52a509` (12,942 B); `mif_pws_v2_coupon_blueprint.svg` — `129a6e22f7d0eac1d562908dda7d0418f39a0bcf4667fdf9421287f3f968eeda` (3,620 B). All four hash-identically to the copies inside the screening package.

## Files published here, with their source hashes

### Simulation

| Published file | Source | Source SHA-256 |
| --- | --- | --- |
| `simulation/tournament_model/coupled_electro_thermo_wafer_sim.py` | Tournament module from the first archive | `ce5ae583b6ff46e36bd2342aab3363f8925bce32d6f4e1c9bf084478c3e9a575` |
| `simulation/tournament_ablation.py` | Adapted from `independent_ablation.py` in the falsification archive (`09d158f8f671321bcd08b2137105c72308012ff589403565309d370292d65fbd`) | See adaptations |
| `simulation/frontier_repair_round_004.py` | `frontier_repair_round_004.py` from the repair-round archive (`b746c474d39e7ab532f2ce4f4d70e59ae2cf736f2453a410801eaa763473e399`) | See adaptations |
| `simulation/first_principles_gates_004.py` | Same archive, verbatim | `ae45d817fe259510e55b41ec2c582a8d07f2668751327aa81f868bccba800e7c` |
| `simulation/mif004/physics_and_manufacturing_sim.py` | Screening package, verbatim | `f1d1f28bddef0071cd7abd041b16b5e757a89210359b1daef11bd8bec2257464` |
| `simulation/mif004/independent_falsification_and_verification.py` | Screening package, verbatim | `22041b83dea3171eb2e8d757ccf969b73a96901320ffc816fcabce62c827c2bc` |
| `simulation/mif004/bom_and_supplier_matrix.py` | Screening package, verbatim | `e11ea947780713266da8550fb7172e2243d1219e1f763b4ad2e4ccb2fb7412bd` |
| `simulation/mif004/generate_cad_and_drawings.py` | Screening package, verbatim | `316b5f0dc71a4c20546bc1ca2e0ac3dd2e21432117f089be8d53e5b1b713f67e` |
| `simulation/mif004/run_all_physical_experiment_004.py` | Screening package, verbatim | `9e0f91888f08ca00c73931dce0f950edd8dc622bf92ecaaa1bd8d5ef68f50345` |
| `simulation/mif004/tests/test_physical_experiment_004.py` | Screening package, verbatim | `adfabbb6fe7b4e8f5ca1da4d1affa08c6bb5498b0275f75f72c98fcda36c5113` |
| `simulation/mif004/bom/itemized_bom_all_approaches.csv` | Screening package, verbatim | `7f56285639c1af28aaa87d23f215215d533da1b0a3386bd60b4be4e584a027bf` |
| `simulation/mif004/bom/itemized_bom_and_suppliers.json` | Screening package, verbatim | `432b3b2fa7c6625ecd3a077b279b9723d0927584a801ee5dd65af5660690880a` |
| `simulation/mif004/independent_challenge_004.py` | Review archive, verbatim | `d49869cbc6da3d4099d9cb214cc2f35f789fb61fa071bdb2bb9d029b75bfc47c` |
| `simulation/expected/ablation_results.json` | Falsification archive, verbatim | `e3a500890bd8246abda08df4ab914e3127a8980da9b182e59e3a0020f8a4f7a9` |
| `simulation/expected/r004_first_principles_gates.json` | Repair-round archive, verbatim | `f0dc3eb3022783ac2c4646faef3e77b9aae116e8d0571fcaaf63a3415c8631e9` |
| `simulation/expected/r004_source_bound_results.json` | Repair-round archive, verbatim | `031a502e40ad5e371c88d4a4075dd6dfcf824b26e429d614b90ad9fd533b82f4` |
| `simulation/expected/independent_challenge_results.json` | Review archive, verbatim | `93545e61ef456f17fb066bb9ab202b53c5425e8602325bd9ea0a42477ba36d63` |
| `simulation/expected/mif004_master_evidence.json` | Screening package, verbatim | `7f84efe061072a534d1bd64df597f4332dae0945a020320c3e31a16de5cb8b76` |

### Evidence and figures

| Published file | Source | Source SHA-256 |
| --- | --- | --- |
| `evidence/independent_acceptance_report.md` | Falsification archive, verbatim | `1549211c7af58718a1ebc6939712ec666535fbe15e2cbc9a90b3f3e47cd16f62` |
| `evidence/independent_review_004.md` | Review archive, verbatim | `5a67e431c9ae05c9b0a6a240433aed01444ad625826835825e53274d936605b9` |
| `evidence/repair_round_004.md` | Repair-round analysis, verbatim | `ff58df869e55186b9071cac179959d39a37466f51e29d0b3f59589c1ddd74a39` |
| `evidence/INDEPENDENT_RATCHET_003_FULL_STACK_REVIEW.md` | Screening package (recovered upstream copy), verbatim | `b24f0a354a7d37d47b4360df55fdb3ad45ae0e71dd61a68c3ed4069b5c97bc51` |
| `evidence/defective_heater_netlist.sp` | Screening package `cad_and_drawings/mif_pws_v2_kelvin_and_rdl_netlist.sp`, verbatim | `395b70e74d39c9a67917f7684cd53ccafd6ef08eee0b06d7f73067e949a4f1fe` |
| `evidence/independent_challenge_results.json` | Review archive, verbatim | `93545e61ef456f17fb066bb9ab202b53c5425e8602325bd9ea0a42477ba36d63` |
| `figures/fig1_manufacturing_tournament_comparison.png` | See supporting files | `b49753669fd882b5ca49a8f86ab25bf0490a7199d570315951d335b49e739fc0` |
| `figures/fig2_test_fixture_and_surrogate_protocol.png` | See supporting files | `16b2fc041ec811552cc328c4351ac385d227932410a5701dc9cbc64e734f46dc` |
| `figures/mif_pws_v2_fabrication_blueprint.svg` | Screening package, verbatim | `1d06be36914427cfa23312420d102bffff4a5ac73a9a7116861755775f52a509` |
| `figures/mif_pws_v2_coupon_blueprint.svg` | Screening package, verbatim | `129a6e22f7d0eac1d562908dda7d0418f39a0bcf4667fdf9421287f3f968eeda` |

### CAD (unqualified research artifacts)

| Published file | Source | Source SHA-256 |
| --- | --- | --- |
| `cad/mif_pws_v2_hybrid_coldplate.step` | Screening package, verbatim | `cd84af33d814f5a75c4344b0f453ff09b5ba07eae3888c3a61f4bc5ed92bfbde` |
| `cad/mif_pws_v2_cmc_kerf_bridge.step` | Screening package, verbatim | `aca81af81520ba78e346f39d193a1464123b3bf39d7357e33d0761d045ba193b` |
| `cad/mif_pws_v2_hybrid_coldplate.stl` | Screening package, verbatim | `cea6fa90e905f124f7e728dcfa99bdd5ad793ca0f5be234a38e84a7b1ca4898c` |
| `cad/mif_pws_v2_machining_drawing.dxf` | Screening package, verbatim | `6f1e83619c7701669eeb19a205104d9326c38e897e29c9feff11ea4d122e0b00` |

## Adaptations made for this public tree

Three files were adapted. Everything else is a verbatim copy.

1. **`simulation/tournament_ablation.py`** — rewritten from the
   original `independent_ablation.py`. The original read the tournament
   model from a frozen source archive and verified the archive's hash.
   This version imports the same module from the local
   `tournament_model` package, which is a verbatim copy of that module.
   The arm definitions, the severe case, the parity calculation, and
   the output format are unchanged. The output adds one field,
   `source_module_sha256`, holding the hash of the local module. The
   adapted script reproduces the supplied expected results exactly
   (controls, severe case, and parity all match).
2. **`simulation/frontier_repair_round_004.py`** — three lines changed:
   the script now imports the tournament model from the local
   `tournament_model` package instead of from the original archive
   bundle. Nothing else changed. It reproduces the supplied expected
   results exactly.
3. **`simulation/tournament_model/__init__.py`** — new file, a short
   provenance note. The module inside the package is a verbatim copy.

New files written for this publication: `README.md`, `REPRODUCE.md`,
`LIMITATIONS.md`, `CONTRIBUTING.md`, this file, `simulation/README.md`,
`simulation/run_reproduction.py`, `simulation/requirements.txt`,
`simulation/.gitignore`, `cad/README.md`, and `evidence/README.md`.
All are written in plain language and contain no internal research
directives.

## Exclusions

| Excluded | Reason |
| --- | --- |
| `MANUFACTURING_AND_TEST_PROTOCOL.md` (screening package) | Step-by-step manufacturing and energized-test instructions for hardware that is on HOLD. The electrical design is wrong by a factor of twelve (finding F1) and the heater layout does not fit (F2). Only the acceptance thresholds and kill criteria are summarized, as untested predictions, in `LIMITATIONS.md`. |
| The original research report (`OPENLINE_CIVILIZATION_RATCHET_003_REPORT.md`) | Written in an internal voice with internal directives. Its numbers are covered by the independent acceptance report, the repair-round analysis, and this section's own text. |
| The original master evidence JSON (`OPENLINE_CIVILIZATION_RATCHET_003_MASTER_EVIDENCE.json`) | An internal evidence file whose disposition ("verified computationally") was overturned by the independent falsification. Its numbers are covered by the falsification report. |
| The full Genie software tree inside the first and repaired archives (377 files in the repaired archive, 99 in the original) | Unrelated to the chip research. Only the tournament model module, which the ablation depends on, is published. |
| The repaired full stack's case-packet demo archives and test evidence images | Missing from the archive (14 files); nothing to publish. |
| The `model.onnx` file in the archives | A security-triage model from an unrelated part of the software tree, shipped without a license file. Not chip research. |
| The GDSII layout, KiCad schematic, and SPICE circuit for an unrelated milliwatt-scale sensor design | Not part of the MIF-PWS v2 package. Publishing them would mix an unrelated design into this research. |
| The facility desalination model and its receipts | The freshwater-production claim is not established (finding F7). The model and its receipt figures are not published as results; the conflict is documented in `LIMITATIONS.md` and in the audit. |

## Safety and privacy scan

Before publication, every extracted file was scanned for credentials,
private keys, personal data, and licensed third-party content.

- No private key, API token, password, or credential was found in any
  archive. The one signing-key artifact is the fixed literal seed in
  `simulation/mif004/independent_falsification_and_verification.py`
  (finding F6): it is a deterministic demonstration key, derivable by
  anyone who reads the source, and it is documented as forgeable. It is
  not a real credential.
- No real person's email, phone, or address was found. All email
  addresses in the archives use fictional example domains, and all
  phone numbers are fictional 555 numbers in test fixtures.
- No licensed third-party software is redistributed. The archives
  contain no vendored libraries. Runtime dependencies (numpy, scipy,
  matplotlib, Pillow, cryptography) are installed by the reader at
  reproduction time under their own licenses.
- The bill of materials names suppliers and manufacturers (DigiKey,
  Vishay, Sensirion, Texas Instruments, and others) as part of the
  sourcing record. No personal names appear.
