"""Unit tests for idempotency fingerprinting — spec 17."""
from app.domain.policies.idempotency import fingerprint_request


def test_same_inputs_produce_same_fingerprint():
    fp1 = fingerprint_request("emails", "send_x", {"a": 1})
    fp2 = fingerprint_request("emails", "send_x", {"a": 1})
    assert fp1 == fp2


def test_fingerprint_is_sha256_hex():
    fp = fingerprint_request("q", "t", {"k": "v"})
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_dict_key_order_does_not_matter():
    fp1 = fingerprint_request("q", "t", {"a": 1, "b": 2, "c": 3})
    fp2 = fingerprint_request("q", "t", {"c": 3, "a": 1, "b": 2})
    assert fp1 == fp2


def test_different_payload_yields_different_fingerprint():
    fp1 = fingerprint_request("q", "t", {"a": 1})
    fp2 = fingerprint_request("q", "t", {"a": 2})
    assert fp1 != fp2


def test_different_queue_yields_different_fingerprint():
    fp1 = fingerprint_request("q1", "t", {"a": 1})
    fp2 = fingerprint_request("q2", "t", {"a": 1})
    assert fp1 != fp2


def test_different_task_yields_different_fingerprint():
    fp1 = fingerprint_request("q", "t1", {"a": 1})
    fp2 = fingerprint_request("q", "t2", {"a": 1})
    assert fp1 != fp2
