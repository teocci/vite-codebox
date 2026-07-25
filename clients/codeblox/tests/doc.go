// Package tests holds the end-to-end suite. It drives the built codeblox binary
// as a subprocess rather than calling into the packages, so it exercises what an
// operator — and P-5's Python wrappers — actually see: argv handling, stdout and
// stderr separation, and exit codes. None of that is reachable from the
// package-adjacent unit tests, which call Go functions and never spawn a process.
//
// Every test file carries the `integration` build tag, so `go test ./...` stays
// fast and hermetic and this suite is opt-in:
//
//	go test -tags=integration ./tests/
//
// Each invocation runs with an empty home directory and the file credential
// backend, so the real ~/.codeblox is never read or written and the OS keyring is
// never touched. Tests that need a live world skip when the ws server is not
// listening, so the suite is still useful without `npm start`.
//
// This file carries no build tag on purpose: without it every file in the
// directory would be excluded by default and the package would have no Go files
// to compile.
package tests
