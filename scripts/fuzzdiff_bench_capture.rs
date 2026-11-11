//! Capture program for the "Side-by-side parser" bench of samiali38183.github.io.
//!
//! This file is NOT part of the fuzzdiff repository. `scripts/capture_fuzzdiff_bench.py` copies it into a scratch
//! clone of fuzzdiff at the tagged commit as `harness/examples/bench_capture.rs` and runs
//!
//!   cargo run --release -p fuzzdiff-harness --features mutants --example bench_capture
//!
//! It uses only the public API of the harness crate (compare_case, ffi::c_parse, ffi::c_chunked, the httparse
//! oracle's tri_head / tri_chunk_size / explain, the generator) plus the fuzzdiff crate and httparse themselves,
//! evaluates each curated input through picohttpparser (C), fuzzdiff (Rust) and httparse, and prints one JSON
//! document on stdout. Nothing is edited by hand: every result below was returned by a parser.
//!
//! Environment: BENCH_ROOT (the fuzzdiff clone, for corpus files), BENCH_COMMIT, BENCH_DATE, BENCH_RUSTC.

use fuzzdiff::mutants::{set_active, Mutant};
use fuzzdiff::{ChunkStatus, ChunkedDecoder, Config, Header, Status};
use fuzzdiff_harness::ffi::{self, HeadKind};
use fuzzdiff_harness::generate::{random_case, targeted_cases, Rng};
use fuzzdiff_harness::httparse_cases::{Kind, CLASSES, EXAMPLES};
use fuzzdiff_harness::httparse_oracle::{explain, tri_chunk_size, tri_head, Explanation};
use fuzzdiff_harness::{compare_case, describe, Case, DivergenceKind, Op, Outcome};
use std::fmt::Write as _;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::time::Instant;

const SLOTS: usize = 64; // header slots given to all three parsers, as in docs/DIFFERENTIAL_HTTPARSE.md
const BUDGET: u64 = 2_000_000;
const SHOW_HEADERS: usize = 6;

