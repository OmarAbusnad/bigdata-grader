from grader.final_runtime import _ingest_transport_unproved


def test_p50_single_timeout_is_not_student_http_failure():
    attempts=[{"kind":"json","body_keys":["file_path"],
               "response":{"status":None,"ok":False,
                           "error":"TimeoutError: timed out"}}]
    assert _ingest_transport_unproved(attempts)


def test_http_500_remains_grading_candidate_even_if_followed_by_timeout():
    attempts=[
       {"response":{"status":500,"ok":False,"body":{"detail":"Student exception"}}},
       {"response":{"status":None,"ok":False,"error":"TimeoutError"}},
    ]
    assert not _ingest_transport_unproved(attempts)


def test_http_400_wrong_body_not_transport_failure():
    assert not _ingest_transport_unproved([
        {"response":{"status":400,"ok":False,"body":{"detail":"file_path required"}}}
    ])


def test_empty_attempts_are_not_automatically_transport_blocked():
    assert not _ingest_transport_unproved([])
