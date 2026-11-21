"""Install the pinned Apache Tika DOC parser locally, verifying its release SHA-512."""

import hashlib
from pathlib import Path

import httpx

VERSION = "3.3.3"
SHA512 = (
    "3c6e62e864e32af234832ec6d928bbc58692d3ddd60564cd8c80dee7e161653d6"
    "efcba373b6cc9468c778010bea92bdee5ca75ab24f01923480bec1b29b573fd"
)


def main():
    target = Path("data/tools") / f"tika-app-{VERSION}.jar"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and hashlib.sha512(target.read_bytes()).hexdigest() == SHA512:
        print(f"Verified {target}")
        return
    url = f"https://downloads.apache.org/tika/{VERSION}/tika-app-{VERSION}.jar"
    temporary = target.with_suffix(".download")
    try:
        with httpx.stream("GET", url, timeout=180, follow_redirects=True) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for block in response.iter_bytes():
                    output.write(block)
        if hashlib.sha512(temporary.read_bytes()).hexdigest() != SHA512:
            raise ValueError("Tika release checksum mismatch")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Installed {target}; requires Java 17+")


if __name__ == "__main__":
    main()