// ---------------------------------------------------------------- tiny JSON writer
enum J {
    Null,
    Bool(bool),
    Num(i64),
    Str(String),
    Arr(Vec<J>),
    Obj(Vec<(&'static str, J)>),
}
fn s(x: impl Into<String>) -> J {
    J::Str(x.into())
}
fn n(x: usize) -> J {
    J::Num(x as i64)
}
fn obj(v: Vec<(&'static str, J)>) -> J {
    J::Obj(v)
}
fn jstr(out: &mut String, x: &str) {
    out.push('"');
    for ch in x.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            c if (c as u32) < 0x20 => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out.push('"');
}
fn write_j(out: &mut String, j: &J, depth: usize) {
    match j {
        J::Null => out.push_str("null"),
        J::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        J::Num(x) => {
            let _ = write!(out, "{x}");
        }
        J::Str(x) => jstr(out, x),
        J::Arr(v) => {
            out.push('[');
            for (i, e) in v.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                if depth < 1 {
                    out.push('\n');
                }
                write_j(out, e, depth + 1);
            }
            out.push(']');
        }
        J::Obj(v) => {
            out.push('{');
            for (i, (k, e)) in v.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                if depth < 1 {
                    out.push('\n');
                }
                jstr(out, k);
                out.push(':');
                write_j(out, e, depth + 1);
            }
            out.push('}');
        }
    }
}

// ---------------------------------------------------------------- visible escapes
fn esc(b: &[u8]) -> String {
    let mut o = String::new();
    for &c in b {
        match c {
            b'\r' => o.push_str("\\r"),
            b'\n' => o.push_str("\\n"),
            b'\t' => o.push_str("\\t"),
            b'\\' => o.push_str("\\\\"),
            0x20..=0x7e => o.push(c as char),
            _ => {
                let _ = write!(o, "\\x{c:02x}");
            }
        }
    }
    o
}

// ---------------------------------------------------------------- per-parser results
fn headers_json(h: Vec<(Option<Vec<u8>>, Vec<u8>)>) -> (J, usize) {
    let total = h.len();
    let shown = h
        .into_iter()
        .take(SHOW_HEADERS)
        .map(|(nm, v)| J::Arr(vec![nm.map_or(J::Null, |x| s(esc(&x))), s(esc(&v))]))
        .collect();
    (J::Arr(shown), total)
}

struct Head {
    consumed: usize,
    method: Vec<u8>,
    path: Vec<u8>,
    reason: Vec<u8>,
    minor: i32,
    status: i32,
    headers: Vec<(Option<Vec<u8>>, Vec<u8>)>,
}

fn head_json(op: Op, verdict: &str, detail: Option<String>, h: Option<Head>) -> J {
    let mut v = vec![("verdict", s(verdict))];
    if let Some(d) = detail {
        v.push(("error", s(d)));
    }
    if let Some(h) = h {
        v.push(("consumed", n(h.consumed)));
        if op == Op::Request {
            v.push(("method", s(esc(&h.method))));
            v.push(("target", s(esc(&h.path))));
        }
        if op != Op::Headers {
            v.push(("minor", J::Num(i64::from(h.minor))));
        }
        if op == Op::Response {
            v.push(("status", J::Num(i64::from(h.status))));
            v.push(("reason", s(esc(&h.reason))));
        }
        let (hj, total) = headers_json(h.headers);
        v.push(("headers", hj));
        v.push(("nheaders", n(total)));
    }
    obj(v)
}

fn c_head_json(op: Op, data: &[u8]) -> J {
    let kind = match op {
        Op::Request => HeadKind::Request,
        Op::Response => HeadKind::Response,
        _ => HeadKind::Headers,
    };
    let c = ffi::c_parse(kind, data, 0, SLOTS);
    match c.ret {
        -2 => return head_json(op, "partial", None, None),
        -1 => return head_json(op, "error", None, None),
        _ => {}
    }
    let sl = |(o, l): (usize, usize)| data[o..o + l].to_vec();
    let headers = c
        .headers
        .iter()
        .map(|h| (h.name.map(sl), sl(h.value)))
        .collect();
    head_json(
        op,
        "complete",
        None,
        Some(Head {
            consumed: c.ret as usize,
            method: sl(c.method),
            path: sl(c.path),
            reason: sl(c.reason),
            minor: c.minor_version,
            status: c.status,
            headers,
        }),
    )
}

fn rust_head_json(op: Op, data: &[u8], strict: bool) -> J {
    let cfg = Config {
        reject_obs_fold: strict,
    };
    let r = catch_unwind(AssertUnwindSafe(|| {
        let mut hs = vec![Header::EMPTY; SLOTS];
        let conv = |n_: usize, hs: &[Header<'_>]| -> Vec<(Option<Vec<u8>>, Vec<u8>)> {
            hs.iter()
                .take(n_)
                .map(|h| (h.name.map(<[u8]>::to_vec), h.value.to_vec()))
                .collect()
        };
        match op {
            Op::Request => cfg.parse_request(data, &mut hs, 0).map(|st| match st {
                Status::Partial => None,
                Status::Complete(r) => Some(Head {
                    consumed: r.consumed,
                    method: r.method.to_vec(),
                    path: r.path.to_vec(),
                    reason: vec![],
                    minor: i32::from(r.minor_version),
                    status: 0,
                    headers: conv(r.num_headers, &hs),
                }),
            }),
            Op::Response => cfg.parse_response(data, &mut hs, 0).map(|st| match st {
                Status::Partial => None,
                Status::Complete(r) => Some(Head {
                    consumed: r.consumed,
                    method: vec![],
                    path: vec![],
                    reason: r.reason.to_vec(),
                    minor: i32::from(r.minor_version),
                    status: i32::from(r.status),
                    headers: conv(r.num_headers, &hs),
                }),
            }),
            _ => cfg.parse_headers(data, &mut hs, 0).map(|st| match st {
                Status::Partial => None,
                Status::Complete(r) => Some(Head {
                    consumed: r.consumed,
                    method: vec![],
                    path: vec![],
                    reason: vec![],
                    minor: 0,
                    status: 0,
                    headers: conv(r.num_headers, &hs),
                }),
            }),
        }
    }));
    match r {
        Err(_) => head_json(op, "panic", Some("the parser panicked".into()), None),
        Ok(Err(e)) => head_json(op, "error", Some(format!("{e:?}")), None),
        Ok(Ok(None)) => head_json(op, "partial", None, None),
        Ok(Ok(Some(h))) => head_json(op, "complete", None, Some(h)),
    }
}

fn hp_head_json(op: Op, data: &[u8]) -> J {
    let mut hs = [httparse::EMPTY_HEADER; SLOTS];
    let conv = |h: &[httparse::Header<'_>]| -> Vec<(Option<Vec<u8>>, Vec<u8>)> {
        h.iter()
            .map(|h| (Some(h.name.as_bytes().to_vec()), h.value.to_vec()))
            .collect()
    };
    match op {
        Op::Request => {
            let mut r = httparse::Request::new(&mut hs);
            match r.parse(data) {
                Ok(httparse::Status::Partial) => head_json(op, "partial", None, None),
                Ok(httparse::Status::Complete(c)) => head_json(
                    op,
                    "complete",
                    None,
                    Some(Head {
                        consumed: c,
                        method: r.method.unwrap_or("").as_bytes().to_vec(),
                        path: r.path.unwrap_or("").as_bytes().to_vec(),
                        reason: vec![],
                        minor: i32::from(r.version.unwrap_or(0)),
                        status: 0,
                        headers: conv(r.headers),
                    }),
                ),
                Err(e) => head_json(op, "error", Some(format!("{e:?}")), None),
            }
        }
        Op::Response => {
            let mut r = httparse::Response::new(&mut hs);
            match r.parse(data) {
                Ok(httparse::Status::Partial) => head_json(op, "partial", None, None),
                Ok(httparse::Status::Complete(c)) => head_json(
                    op,
                    "complete",
                    None,
                    Some(Head {
                        consumed: c,
                        method: vec![],
                        path: vec![],
                        reason: r.reason.unwrap_or("").as_bytes().to_vec(),
                        minor: i32::from(r.version.unwrap_or(0)),
                        status: i32::from(r.code.unwrap_or(0)),
                        headers: conv(r.headers),
                    }),
                ),
                Err(e) => head_json(op, "error", Some(format!("{e:?}")), None),
            }
        }
        _ => match httparse::parse_headers(data, &mut hs) {
            Ok(httparse::Status::Partial) => head_json(op, "partial", None, None),
            Ok(httparse::Status::Complete((c, h))) => head_json(
                op,
                "complete",
                None,
                Some(Head {
                    consumed: c,
                    method: vec![],
                    path: vec![],
                    reason: vec![],
                    minor: 0,
                    status: 0,
                    headers: conv(h),
                }),
            ),
            Err(e) => head_json(op, "error", Some(format!("{e:?}")), None),
        },
    }
}

fn chunk_result(verdict: &str, detail: Option<String>, out: &[u8], left: &[u8]) -> J {
    let mut v = vec![("verdict", s(verdict))];
    if let Some(d) = detail {
        v.push(("error", s(d)));
    }
    if verdict == "complete" {
        v.push(("decoded", s(esc(out))));
        v.push(("decoded_len", n(out.len())));
        v.push(("leftover", s(esc(left))));
        v.push(("leftover_len", n(left.len())));
    }
    obj(v)
}

fn c_chunk_json(data: &[u8]) -> J {
    let r = ffi::c_chunked(data, &[data.len()], false);
    match r.steps.last().map(|x| x.ret) {
        Some(-1) => chunk_result("error", None, &[], &[]),
        Some(-2) | None => chunk_result("partial", None, &[], &[]),
        Some(_) => chunk_result("complete", None, &r.out, &r.left),
    }
}

fn rust_chunk_json(data: &[u8]) -> J {
    let mut dec = ChunkedDecoder::new(false);
    let mut buf = data.to_vec();
    let d = dec.decode(&mut buf);
    match d.status {
        ChunkStatus::Incomplete => chunk_result("partial", None, &[], &[]),
        ChunkStatus::Error(e) => chunk_result("error", Some(format!("{e:?}")), &[], &[]),
        ChunkStatus::Complete { leftover } => {
            chunk_result("complete", None, &buf[..d.len], &buf[d.len..d.len + leftover])
        }
    }
}

fn hp_chunk_json(data: &[u8]) -> J {
    match httparse::parse_chunk_size(data) {
        Ok(httparse::Status::Complete((used, size))) => obj(vec![
            ("verdict", s("complete")),
            ("consumed", n(used)),
            ("size", J::Num(size as i64)),
        ]),
        Ok(httparse::Status::Partial) => obj(vec![("verdict", s("partial"))]),
        Err(e) => obj(vec![("verdict", s("error")), ("error", s(format!("{e:?}")))]),
    }
}

// ---------------------------------------------------------------- inputs
#[derive(Clone)]
enum Source {
    Curated(&'static str, &'static str), // class id, label
    Corpus(&'static str),                // path under corpus/
    Planted(Mutant, Vec<u8>, Op, &'static str),
}

struct Spec {
    id: &'static str,
    group: &'static str,
    title: &'static str,
    source: Source,
    strict: bool,
}

fn specs() -> Vec<Spec> {
    use Source::*;
    let sp = |id, group, title, source| Spec { id, group, title, source, strict: false };
    vec![
        sp("baseline", "Request line", "Baseline request", Curated("agree", "baseline request")),
        sp("http10", "Request line", "HTTP/1.0 request (corpus)", Corpus("request/picohttpparser-simple.bin")),
        sp("double-sp", "Request line", "Two SP after the method", Curated("sp-count", "two SP after the method")),
        sp("http12", "Request line", "HTTP/1.2", Curated("version", "HTTP/1.2 request")),
        sp("hi-target", "Request line", "0x80 in the target", Curated("hi-target", "0x80 in the target")),
        sp("nul-target", "Request line", "NUL byte in the target (corpus)", Corpus("request/hand-nul-in-path.bin")),
        sp("lead-crlf", "Request line", "Two empty lines before the request", Curated("lead-crlf", "two empty lines before the request")),
        sp("obs-fold", "Headers", "Obsolete line folding", Curated("fold", "request, SP continuation")),
        Spec { id: "obs-fold-strict", group: "Headers", title: "Obsolete line folding, strict mode (D1)", source: Curated("fold", "request, SP continuation"), strict: true },
        sp("multi-fold", "Headers", "Several folded lines (corpus)", Corpus("request/hand-fold-after-header.bin")),
        sp("many-headers", "Headers", "100 header lines, 64 slots (corpus)", Corpus("request/hand-many-headers-100.bin")),
        sp("status-sp", "Response", "Two SP after the status code", Curated("sp-count", "two SP after the status code")),
        sp("chunk-lf-ext", "Chunked body", "Bare LF inside a chunk extension", Curated("chunk-ext", "bare LF inside an extension")),
        sp("chunk-empty", "Chunked body", "Empty chunk size", Curated("chunk-size", "empty size")),
        sp("chunk-17", "Chunked body", "17 hex digits in a chunk size", Curated("chunk-size", "17 hex digits (overflow of u64)")),
        sp("trunc-version", "Truncated input", "Version cut after HTTP/1.", Curated("timing", "version cut after 'HTTP/1.'")),
        sp("trunc-corpus", "Truncated input", "Request cut after the target start (corpus)", Corpus("request/picohttpparser-incomplete-3.bin")),
        sp("mut-len", "Planted bug", "Seeded bug HeaderLenOffByOne",
            Planted(Mutant::HeaderLenOffByOne, b"GET / HTTP/1.1\r\nX-Long: 0123456789abcdefghij\r\n\r\n".to_vec(), Op::Request, "HeaderLenOffByOne")),
        sp("mut-bounds", "Planted bug", "Seeded bug MissingBoundsCheck",
            Planted(Mutant::MissingBoundsCheck, b"GET / HTTP/1.1".to_vec(), Op::Request, "MissingBoundsCheck")),
    ]
}

fn op_name(op: Op) -> &'static str {
    match op {
        Op::Request => "request",
        Op::Response => "response",
        Op::Headers => "headers",
        Op::Chunked => "chunked",
    }
}

fn outcome_json(o: &Outcome) -> J {
    match o {
        Outcome::Equal => obj(vec![("kind", s("Equal"))]),
        Outcome::BothReject => obj(vec![("kind", s("BothReject"))]),
        Outcome::RustStricter(d) => obj(vec![("kind", s("RustStricter")), ("deviation", s(d.id()))]),
        Outcome::Divergence(d) => obj(vec![
            ("kind", s("Divergence")),
            (
                "how",
                s(match d.kind {
                    DivergenceKind::RustPanic => "RustPanic",
                    DivergenceKind::ResultMismatch => "ResultMismatch",
                    DivergenceKind::CBadOffsets => "CBadOffsets",
                }),
            ),
        ]),
    }
}

fn class_title(id: &str) -> &'static str {
    CLASSES.iter().find(|c| c.0 == id).map(|c| c.1).expect("class")
}

fn main() {
    let default_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(|info| {
        // the MissingBoundsCheck mutant panics by design; any other panic must be visible
        if !info.to_string().contains("index out of bounds") {
            eprintln!("{info}");
        }
    }));
    let _ = default_hook;
    let root = std::path::PathBuf::from(std::env::var("BENCH_ROOT").expect("BENCH_ROOT"));
    let mut inputs = Vec::new();
    for sp in specs() {
        set_active(None);
        let (bytes, op, doc, mutant, label_src): (Vec<u8>, Op, J, Option<(Mutant, &str)>, J) = match &sp.source {
            Source::Curated(class, label) => {
                let e = EXAMPLES
                    .iter()
                    .find(|e| e.class == *class && e.label == *label)
                    .unwrap_or_else(|| panic!("curated example not found: {class}/{label}"));
                let op = match e.kind {
                    Kind::Request => Op::Request,
                    Kind::Response => Op::Response,
                    Kind::Headers => Op::Headers,
                    Kind::ChunkSize => Op::Chunked,
                };
                (
                    e.bytes.to_vec(),
                    op,
                    obj(vec![
                        ("class", s(class_title(class))),
                        ("class_id", s(*class)),
                        ("label", s(e.label)),
                        ("pattern", s(e.expect)),
                    ]),
                    None,
                    obj(vec![("kind", s("httparse-curated")), ("ref", s(format!("{class}: {}", e.label)))]),
                )
            }
            Source::Corpus(path) => {
                let bytes = std::fs::read(root.join("corpus").join(path)).expect("corpus file");
                let op = if path.starts_with("request/") {
                    Op::Request
                } else if path.starts_with("response/") {
                    Op::Response
                } else if path.starts_with("headers/") {
                    Op::Headers
                } else {
                    Op::Chunked
                };
                (bytes, op, J::Null, None, obj(vec![("kind", s("corpus")), ("ref", s(format!("corpus/{path}")))]))
            }
            Source::Planted(m, bytes, op, name) => (
                bytes.clone(),
                *op,
                J::Null,
                Some((*m, *name)),
                obj(vec![("kind", s("seeded-bug")), ("ref", s(*name))]),
            ),
        };

        // C and the Rust port (with the mutant switched on only for the planted-bug inputs)
        let mut case = Case::new(op, bytes.clone());
        case.max_headers = SLOTS;
        case.strict = sp.strict;
        let (c_res, rust_res, outcome) = if let Some((m, _)) = &mutant {
            set_active(Some(*m));
            let r = (c_head_json(op, &bytes), rust_head_json(op, &bytes, false), compare_case(&case));
            set_active(None);
            r
        } else if op == Op::Chunked {
            (c_chunk_json(&bytes), rust_chunk_json(&bytes), compare_case(&case))
        } else {
            (c_head_json(op, &bytes), rust_head_json(op, &bytes, sp.strict), compare_case(&case))
        };

        // httparse: head parsing, or the first chunk-size line when the body after it is well formed (curated only)
        let is_curated = matches!(sp.source, Source::Curated(..));
        let (hp_res, tri_pattern, explained): (J, Option<String>, J) = if op == Op::Chunked {
            if is_curated {
                let t = tri_chunk_size(&bytes);
                (hp_chunk_json(&bytes), Some(t.pattern()), J::Null)
            } else {
                (J::Null, None, J::Null)
            }
        } else {
            let t = tri_head(op, &bytes);
            let ex = if t.agrees() {
                s("agree")
            } else {
                match explain(op, &bytes) {
                    Explanation::Features(f) => s(format!("features: {}", f.join(", "))),
                    Explanation::EarlyReject => s("early-reject"),
                    Explanation::HeaderCap => s("header-cap"),
                    Explanation::Unexplained => panic!("unexplained disagreement for {}", sp.id),
                }
            };
            (hp_head_json(op, &bytes), Some(t.pattern()), ex)
        };

        inputs.push(obj(vec![
            ("id", s(sp.id)),
            ("group", s(sp.group)),
            ("title", s(sp.title)),
            ("source", label_src),
            ("op", s(op_name(op))),
            ("strict", J::Bool(sp.strict)),
            ("slots", n(SLOTS)),
            ("bytes_len", n(bytes.len())),
            ("bytes", s(esc(&bytes))),
            ("c", c_res),
            ("rust", rust_res),
            ("httparse", hp_res),
            ("harness", outcome_json(&outcome)),
            ("pattern", tri_pattern.map_or(J::Null, s)),
            ("explained_by", explained),
            ("doc", doc),
            ("mutant", mutant.map_or(J::Null, |(_, nm)| s(nm))),
        ]));
    }
    set_active(None);

