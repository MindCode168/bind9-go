// SPDX-License-Identifier: MPL-2.0
package ttl

import (
	"errors"
	"strings"
	"testing"
)

func TestParse(t *testing.T) {
	for _, tc := range []struct {
		text string
		want uint32
		err  error
	}{
		{"0", 0, nil}, {"4294967295", 0xffffffff, nil},
		{"1W2D3H4M5S", 788645, nil}, {"1s1h", 3601, nil}, {"1h1h", 7200, nil},
		{"0h5", 5, nil}, {"01", 1, nil}, {"60s", 60, nil}, {"1\x00junk", 1, nil},
		{"", 0, ErrBadTTL}, {"-1", 0, ErrBadTTL}, {"+1", 0, ErrBadTTL},
		{"1 ", 0, ErrBadTTL}, {" 1", 0, ErrBadTTL}, {"1h5", 0, ErrBadTTL},
		{"4294967296", 0, ErrBadTTL}, {"4294967295s1s", 0, ErrRange},
		{"4294967295w", 0, ErrRange}, {"1x", 0, ErrBadTTL},
		{strings.Repeat("0", 64), 0, ErrBadTTL}, {strings.Repeat("0", 63), 0, nil},
	} {
		got, err := Parse(tc.text)
		if got != tc.want || !errors.Is(err, tc.err) {
			t.Errorf("Parse(%q) = %d,%v; want %d,%v", tc.text, got, err, tc.want, tc.err)
		}
	}
	if _, err := ParseCounter("invalid"); !errors.Is(err, ErrSyntax) {
		t.Fatal("counter syntax error mapping")
	}
}

func TestFormat(t *testing.T) {
	for _, tc := range []struct {
		value           uint32
		verbose, upcase bool
		want            string
	}{
		{0, false, false, "0s"}, {0, false, true, "0S"}, {0, true, true, "0 seconds"},
		{3600, false, true, "1H"}, {3661, false, true, "1h1m1s"},
		{3600, true, false, "1 hour"}, {7200, true, false, "2 hours"},
		{788645, false, false, "1w2d3h4m5s"},
		{788645, true, true, "1 week 2 days 3 hours 4 minutes 5 seconds"},
	} {
		if got := Format(tc.value, tc.verbose, tc.upcase); got != tc.want {
			t.Errorf("Format(%d) = %q; want %q", tc.value, got, tc.want)
		}
	}
}

func FuzzRoundTrip(f *testing.F) {
	f.Add(uint32(0))
	f.Add(uint32(0xffffffff))
	f.Add(uint32(788645))
	f.Fuzz(func(t *testing.T, value uint32) {
		for _, upcase := range []bool{false, true} {
			encoded := Format(value, false, upcase)
			got, err := Parse(encoded)
			if err != nil || got != value {
				t.Fatalf("round trip failed: %q", encoded)
			}
		}
	})
}
