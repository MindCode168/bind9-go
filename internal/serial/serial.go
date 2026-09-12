// SPDX-License-Identifier: MPL-2.0
// Package serial implements the 32-bit serial number arithmetic used by DNS.
package serial

import "errors"

// ErrUndefined reports the half-range ambiguity defined by RFC 1982.
var ErrUndefined = errors.New("serial number operation is undefined")

// Less implements isc_serial_lt, including false for undefined ordering.
func Less(a, b uint32) bool { c, err := Compare(a, b); return err == nil && c < 0 }

// Greater implements isc_serial_gt.
func Greater(a, b uint32) bool { c, err := Compare(a, b); return err == nil && c > 0 }

// LessEqual implements isc_serial_le.
func LessEqual(a, b uint32) bool { return a == b || Less(a, b) }

// GreaterEqual implements isc_serial_ge.
func GreaterEqual(a, b uint32) bool { return a == b || Greater(a, b) }

// Equal implements isc_serial_eq.
func Equal(a, b uint32) bool { return a == b }

// NotEqual implements isc_serial_ne.
func NotEqual(a, b uint32) bool { return a != b }

// Compare returns -1, 0, or 1 according to serial arithmetic. Values exactly
// 2^31 apart have no defined ordering and return ErrUndefined.
func Compare(a, b uint32) (int, error) {
	if a == b {
		return 0, nil
	}
	d := a - b
	if d == 1<<31 {
		return 0, ErrUndefined
	}
	if d < 1<<31 {
		return 1, nil
	}
	return -1, nil
}

// Add advances a serial by an increment in [0, 2^31-1], wrapping modulo 2^32.
func Add(value, increment uint32) (uint32, error) {
	if increment >= 1<<31 {
		return 0, ErrUndefined
	}
	return value + increment, nil
}