    // ---- seeded bugs: inputs until the generator finds each (same loop as harness/tests/mutants.rs)
    let mut muts = Vec::new();
    for m in Mutant::ALL {
        set_active(Some(m));
        let start = Instant::now();
        let mut found: Option<(u64, String, String)> = None;
        for i in 0..BUDGET {
            let case = random_case(&mut Rng::new(i + 1));
            if let Outcome::Divergence(d) = compare_case(&case) {
                let how = match d.kind {
                    DivergenceKind::RustPanic => "RustPanic",
                    DivergenceKind::ResultMismatch => "ResultMismatch",
                    DivergenceKind::CBadOffsets => "CBadOffsets",
                };
                found = Some((i + 1, how.into(), describe(&case).chars().take(160).collect()));
                break;
            }
        }
        let secs = start.elapsed().as_secs_f64();
        let targeted = targeted_cases().into_iter().enumerate().find_map(|(i, c)| match compare_case(&c) {
            Outcome::Divergence(d) => Some((i + 1, format!("{:?}", d.kind))),
            _ => None,
        });
        set_active(None);
        muts.push(obj(vec![
            ("name", s(format!("{m:?}"))),
            ("generator_inputs", found.as_ref().map_or(J::Null, |f| J::Num(f.0 as i64))),
            ("generator_seconds", J::Str(format!("{secs:.6}"))),
            ("generator_how", found.as_ref().map_or(J::Null, |f| s(f.1.clone()))),
            ("first_failing_input", found.as_ref().map_or(J::Null, |f| s(f.2.clone()))),
            ("budget", J::Num(BUDGET as i64)),
            ("targeted_case", targeted.as_ref().map_or(J::Null, |t| n(t.0))),
            ("targeted_how", targeted.as_ref().map_or(J::Null, |t| s(t.1.clone()))),
        ]));
    }
    let start = Instant::now();
    let mut diverged = 0;
    for i in 0..BUDGET / 4 {
        if compare_case(&random_case(&mut Rng::new(i + 1))).is_divergence() {
            diverged += 1;
        }
    }
    let ntargeted = targeted_cases().len();
    for c in targeted_cases() {
        if compare_case(&c).is_divergence() {
            diverged += 1;
        }
    }
    let control = obj(vec![
        ("inputs", J::Num((BUDGET / 4) as i64)),
        ("targeted_cases", n(ntargeted)),
        ("divergences", J::Num(diverged)),
        ("seconds", J::Str(format!("{:.6}", start.elapsed().as_secs_f64()))),
    ]);

    let doc = obj(vec![
        (
            "meta",
            obj(vec![
                ("tool", s("fuzzdiff")),
                ("version", s("0.2.0")),
                ("tag", s("v0.2.0")),
                ("commit", s(std::env::var("BENCH_COMMIT").unwrap_or_default())),
                ("c_reference", s("picohttpparser dd573d8")),
                ("httparse", s("1.10.1 (default configuration)")),
                ("slots", n(SLOTS)),
                ("captured", s(std::env::var("BENCH_DATE").unwrap_or_default())),
                ("rustc", s(std::env::var("BENCH_RUSTC").unwrap_or_default())),
                ("platform", s("Windows, release build, MSVC build of the C code")),
                ("command", s("cargo run --release -p fuzzdiff-harness --features mutants --example bench_capture")),
            ]),
        ),
        ("inputs", J::Arr(inputs)),
        ("mutants", J::Arr(muts)),
        ("control", control),
    ]);
    let mut out = String::new();
    write_j(&mut out, &doc, 0);
    println!("{out}");
}
