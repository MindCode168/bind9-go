// SPDX-License-Identifier: MPL-2.0
package ttl

import (
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"testing"
)

func TestUpstreamOracle(t *testing.T) {
	data, err := os.ReadFile("testdata/upstream.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixtures struct {
		Parse []struct {
			Hex     string
			Counter bool
			Result  string
			Value   uint32
		}
		Format []struct {
			Value           uint32
			Verbose, Upcase bool
			Text            string
		}
	}
	if err := json.Unmarshal(data, &fixtures); err != nil {
		t.Fatal(err)
	}
	if len(fixtures.Parse) < 10000 || len(fixtures.Format) < 8000 {
		t.Fatal("incomplete oracle fixture")
	}
	for _, tc := range fixtures.Parse {
		input, err := hex.DecodeString(tc.Hex)
		if err != nil {
			t.Fatal(err)
		}
		var got uint32
		if tc.Counter {
			got, err = ParseCounter(string(input))
		} else {
			got, err = Parse(string(input))
		}
		result := "success"
		switch {
		case err == nil:
		case errors.Is(err, ErrSyntax):
			result = "syntax"
		case errors.Is(err, ErrBadTTL):
			result = "badttl"
		case errors.Is(err, ErrRange):
			result = "range"
		default:
			t.Fatalf("unmapped error: %v", err)
		}
		if result != tc.Result || (err == nil && got != tc.Value) {
			t.Fatalf("C/Go mismatch for %q counter=%t: Go %d/%s, C %d/%s", input, tc.Counter, got, result, tc.Value, tc.Result)
		}
	}
	for _, tc := range fixtures.Format {
		if got := Format(tc.Value, tc.Verbose, tc.Upcase); got != tc.Text {
			t.Fatalf("C/Go format mismatch: %d verbose=%t upcase=%t: %q != %q", tc.Value, tc.Verbose, tc.Upcase, got, tc.Text)
		}
	}
}

func FuzzParse(f *testing.F) {
	for _, s := range []string{"", "0h5", "1h5", "4294967295s1s", "1\x00junk", "1w2d3h", "\xff"} {
		f.Add(s)
	}
	f.Fuzz(func(t *testing.T, s string) {
		value, err := Parse(s)
		counter, counterErr := ParseCounter(s)
		if err == nil {
			if counterErr != nil || value != counter {
				t.Fatal("counter and TTL disagree")
			}
			back, backErr := Parse(Format(value, false, false))
			if backErr != nil || back != value {
				t.Fatal("accepted TTL cannot be represented")
			}
		} else if errors.Is(err, ErrRange) {
			if !errors.Is(counterErr, ErrRange) {
				t.Fatal("range classification mismatch")
			}
		} else if !errors.Is(err, ErrBadTTL) || !errors.Is(counterErr, ErrSyntax) {
			t.Fatal("syntax classification mismatch")
		}
	})
}
