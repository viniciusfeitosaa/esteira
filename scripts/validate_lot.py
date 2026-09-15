#!/usr/bin/env python3
"""Validate lot accuracy: exit 0 if |c-N|/N <= 0.005"""

import argparse
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--expected", type=float, required=True)
    p.add_argument("--counted", type=float, required=True)
    p.add_argument("--max-error", type=float, default=0.005)
    args = p.parse_args()
    if args.expected <= 0:
        print("expected must be > 0")
        sys.exit(2)
    err = abs(args.counted - args.expected) / args.expected
    ok = err <= args.max_error
    print(
        f"expected={args.expected} counted={args.counted} "
        f"error={err*100:.3f}% limit={args.max_error*100:.2f}% -> "
        f"{'PASS' if ok else 'FAIL'}"
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
