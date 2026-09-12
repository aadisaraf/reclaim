# Contract: X12 fixtures, readers, and validation rules

Scope: `fixtures/x12/era-2026-09-12.835` (Appendix A2) and `fixtures/x12/HSP-CLM-100028.837`
(Appendix A3). Modules: `src/reclaim/x12/tokenizer.py`, `remit835.py`, `claim837.py`,
`validate.py`. No EDI library is used. Fixture text is copied byte for byte from Appendix A.

## 1. Tokenizer (both transaction sets)

| Rule | Detail |
|---|---|
| Delimiters come from ISA | ISA is fixed width (106 characters including the segment terminator). Element separator = character at index 3. Repetition separator = ISA11 (index 82). Component separator = ISA16 (index 104). Segment terminator = index 105. Nothing is hard-coded. |
| Line breaks | CR and LF characters that directly follow a segment terminator are ignored. A line break anywhere else is a parse error. |
| Empty elements | Kept as `""` so element positions never shift (for example `CLP05` empty). |
| Output | `list[Segment]`, where `Segment = (tag, elements: list[str], index)`. Composite elements are split on the component separator only by the reader that needs them (`SVC01`, `SV101`, `CLM05`, `HI01`). |
| Errors | `X12ParseError(segment_index, message)`. Parsing never returns partial results. |

Test files use the same content with CRLF, LF, and no line breaks, plus a copy with `|` as the
element separator and `}` as the component separator, to prove delimiters are read from ISA.

## 2. 835 (005010X221A1) segments read

