| Class | Example | picohttpparser | fuzzdiff | httparse | Pattern | Stricter |
|---|---|---|---|---|---|---|
| Accepted by all three (context) | `GET / HTTP/1.1\r\nHost: a\r\n\r\n` (baseline request) | complete | complete | complete | CCC | same |
| Accepted by all three (context) | `POST / HTTP/1.1\r\nHost: a\r\nContent-Length: 4\r\nTransfer-Encoding: chunked\r\n\r\n` (Content-Length and Transfer-Encoding both present) | complete | complete | complete | CCC | same |
| Accepted by all three (context) | `POST / HTTP/1.1\r\nHost: a\r\nContent-Length: 4\r\nContent-Length: 5\r\n\r\n` (duplicate Content-Length, different values) | complete | complete | complete | CCC | same |
| Accepted by all three (context) | `POST / HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: xchunked\r\n\r\n` (Transfer-Encoding: xchunked) | complete | complete | complete | CCC | same |
| Accepted by all three (context) | `GET http://a/ HTTP/1.1\r\nHost: a\r\n\r\n` (absolute-form target) | complete | complete | complete | CCC | same |
| Accepted by all three (context) | `OPTIONS * HTTP/1.1\r\nHost: a\r\n\r\n` (asterisk-form target) | complete | complete | complete | CCC | same |
| Accepted by all three (context) | `get / HTTP/1.1\r\n\r\n` (lower-case method) | complete | complete | complete | CCC | same |
| Accepted by all three (context) | `G@T / HTTP/1.1\r\n\r\n` (non-token method) | reject | reject | reject | RRR | same |
| Accepted by all three (context) | `GET / HTTP/1.1 \r\n\r\n` (trailing SP after the version) | reject | reject | reject | RRR | same |
| Accepted by all three (context) | `GET / HTTP/1.1\r\nA: b\tc\r\n\r\n` (HTAB inside a field value) | complete | complete | complete | CCC | same |
| Accepted by all three (context) | `GET / HTTP/1.1\r\n: x\r\n\r\n` (empty field name) | reject | reject | reject | RRR | same |
| Accepted by all three (context) | `GET / HTTP/1.1\r\nfoo\r\n\r\n` (header line without a colon) | reject | reject | reject | RRR | same |
| Accepted by all three (context) | `HTTP/1.1 200\r\n\r\n` (response with no reason phrase) | complete | complete | complete | CCC | same |
| Obsolete line folding | `GET / HTTP/1.1\r\nA: b\r\n c\r\n\r\n` (request, SP continuation) | complete | complete | reject | CCR | httparse |
| Obsolete line folding | `GET / HTTP/1.1\r\nA: b\r\n\tc\r\n\r\n` (request, HTAB continuation) | complete | complete | reject | CCR | httparse |
| Obsolete line folding | `A: b\r\n c\r\n\r\n` (header block, SP continuation) | complete | complete | reject | CCR | httparse |
| Obsolete line folding | `HTTP/1.1 200 OK\r\nA: b\r\n c\r\n\r\n` (response, SP continuation) | complete | complete | reject | CCR | httparse |
| Whitespace before the first header line | `GET / HTTP/1.1\r\n A: b\r\n\r\n` (request, SP before the first header) | reject | reject | reject | RRR | same |
| Whitespace before the first header line | ` A: b\r\n\r\n` (header block, SP before the first header) | reject | reject | reject | RRR | same |
| Number of SP between start-line elements | `GET  / HTTP/1.1\r\n\r\n` (two SP after the method) | complete | complete | reject | CCR | httparse |
| Number of SP between start-line elements | `GET /  HTTP/1.1\r\n\r\n` (two SP before the version) | complete | complete | reject | CCR | httparse |
| Number of SP between start-line elements | `HTTP/1.1 200  OK\r\n\r\n` (two SP after the status code) | complete | complete | complete | CCC! | same verdict, fields differ |
| Other whitespace as a start-line separator | `GET\t/ HTTP/1.1\r\n\r\n` (HTAB after the method) | reject | reject | reject | RRR | same |
| Other whitespace as a start-line separator | `GET /\tHTTP/1.1\r\n\r\n` (HTAB before the version) | reject | reject | reject | RRR | same |
| HTTP version digits | `GET / HTTP/1.2\r\n\r\n` (HTTP/1.2 request) | complete | complete | reject | CCR | httparse |
| HTTP version digits | `GET / HTTP/1.9\r\n\r\n` (HTTP/1.9 request) | complete | complete | reject | CCR | httparse |
| HTTP version digits | `HTTP/1.2 200 OK\r\n\r\n` (HTTP/1.2 response) | complete | complete | reject | CCR | httparse |
| HTTP version digits | `GET / HTTP/2.0\r\n\r\n` (HTTP/2.0 request) | reject | reject | reject | RRR | same |
| HTTP version digits | `GET / HTTP/0.9\r\n\r\n` (HTTP/0.9 request) | reject | reject | reject | RRR | same |
| HTTP version digits | `GET / HTTP/1.10\r\n\r\n` (HTTP/1.10 request) | reject | reject | reject | RRR | same |
| HTTP version digits | `GET / http/1.1\r\n\r\n` (lower-case http/1.1) | reject | reject | reject | RRR | same |
| Octets 0x80-0xFF in the request-target | `GET /\x80 HTTP/1.1\r\n\r\n` (0x80 in the target) | complete | complete | reject | CCR | httparse |
| Octets 0x80-0xFF in the request-target | `GET /\xff HTTP/1.1\r\n\r\n` (0xFF in the target) | complete | complete | reject | CCR | httparse |
| Octets 0x80-0xFF in a field value | `GET / HTTP/1.1\r\nA: \x80\r\n\r\n` (0x80 in a field value) | complete | complete | complete | CCC | same |
| Octets 0x80-0xFF in a field value | `HTTP/1.1 200 OK\r\nA: \xff\r\n\r\n` (0xFF in a response field value) | complete | complete | complete | CCC | same |
| Octets 0x80-0xFF in a field name | `GET / HTTP/1.1\r\n\x80: x\r\n\r\n` (0x80 in a field name) | reject | reject | reject | RRR | same |
| Field-name characters outside tchar | `GET / HTTP/1.1\r\nA@B: x\r\n\r\n` (@ in a field name) | reject | reject | reject | RRR | same |
| Field-name characters outside tchar | `GET / HTTP/1.1\r\nA(B: x\r\n\r\n` (( in a field name) | reject | reject | reject | RRR | same |
| Field-name characters outside tchar | `GET / HTTP/1.1\r\nA B: x\r\n\r\n` (SP inside a field name) | reject | reject | reject | RRR | same |
| Field-name characters outside tchar | `GET / HTTP/1.1\r\nA_B~: x\r\n\r\n` (underscore and tilde in a field name (valid tchar)) | complete | complete | complete | CCC | same |
| Whitespace between field name and colon | `GET / HTTP/1.1\r\nA : b\r\n\r\n` (SP before the colon, request) | reject | reject | reject | RRR | same |
| Whitespace between field name and colon | `HTTP/1.1 200 OK\r\nA : b\r\n\r\n` (SP before the colon, response) | reject | reject | reject | RRR | same |
| Whitespace between field name and colon | `GET / HTTP/1.1\r\nA\t: b\r\n\r\n` (HTAB before the colon) | reject | reject | reject | RRR | same |
| Bare LF as line terminator | `GET / HTTP/1.1\nHost: a\n\n` (LF-only line endings) | complete | complete | complete | CCC | same |
| Bare LF as line terminator | `GET / HTTP/1.1\nHost: a\r\n\r\n` (LF after the start-line only) | complete | complete | complete | CCC | same |
| Bare CR | `GET / HTTP/1.1\r\r\nHost: a\r\n\r\n` (bare CR after the start-line) | reject | reject | reject | RRR | same |
| Bare CR | `GET / HTTP/1.1\r\nA: b\rc\r\n\r\n` (bare CR inside a field value) | reject | reject | reject | RRR | same |
| NUL and other control octets | `GET / HTTP/1.1\r\nA: b\x00c\r\n\r\n` (NUL in a field value) | reject | reject | reject | RRR | same |
| NUL and other control octets | `GET /\x00 HTTP/1.1\r\n\r\n` (NUL in the target) | reject | reject | reject | RRR | same |
| NUL and other control octets | `GET / HTTP/1.1\r\nA: b\x7fc\r\n\r\n` (DEL in a field value) | reject | reject | reject | RRR | same |
| NUL and other control octets | `GET / HTTP/1.1\r\nA: b\x01c\r\n\r\n` (0x01 in a field value) | reject | reject | reject | RRR | same |
| NUL and other control octets | `GET /\x01 HTTP/1.1\r\n\r\n` (0x01 in the target) | reject | reject | reject | RRR | same |
| Empty lines before the start-line | `\r\nGET / HTTP/1.1\r\n\r\n` (one empty line before the request) | complete | complete | complete | CCC | same |
| Empty lines before the start-line | `\r\n\r\nGET / HTTP/1.1\r\n\r\n` (two empty lines before the request) | reject | reject | complete | RRC | picohttpparser |
| Status-code range | `HTTP/1.1 600 X\r\n\r\n` (status 600) | reject | reject | complete | RRC | picohttpparser |
| Status-code range | `HTTP/1.1 099 X\r\n\r\n` (status 099) | reject | reject | complete | RRC | picohttpparser |
| Status-code range | `HTTP/1.1 999 X\r\n\r\n` (status 999) | reject | reject | complete | RRC | picohttpparser |
| Status-code range | `HTTP/1.1 20 X\r\n\r\n` (two-digit status) | reject | reject | reject | RRR | same |
| Reason-phrase content | `HTTP/1.1 200 OK\xff\r\n\r\n` (0xFF in the reason phrase) | complete | complete | complete | CCC! | same verdict, fields differ |
| Reason-phrase content | `HTTP/1.1 200 \tOK\r\n\r\n` (HTAB in the reason phrase) | complete | complete | complete | CCC | same |
| Reason-phrase content | `HTTP/1.1 200 O\x01K\r\n\r\n` (0x01 in the reason phrase) | reject | reject | reject | RRR | same |
| Partial input: when a parser gives up | `GET / HTTP/1.` (version cut after 'HTTP/1.') | partial | partial | partial | PPP | same |
| Partial input: when a parser gives up | `GET / HX\r\n\r\nxy` (invalid version prefix, 8 bytes available) | partial | partial | reject | PPR | httparse (rejects earlier) |
| Partial input: when a parser gives up | `GE\x01` (invalid method byte after a full method) | reject | reject | reject | RRR | same |
| Partial input: when a parser gives up | `GET / HTTP/1.1\r\nA: b\r\n c` (obs-fold line cut before its end) | partial | partial | reject | PPR | httparse (rejects earlier) |
| Chunk extensions | `5\r\nhello\r\n0\r\n\r\n` (no extension (baseline)) | complete | complete | complete | CCC | same |
| Chunk extensions | `5;a=b\r\nhello\r\n0\r\n\r\n` (name=value extension) | complete | complete | complete | CCC | same |
| Chunk extensions | `5;a\r\nhello\r\n0\r\n\r\n` (name-only extension) | complete | complete | complete | CCC | same |
| Chunk extensions | `5;\r\nhello\r\n0\r\n\r\n` (empty extension (';' then CRLF)) | complete | complete | complete | CCC | same |
| Chunk extensions | `5;a=\"b c\"\r\nhello\r\n0\r\n\r\n` (quoted-string value) | complete | complete | complete | CCC | same |
| Chunk extensions | `5 ; a = b\r\nhello\r\n0\r\n\r\n` (BWS around ';' and '=') | complete | complete | complete | CCC | same |
| Chunk extensions | `5;a=\xff\r\nhello\r\n0\r\n\r\n` (0xFF in an extension) | complete | complete | complete | CCC | same |
| Chunk extensions | `5;a=\x00\r\nhello\r\n0\r\n\r\n` (NUL in an extension) | complete | complete | complete | CCC | same |
| Chunk extensions | `5;a=b\rc\r\nhello\r\n0\r\n\r\n` (bare CR in an extension) | reject | reject | reject | RRR | same |
| Chunk extensions | `5;a=b\nhello\r\n0\r\n\r\n` (bare LF inside an extension) | reject | reject | complete | RRC | picohttpparser |
| Chunk-size line shape | `5 \r\nhello\r\n0\r\n\r\n` (SP after the size) | complete | complete | complete | CCC | same |
| Chunk-size line shape | `5\t\r\nhello\r\n0\r\n\r\n` (HTAB after the size) | complete | complete | complete | CCC | same |
| Chunk-size line shape | `5\nhello\r\n0\r\n\r\n` (bare LF after the size) | reject | reject | reject | RRR | same |
| Chunk-size line shape | `A\r\n0123456789\r\n0\r\n\r\n` (upper-case hex digit) | complete | complete | complete | CCC | same |
| Chunk-size line shape | `0005\r\nhello\r\n0\r\n\r\n` (leading zeros) | complete | complete | complete | CCC | same |
| Chunk-size line shape | `0x5\r\nhello\r\n0\r\n\r\n` (0x prefix) | reject | reject | reject | RRR | same |
| Chunk-size line shape | `+5\r\nhello\r\n0\r\n\r\n` (plus sign) | reject | reject | reject | RRR | same |
| Chunk-size line shape | `\r\nhello\r\n0\r\n\r\n` (empty size) | reject | reject | complete | RRC | picohttpparser |
| Chunk-size line shape | `5g\r\nhello\r\n0\r\n\r\n` (non-hex byte after the size) | reject | reject | reject | RRR | same |
| Chunk-size line shape | `10000000000000000\r\nhello` (17 hex digits (overflow of u64)) | reject | reject | reject | RRR | same |
| Chunk-size line shape | `000000000000000005\r\nhello\r\n0\r\n\r\n` (18 hex digits with leading zeros) | reject | reject | reject | RRR | same |
