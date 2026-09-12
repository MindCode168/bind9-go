// SPDX-License-Identifier: MPL-2.0
package serial

import (
	"bufio"
	"fmt"
	"os"
	"testing"
)

func TestUpstreamOracle(t *testing.T) {
	f, err := os.Open("testdata/upstream.txt")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	s := bufio.NewScanner(f)
	count := 0
	for s.Scan() {
		var a, b uint32
		var expected [6]int
		n, err := fmt.Sscan(s.Text(), &a, &b, &expected[0], &expected[1],
			&expected[2], &expected[3], &expected[4], &expected[5])
		if err != nil || n != 8 {
			t.Fatalf("invalid fixture: %q", s.Text())
		}
		actual := [6]bool{Less(a, b), Greater(a, b), LessEqual(a, b),
			GreaterEqual(a, b), Equal(a, b), NotEqual(a, b)}
		for i, got := range actual {
			if got != (expected[i] == 1) {
				t.Fatalf("upstream mismatch: a=%d b=%d operation=%d", a, b, i)
			}
		}
		count++
	}
	if err := s.Err(); err != nil {
		t.Fatal(err)
	}
	if count != 8273 {
		t.Fatalf("incomplete fixture: %d cases", count)
	}
}
