from grader.final_runtime import _refresh_transport_unproved


def test_grader_mv_timeout_is_not_an_http_failure():
    timeout={"status":None,"ok":False,"error":"TimeoutError: timed out","is_json":False}
    assert _refresh_transport_unproved(timeout,timeout) is True


def test_real_http_error_is_student_endpoint_failure_not_transport():
    failed={"status":500,"ok":False,"body":{"detail":"server-side error"}}
    assert _refresh_transport_unproved(failed,failed) is False


def test_successful_refresh_is_not_transport_blocked():
    good={"status":200,"ok":True,"body":{"status":"SUCCESS"}}
    assert _refresh_transport_unproved(good,good) is False


def test_transport_exception_on_second_refresh_blocks_incremental_judgment():
    good={"status":200,"ok":True}
    timeout={"status":None,"ok":False,"error":"TimeoutError: timed out"}
    assert _refresh_transport_unproved(good,timeout)
