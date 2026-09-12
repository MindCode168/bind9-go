package serial

import (
	"errors"
	"testing"
)

func TestCompare(t *testing.T) {
	for _, tc := range []struct {
		a, b      uint32
		want      int
		undefined bool
	}{
		{0, 0, 0, false},
		{1, 0, 1, false},
		{0, 1, -1, false},
		{0, 0xffffffff, 1, false},
		{0xffffffff, 0, -1, false},
		{0x7fffffff, 0, 1, false},
		{0x80000000, 0, 0, true},
		{0, 0x80000000, 0, true},
		{0x80000001, 0, -1, false},
	} {
		got, err := Compare(tc.a, tc.b)
		if got != tc.want || errors.Is(err, ErrUndefined) != tc.undefined {
			t.Errorf("Compare(%d,%d) = %d,%v", tc.a, tc.b, got, err)
		}
	}
}

func TestAdd(t *testing.T) {
	for _, tc := range []struct {
		value, increment, want uint32
		undefined              bool
	}{
		{0xffffffff, 1, 0, false},
		{10, 0x7fffffff, 0x80000009, false},
		{10, 0, 10, false},
		{0, 0x80000000, 0, true},
		{1, 0xffffffff, 0, true},
	} {
		got, err := Add(tc.value, tc.increment)
		if got != tc.want || errors.Is(err, ErrUndefined) != tc.undefined {
			t.Errorf("Add(%d,%d) = %d,%v", tc.value, tc.increment, got, err)
		}
	}
}

func FuzzCompare(t *testing.F) {
	t.Add(uint32(0), uint32(0xffffffff))
	t.Add(uint32(0x80000000), uint32(0))
	t.Fuzz(func(t *testing.T, a, b uint32) {
		ab, e1 := Compare(a, b)
		ba, e2 := Compare(b, a)
		if !errors.Is(e1, e2) || ab != -ba {
			t.Fatal("serial comparison is not antisymmetric")
		}
		increment := b & 0x7fffffff
		next, err := Add(a, increment)
		if err != nil {
			t.Fatal(err)
		}
		cmp, err := Compare(next, a)
		if err != nil || (increment == 0 && cmp != 0) || (increment > 0 && cmp != 1) {
			t.Fatal("advancing a serial did not preserve serial ordering")
		}
	})
}
