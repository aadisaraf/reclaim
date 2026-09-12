# Contract: mock-hospital (FHIR R4)

**Service**: `mock-hospital`, a FastAPI app in `mocks/hospital/app.py`. It serves JSON fixtures from
`fixtures/fhir/`.

**Base URL**:
- Local: `http://mock-hospital.example/fhir/R4`, from the compose network alias.
- Appendix A5 names `https://mock-hospital.example/fhir/R4`. We run http locally (research.md §11).

**Label**: every response carries the header `X-Synthetic-Data: true`, and the service
description says "SYNTHETIC DEMO DATA".

## Auth (mock of SMART Backend Services)

| Endpoint | Behavior |
|---|---|
| `GET /fhir/R4/.well-known/smart-configuration` | 200 JSON with `token_endpoint` `<host>/auth/token`, `grant_types_supported` `["client_credentials"]`, `token_endpoint_auth_methods_supported` `["client_secret_post"]`, `scopes_supported` (the scopes below). No auth needed. |
| `POST /auth/token` | Form fields `grant_type=client_credentials`, `client_id`, `client_secret`, and optional `scope`. Valid values come from `HOSPITAL_CLIENT_ID` and `HOSPITAL_CLIENT_SECRET` in `.env`. Returns 200 `{"access_token": "<random>", "token_type": "Bearer", "expires_in": 3600, "scope": "system/Encounter.rs system/Patient.rs system/Coverage.rs system/Condition.rs system/ServiceRequest.rs system/Procedure.rs system/DiagnosticReport.rs system/Observation.rs system/DocumentReference.rs system/MedicationRequest.rs system/Binary.r"}`. A bad client returns 401 `{"error": "invalid_client"}`, following OAuth. |

Every `/fhir/R4/*` request (except smart-configuration) needs `Authorization: Bearer <token>`,
where the token was issued by this process. Responses use `Content-Type: application/fhir+json`.

Production path (not built): SMART Backend Services with a signed JWT client assertion
(`private_key_jwt`).

## Interactions

| Request | Result |
|---|---|
| `GET /Encounter/{id}` | read |
| `GET /Patient/{id}` | read |
| `GET /Binary/{id}` | read; `{"resourceType":"Binary","id":…,"contentType":"text/plain","data":"<base64>"}` |
| `GET /Coverage?patient={id}` | searchset |
| `GET /Condition?patient={id}` | searchset |
| `GET /ServiceRequest?patient={id}` | searchset |
| `GET /Procedure?patient={id}` | searchset |
| `GET /DiagnosticReport?patient={id}` | searchset |
| `GET /Observation?patient={id}` | searchset |
| `GET /DocumentReference?patient={id}` | searchset |
| `GET /MedicationRequest?patient={id}` | searchset; for `patient-0042` it returns `total: 0` and no `entry` |
| `GET /{type}/{id}` for Coverage, Condition, ServiceRequest, Procedure, DiagnosticReport, Observation, DocumentReference, Practitioner, Organization | read (used by tests and the UI "source" link) |

A searchset Bundle looks like
`{"resourceType":"Bundle","type":"searchset","total":n,"link":[{"relation":"self","url":…}],"entry":[{"fullUrl":…,"resource":…,"search":{"mode":"match"}}]}`.

Search supports only the `patient` parameter, with a bare id or `Patient/<id>`.

## Errors (OperationOutcome)

`{"resourceType":"OperationOutcome","issue":[{"severity":"error","code":"<code>","diagnostics":"<text>"}]}`

| Status | `code` | When |
|---|---|---|
| 401 | `login` | Missing, invalid, or unknown bearer token |
| 404 | `not-found` | Unknown type or id, including a hidden resource in missing-evidence mode |
| 400 | `not-supported` | A search parameter other than `patient`, or a missing `patient` |

## Fixture resources

Values follow Appendix A5 exactly. Each resource is one file in `fixtures/fhir/`.

| File | Date field used for lookback |
|---|---|
| `Patient-patient-0042.json` (identifier MR `MRN-0042`) | none |
| `Coverage-coverage-0042.json` (`subscriberId` `MEMBER-448820`; `class` plan "Commercial PPO", group `NST-PPO-GRP-01`; payor identifier `NSTHLTH01`) | none |
| `Practitioner-practitioner-lee.json` (NPI `1234567893`) | none |
| `Organization-mock-hospital.json` (NPI `1245319599`, Seattle WA) | none |
| `Encounter-encounter-20260810-42.json` (period `2026-08-10T09:00:00Z`–`09:45:00Z`) | none |
| `Condition-condition-100.json` (M54.16, onset 2026-05-20) | `recordedDate` 2026-05-28 |
| `DiagnosticReport-report-xr-555.json` | `effectiveDateTime` 2026-05-28 |
| `Observation-obs-pain-7781.json` (LOINC 72514-3, value 8) | `effectiveDateTime` 2026-08-10 |
| `ServiceRequest-order-901.json` (CPT 72148, `reasonReference` Condition/condition-100, `note[0].text` with the rationale) | `authoredOn` 2026-08-10 |
| `Procedure-procedure-902.json` (`basedOn` ServiceRequest/order-901) | `performedDateTime` 2026-08-10 |
| `DocumentReference-note-progress-031.json` + `Binary-note-progress-031.json` (no mention of prior treatment) | `date` 2026-08-10 |
| `DocumentReference-treatment-note-022.json` + `Binary-treatment-note-022.json` (PT 2026-06-02 to 2026-07-14, 6 weeks, home exercise program, not improved) | `date` 2026-07-14 |
| `DocumentReference-note-ortho-2019-004.json` + `Binary-note-ortho-2019-004.json` (2019 ankle sprain) | `date` 2019-03-02 |

The note texts are written by hand at implementation time to match the A5 descriptions. After
they are written, their exact wording is frozen, because replay keys hash them.

## Presenter control (not FHIR; demo only)

These endpoints need the same bearer token as the FHIR routes.

| Endpoint | Behavior |
|---|---|
| `PUT /_control/missing-evidence` `{"enabled": true\|false}` | While enabled, `DocumentReference/treatment-note-022` is left out of searches (so `total` drops by 1) and read, along with `Binary/treatment-note-022`, returns 404 `not-found`. |
| `GET /_control/state` | Returns `{"missingEvidence": bool}` |
| `POST /_control/reset` | Sets `missingEvidence` to false |

The state lives in memory, and the default after a restart is off.

## Tests

- `tests/fixtures/test_fhir_fixtures.py`: every fixture parses with the fhir.resources R4B models,
  and Appendix A5 values are asserted by hand.
- `tests/contract/test_mock_hospital.py`:
  - token flow, plus 401 without a token
  - a searchset Bundle shape for each type
  - MedicationRequest returns total 0
  - a 400 on an unsupported parameter
  - the toggle hides both resources and reset restores them
