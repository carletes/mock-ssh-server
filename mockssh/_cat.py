import sys


def main():
    dest = sys.stderr if "--stderr" in sys.argv else sys.stdout
    out = dest.buffer if hasattr(dest, "buffer") else dest
    try:
        for line in sys.stdin.buffer if hasattr(sys.stdin, "buffer") else sys.stdin:
            out.write(line)
            out.flush()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
