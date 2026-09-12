// Copyright (C) Internet Systems Consortium, Inc. ("ISC")
// SPDX-License-Identifier: MPL-2.0
// Go adaptation of BIND 9.20.27 lib/dns/ttl.c.

// Package ttl implements BIND's TTL and counter text syntax.
package ttl

import (
	"errors"
	"strconv"
	"strings"
)

var (
	ErrSyntax = errors.New("syntax error")
	ErrBadTTL = errors.New("bad TTL")
	ErrRange  = errors.New("out of range")
)

// Parse corresponds to dns_ttl_fromtext. It preserves BIND's accepted syntax,
// including repeated units, unordered units, and case-insensitive unit letters.
func Parse(text string) (uint32, error) {
	n, err := ParseCounter(text)
	if err != nil && !errors.Is(err, ErrRange) {
		return 0, ErrBadTTL
	}
	return n, err
}

// ParseCounter corresponds to dns_counter_fromtext.
func ParseCounter(text string) (uint32, error) {
	if len(text) > 63 {
		return 0, ErrSyntax
	}
	// Upstream copies its text region through snprintf, stopping at the first NUL.
	if end := strings.IndexByte(text, 0); end >= 0 {
		text = text[:end]
	}
	var sum uint64
	for pos := 0; ; {
		start := pos
		for pos < len(text) && text[pos] >= '0' && text[pos] <= '9' {
			pos++
		}
		if pos == start {
			return 0, ErrSyntax
		}
		n, err := strconv.ParseUint(text[start:pos], 10, 32)
		if err != nil {
			return 0, ErrSyntax
		}
		if pos == len(text) {
			if sum != 0 {
				return 0, ErrSyntax
			}
			sum = n
			break
		}
		var factor uint64
		switch text[pos] {
		case 'w', 'W':
			factor = 7 * 24 * 3600
		case 'd', 'D':
			factor = 24 * 3600
		case 'h', 'H':
			factor = 3600
		case 'm', 'M':
			factor = 60
		case 's', 'S':
			factor = 1
		default:
			return 0, ErrSyntax
		}
		sum += n * factor
		pos++
		if pos == len(text) {
			break
		}
	}
	if sum > 0xffffffff {
		return 0, ErrRange
	}
	return uint32(sum), nil
}

// Format corresponds to dns_ttl_totext without the C destination-buffer limit.
// With upcase, a lone abbreviated unit is uppercase; mixed units stay lowercase.
func Format(value uint32, verbose, upcase bool) string {
	units := []struct {
		size uint32
		name string
	}{
		{604800, "week"}, {86400, "day"}, {3600, "hour"}, {60, "minute"}, {1, "second"},
	}
	parts := make([]string, 0, 5)
	for _, unit := range units {
		n := value / unit.size
		value %= unit.size
		if n == 0 && !(unit.size == 1 && len(parts) == 0) {
			continue
		}
		part := strconv.FormatUint(uint64(n), 10)
		if verbose {
			part += " " + unit.name
			if n != 1 {
				part += "s"
			}
		} else {
			part += unit.name[:1]
		}
		parts = append(parts, part)
	}
	if verbose {
		return strings.Join(parts, " ")
	}
	if upcase && len(parts) == 1 {
		return strings.ToUpper(parts[0])
	}
	return strings.Join(parts, "")
}