| Loop | Segment | Elements read | Used for |
|---|---|---|---|
| Envelope | ISA | ISA06 sender, ISA08 receiver, ISA13 control number, ISA15 usage (`T`) | envelope checks; `T` recorded as test data |
| Envelope | GS | GS01 = `HP`, GS06 group control, GS08 = `005010X221A1` | envelope checks |
| Header | ST | ST01 = `835`, ST02 control | envelope checks |
| Header | BPR | BPR02 total paid, BPR16 payment date | balancing; decision date on timeline |
| Header | TRN | TRN02 check/EFT trace number | timeline only |
| Header | DTM*405 | production date | timeline only |
| 1000A Payer | N1*PR | N102 payer name | case `payer` |
| 1000A Payer | REF*2U | REF02 payer ID (`NSTHLTH01`) | identity check 4 |
| 1000A Payer | N3, N4, PER | not used | read and ignored |
| 1000B Payee | N1*PE | N104 payee NPI | NPI check-digit validation |
| 2000 | LX | not used | loop boundary |
| 2100 Claim | CLP | CLP01 hospital claim ID, CLP02 status, CLP03 billed, CLP04 paid, CLP05 patient responsibility (empty = 0), CLP06 claim filing indicator, CLP07 payer claim ID | lane, identity check 1, balancing |
| 2100 Claim | CAS | group, then (reason, amount) triples | claim-level adjustments |
| 2100 Claim | NM1*QC | NM109 member ID. NM103 and NM104 (names) are **skipped and never stored**. | identity check 2 |
| 2100 Claim | NM1*82 | NM109 rendering NPI | identity check 5 |
| 2100 Claim | DTM*232 / DTM*233 | statement period start and end | date-of-service fallback |
| 2100 Claim | REF, AMT, QTY (claim level) | read and ignored | tolerance |
| 2110 Service | SVC | SVC01 composite `HC:72148` (qualifier, code), SVC02 billed, SVC03 paid, SVC05 units | identity check 6, balancing |
| 2110 Service | DTM*472 | service date | identity check 3 (primary) |
| 2110 Service | CAS | group, (reason, amount) triples | service-level adjustments, denial code |
| 2110 Service | REF (for example `REF*6R`), AMT, QTY, LQ | REF*6R line item control is kept; the others are read and ignored | tolerance (Appendix B #3) |
| Trailer | SE, GE, IEA | counts and control numbers | envelope checks |

A new 2100 loop starts at each `CLP`. A new 2110 loop starts at each `SVC`. A segment tag that the
reader does not know, inside a known loop, is skipped rather than failing. Any `PLB` segment
fails validation because the demo does not support provider-level adjustments.

**Derived values**

- Denial code = `<CAS01>-<CAS02>` from the first service-level CAS. If there is none, it comes
  from the first claim-level CAS (hero claim: `CO-50`).
- Date of service = service-level `DTM*472`, or `DTM*232` if there is no DTM*472.
- Lane:

  | CLP02 | Denial code reason | Lane | Case status |
  |---|---|---|---|
  | `4` | `50` | `medical-necessity` | `new` |
  | `4` | anything else | `other-denial` | `other-denial` |
  | `1`, `2`, `3` with CLP04 > 0 | any | `paid` | `paid` |
  | anything else | any | `other-denial` | `other-denial` |

## 3. 837P (005010X222A1) segments read

| Loop | Segment | Elements read | Used for |
|---|---|---|---|
| Envelope | ISA, GS, ST | GS01 = `HC`, GS08 and ST03 = `005010X222A1` | envelope checks |
| Header | BHT | BHT03 batch reference | timeline only |
| 1000A/B | NM1*41, PER, NM1*40 | not used | read and ignored |
| 2000A | HL (code 20) | HL01, HL03 | hierarchy check |
| 2010AA Billing provider | NM1*85 | NM109 billing NPI | NPI check digit |
| 2010AA | N4 | N402 state (`WA`) | policy selection (state) |
| 2010AA | N3, REF*EI | not used | read and ignored |
| 2000B | HL (code 22), SBR | SBR03 group number, SBR09 claim filing indicator (`12`) | timeline only |
| 2010BA Subscriber | NM1*IL | NM109 member ID. Names are **skipped and never stored**. | identity check 2 |
| 2010BA | N3, N4, DMG | not used, never stored | read and ignored |
| 2010BB Payer | NM1*PR | NM109 payer ID (`NSTHLTH01`) | identity check 4 |
| 2300 Claim | CLM | CLM01 hospital claim ID, CLM02 total billed, CLM05 composite (place of service, qualifier, **frequency code**) | identity check 1; frequency 7 goes to needs-review |
| 2300 | HI | HI01 composite `ABK:M5416`, normalized to `M54.16` | packet header (diagnosis) |
| 2310B Rendering provider | NM1*82 | NM109 rendering NPI | identity check 5 |
| 2400 Service | LX | loop boundary | — |
| 2400 | SV1 | SV101 composite `HC:72148`, SV102 billed, SV103 unit basis, SV104 units | identity check 6 |
| 2400 | DTP*472 | DTP02 = `D8`, DTP03 service date | identity check 3 |
| 2400 | REF*6R | line item control | timeline only |
| Trailer | SE, GE, IEA | counts and control numbers | envelope checks |

## 4. Validation rules (`validate.py`)

Each rule produces a named failure. A file that fails any rule is rejected: the remit is recorded
as `rejected` with the rule name, one inbox audit event is written, and no case is created.

| ID | Rule | Applies to | Hero fixture value |
|---|---|---|---|
| X-01 | ISA is 106 characters; ISA13 = IEA02; IEA01 = number of GS groups | both | `000000905` / `000000712` |
| X-02 | GS06 = GE02; GE01 = number of ST sets in the group | both | `905` / `712` |
| X-03 | ST02 = SE02 | both | `0001` |
| X-04 | SE01 = number of segments from ST through SE inclusive | both | 835: **37**; 837P: **25** |
| X-05 | GS08 = `005010X221A1` (835) or `005010X222A1` (837P); ST03 = `005010X222A1` for 837P | both | — |
| X-06 | Per claim: CLP03 − CLP04 = sum of all CAS amounts at claim and service level | 835 | 4800 − 0 = 4800; 350 − 280 = 70; 620 − 0 = 620 |
| X-07 | Per service: SVC02 − SVC03 = sum of that service's CAS amounts | 835 | as above |
| X-08 | BPR02 = sum of CLP04 across all claims (no PLB allowed) | 835 | 280 |
| X-09 | CLP05 (empty = 0) = sum of CAS amounts with group `PR` | 835 | 0 for all three claims |
| X-10 | Every NPI (N1*PE, NM1*82, NM1*85) passes the Luhn check digit with prefix `80840` | both | `1234567893`, `1245319599` pass |
| X-11 | CLM02 = sum of SV102 | 837P | 4800 |
| X-12 | HL parent references point at an earlier HL; HL child flags are consistent | 837P | HL*1 (20), HL*2 (22) |
| X-13 | Dates are valid `CCYYMMDD` | both | `20260810`, `20260820` |

## 5. Required tests (written before the readers)

- `tests/fixtures/test_x12_fixtures.py`: both committed fixtures pass X-01 to X-13. Expected
  values are the hand-written numbers in the table above, not parser output.
- `tests/unit/test_tokenizer.py`: delimiters come from ISA (alternate delimiter copy); CRLF, LF,
  and no line breaks give identical segments; a truncated ISA raises `X12ParseError`.
- `tests/unit/test_remit835.py`: three claims read; hero denial code `CO-50` from service-level
  CAS; a copy with the CAS moved to claim level still yields `CO-50`; REF, DTM, AMT, QTY, and LQ
  after SVC are tolerated; lanes are `medical-necessity`, `paid`, `other-denial`; member names
  are not present in the parsed model.
- `tests/unit/test_claim837.py`: fields listed in section 3 equal the Appendix A3 "Extracted"
  line; `M5416` is normalized to `M54.16`; a frequency-7 copy is flagged.
- Negative validation copies (one rule broken per file): wrong SE count, unbalanced claim, BPR02
  mismatch, bad NPI check digit, GS08 wrong version.
